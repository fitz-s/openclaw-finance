#!/usr/bin/env python3
"""Brave Answers citation-gated sidecar."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from brave_search_fetcher_common import application_error_code, classify_error, quota_state_from_headers, read_api_key, safe_state_path, stable_id, write_jsonl

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OUT = STATE / 'brave-answer-sidecars' / 'latest.jsonl'
BRAVE_ANSWERS_URL = 'https://api.search.brave.com/res/v1/chat/completions'
ENDPOINT = 'brave/answers/chat_completions'
SOURCE_ID = 'source:brave_answers'
MODEL = 'brave'
MAX_DERIVED_PREVIEW_CHARS = 1200
CITATION_TAG_RE = re.compile(r'<citation>(.*?)</citation>', re.DOTALL | re.IGNORECASE)
ENUM_TAG_RE = re.compile(r'<enum_item>(.*?)</enum_item>', re.DOTALL | re.IGNORECASE)
USAGE_TAG_RE = re.compile(r'<usage>(.*?)</usage>', re.DOTALL | re.IGNORECASE)
URL_RE = re.compile(r'https?://[^\s<>{}"\]]+')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def short_text(value: Any, limit: int = MAX_DERIVED_PREVIEW_CHARS) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def domain_from_url(url: str) -> str | None:
    try:
        host = urlparse(url).netloc.lower().removeprefix('www.')
    except Exception:
        return None
    return host or None


def validate_pack(pack: dict[str, Any]) -> list[str]:
    reasons = []
    if not str(pack.get('query') or pack.get('prompt') or '').strip():
        reasons.append('missing_prompt')
    if pack.get('authority_level') != 'sidecar_only':
        reasons.append('answers_requires_sidecar_only_authority')
    if pack.get('purpose') not in {None, 'sidecar_synthesis', 'followup_slice', 'source_trace', 'claim_closure'}:
        reasons.append('invalid_answers_purpose')
    return reasons


def system_prompt(pack: dict[str, Any]) -> str:
    return str(pack.get('system_prompt') or (
        'You are a review-only finance source sidecar. Provide grounded synthesis only. '
        'Do not recommend trades, do not mutate thresholds, and do not create a new judgment. '
        'Citations are required for any source-dependent statement.'
    ))


def build_request_payload(pack: dict[str, Any]) -> dict[str, Any]:
    prompt = str(pack.get('prompt') or pack.get('query') or '').strip()
    payload = {
        'model': pack.get('model') or MODEL,
        'stream': True,
        'messages': [
            {'role': 'system', 'content': system_prompt(pack)},
            {'role': 'user', 'content': prompt[:4000]},
        ],
        'enable_citations': True,
        'enable_entities': bool(pack.get('enable_entities', False)),
        'enable_research': bool(pack.get('enable_research', False)),
    }
    for key in ('country', 'language'):
        if pack.get(key):
            payload[key] = pack[key]
    return payload


def execute_answers_request(payload: dict[str, Any], *, api_key: str, timeout: int = 60) -> tuple[str, int | None, dict[str, Any], str, dict[str, Any], str | None]:
    request = urllib.request.Request(
        BRAVE_ANSWERS_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Accept': 'text/event-stream, application/json',
            'Content-Type': 'application/json',
            'X-Subscription-Token': api_key,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode('utf-8', errors='replace')
            return 'ok', response.status, dict(response.headers.items()), body, {}, None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}
        status = 'rate_limited' if exc.code in {402, 429} else 'failed'
        return status, exc.code, dict(exc.headers.items()), body, payload if isinstance(payload, dict) else {}, str(exc.code)
    except Exception as exc:
        return 'failed', None, {}, '', {}, exc.__class__.__name__


def iter_sse_payloads(stream_text: str) -> list[dict[str, Any]]:
    payloads = []
    for line in stream_text.splitlines():
        line = line.strip()
        if not line.startswith('data:'):
            continue
        data = line[5:].strip()
        if not data or data == '[DONE]':
            continue
        try:
            item = json.loads(data)
        except Exception:
            continue
        if isinstance(item, dict):
            payloads.append(item)
    return payloads


def content_from_stream(stream_text: str) -> str:
    chunks: list[str] = []
    for item in iter_sse_payloads(stream_text):
        choices = item.get('choices') if isinstance(item.get('choices'), list) else []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            delta = choice.get('delta') if isinstance(choice.get('delta'), dict) else {}
            content = delta.get('content') or choice.get('text')
            if isinstance(content, str):
                chunks.append(content)
    if chunks:
        return ''.join(chunks)
    try:
        payload = json.loads(stream_text)
    except Exception:
        return stream_text
    choices = payload.get('choices') if isinstance(payload, dict) else []
    if isinstance(choices, list):
        for choice in choices:
            message = choice.get('message') if isinstance(choice, dict) else None
            if isinstance(message, dict) and isinstance(message.get('content'), str):
                return message['content']
    return stream_text


def parse_jsonish_blob(blob: str) -> Any:
    blob = blob.strip()
    try:
        return json.loads(blob)
    except Exception:
        return blob


def citation_payloads(blob: str) -> list[dict[str, Any]]:
    payload = parse_jsonish_blob(blob)
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, str):
        return [{'url': url} for url in URL_RE.findall(payload)]
    return []


def urls_from_blob(blob: str) -> list[str]:
    payload = parse_jsonish_blob(blob)
    found: list[str] = []
    if isinstance(payload, str):
        found.extend(URL_RE.findall(payload))
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                found.extend(URL_RE.findall(item))
            elif isinstance(item, dict):
                found.extend(str(item.get(key)) for key in ('url', 'uri', 'link') if item.get(key))
    elif isinstance(payload, dict):
        found.extend(str(payload.get(key)) for key in ('url', 'uri', 'link') if payload.get(key))
        values = payload.get('urls') or payload.get('citations')
        if isinstance(values, list):
            for item in values:
                if isinstance(item, str):
                    found.append(item)
                elif isinstance(item, dict):
                    found.extend(str(item.get(key)) for key in ('url', 'uri', 'link') if item.get(key))
    return [url for url in found if isinstance(url, str) and url.startswith(('http://', 'https://'))]


def extract_citations(answer_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in CITATION_TAG_RE.findall(answer_text or ''):
        payloads = citation_payloads(match)
        if payloads:
            for payload in payloads:
                url = str(payload.get('url') or payload.get('uri') or payload.get('link') or '')
                if not url:
                    for candidate_url in urls_from_blob(match):
                        rows.append({'url': candidate_url})
                    continue
                rows.append(payload)
        else:
            rows.extend({'url': url} for url in urls_from_blob(match))
    rows.extend({'url': url} for url in URL_RE.findall(CITATION_TAG_RE.sub('', answer_text or '')))
    deduped: list[dict[str, Any]] = []
    seen = set()
    for row in rows:
        url = str(row.get('url') or '').rstrip(').,;')
        if not url.startswith(('http://', 'https://')):
            continue
        if url in seen:
            continue
        seen.add(url)
        deduped.append(row | {'url': url})
    return [
        {
            'citation_id': stable_id('citation', row['url']),
            'url': row['url'],
            'domain': domain_from_url(row['url']),
            'number': row.get('number'),
            'start_index': row.get('start_index'),
            'end_index': row.get('end_index'),
            'favicon_present': bool(row.get('favicon')),
            'snippet_digest': canonical_hash(row.get('snippet')) if row.get('snippet') else None,
            'raw_snippet_persisted': False,
            'metadata_only': True,
        }
        for row in deduped
    ]


def strip_citation_tags(answer_text: str) -> str:
    text = CITATION_TAG_RE.sub('', answer_text or '')
    text = ENUM_TAG_RE.sub('', text)
    text = USAGE_TAG_RE.sub('', text)
    return text


def enum_item_summary(answer_text: str) -> dict[str, Any]:
    return {
        'count': len(ENUM_TAG_RE.findall(answer_text or '')),
        'raw_enum_items_persisted': False,
    }


def usage_summary(answer_text: str) -> dict[str, Any]:
    matches = USAGE_TAG_RE.findall(answer_text or '')
    if not matches:
        return {'present': False, 'raw_usage_persisted': False}
    latest = parse_jsonish_blob(matches[-1])
    if not isinstance(latest, dict):
        return {'present': True, 'raw_usage_persisted': False}
    allowed = {key: latest.get(key) for key in ('prompt_tokens', 'completion_tokens', 'total_tokens', 'input_tokens', 'output_tokens') if key in latest}
    allowed['present'] = True
    allowed['raw_usage_persisted'] = False
    return allowed


def evidence_candidates_from_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            'candidate_id': stable_id('evidence-candidate', citation['url']),
            'candidate_type': 'citation_url',
            'url': citation['url'],
            'domain': citation.get('domain'),
            'source_id': SOURCE_ID,
            'promotion_path': 'citation_only',
            'requires_fetch_before_evidence_atom': True,
            'metadata_only': True,
            'no_execution': True,
        }
        for citation in citations
    ]


def build_sidecar_record(
    pack: dict[str, Any],
    *,
    request_payload: dict[str, Any],
    status: str,
    status_code: int | None,
    headers: dict[str, Any],
    stream_text: str,
    error_payload: dict[str, Any] | None = None,
    error_code: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    answer_text = '' if dry_run else content_from_stream(stream_text)
    citations = [] if dry_run else extract_citations(answer_text)
    candidates = evidence_candidates_from_citations(citations) if citations else []
    app_code = application_error_code(error_payload or {}, error_code)
    error_meta = classify_error(status_code, app_code)
    safe_request = {
        'model': request_payload.get('model'),
        'stream': request_payload.get('stream'),
        'enable_citations': request_payload.get('enable_citations'),
        'enable_entities': request_payload.get('enable_entities'),
        'enable_research': request_payload.get('enable_research'),
        'country': request_payload.get('country'),
        'language': request_payload.get('language'),
        'message_count': len(request_payload.get('messages') or []),
    }
    preview = short_text(strip_citation_tags(answer_text))
    record = {
        'contract': 'brave-answers-sidecar-v1',
        'answer_id': stable_id('answer-sidecar', pack.get('pack_id'), canonical_hash(safe_request), canonical_hash(preview)),
        'pack_id': pack.get('pack_id'),
        'source_id': SOURCE_ID,
        'endpoint': ENDPOINT,
        'model': request_payload.get('model') or MODEL,
        'request_params': safe_request,
        'fetched_at': now_iso(),
        'status': 'dry_run' if dry_run else status,
        'quota_state': quota_state_from_headers(headers, status_code=status_code),
        'error_code': error_code,
        'application_error_code': app_code,
        'error_class': error_meta['error_class'],
        'retryable': error_meta['retryable'],
        'authority_level': 'sidecar_only',
        'answer_authority': 'derived_context_hypothesis_only',
        'derived_context_preview': preview,
        'answer_text_digest': canonical_hash(answer_text) if answer_text else None,
        'answer_text_is_canonical_evidence': False,
        'citation_count': len(citations),
        'citations': citations,
        'citation_evidence_candidates': candidates,
        'entity_telemetry': enum_item_summary(answer_text),
        'usage_telemetry': usage_summary(answer_text),
        'promotion_eligible': bool(candidates),
        'promotion_rule': 'citations_only; answer_text_never_promotes',
        'raw_stream_persisted': False,
        'raw_response_persisted': False,
        'metadata_only': True,
        'sidecar_only': True,
        'no_execution': True,
    }
    if dry_run:
        record['dry_run'] = True
    return record


def blocked_record(pack: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    return {
        'contract': 'brave-answers-sidecar-v1',
        'answer_id': stable_id('answer-sidecar', pack.get('pack_id'), 'blocked'),
        'pack_id': pack.get('pack_id'),
        'source_id': SOURCE_ID,
        'endpoint': ENDPOINT,
        'model': pack.get('model') or MODEL,
        'fetched_at': now_iso(),
        'status': 'blocked',
        'blocking_reasons': reasons,
        'authority_level': 'sidecar_only',
        'answer_authority': 'derived_context_hypothesis_only',
        'citation_count': 0,
        'citations': [],
        'citation_evidence_candidates': [],
        'promotion_eligible': False,
        'promotion_rule': 'blocked_or_no_citations',
        'raw_stream_persisted': False,
        'raw_response_persisted': False,
        'metadata_only': True,
        'sidecar_only': True,
        'no_execution': True,
    }


def run_sidecar(pack: dict[str, Any], *, api_key: str | None = None, dry_run: bool = False, timeout: int = 60) -> dict[str, Any]:
    reasons = validate_pack(pack)
    if reasons:
        return blocked_record(pack, reasons)
    payload = build_request_payload(pack)
    if dry_run:
        return build_sidecar_record(pack, request_payload=payload, status='dry_run', status_code=None, headers={}, stream_text='', dry_run=True)
    key = api_key or read_api_key()
    if not key:
        return build_sidecar_record(pack, request_payload=payload, status='failed', status_code=None, headers={}, stream_text='', error_code='missing_api_key')
    status, status_code, headers, stream_text, error_payload, error_code = execute_answers_request(payload, api_key=key, timeout=timeout)
    return build_sidecar_record(pack, request_payload=payload, status=status, status_code=status_code, headers=headers, stream_text=stream_text, error_payload=error_payload, error_code=error_code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--pack', required=True)
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--timeout', type=int, default=60)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_state_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    pack = load_json(Path(args.pack), {}) or {}
    record = run_sidecar(pack, dry_run=args.dry_run, timeout=args.timeout)
    existing = [] if not out.exists() else [json.loads(line) for line in out.read_text(encoding='utf-8', errors='replace').splitlines() if line.strip()]
    existing.append(record)
    write_jsonl(out, existing)
    print(json.dumps({'status': record['status'], 'endpoint': record['endpoint'], 'citation_count': record['citation_count'], 'promotion_eligible': record['promotion_eligible'], 'out': str(out)}, ensure_ascii=False))
    return 0 if record['status'] in {'ok', 'dry_run', 'blocked'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
