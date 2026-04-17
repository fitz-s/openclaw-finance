#!/usr/bin/env python3
"""Brave LLM Context selected-source reader."""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from brave_search_fetcher_common import (
    BRAVE_API_BASE,
    application_error_code,
    classify_error,
    domain_from_url,
    freshness_param,
    now_iso,
    query_with_domains,
    quota_state_from_headers,
    read_api_key,
    safe_state_path,
    stable_id,
    write_jsonl,
)

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OUT = STATE / 'brave-llm-context-results.jsonl'
ENDPOINT = 'brave/llm/context'
SOURCE_ID = 'source:brave_llm_context'
PATH = '/llm/context'


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def clamp_int(value: Any, *, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(low, min(parsed, high))


def selected_domains(pack: dict[str, Any]) -> list[str]:
    domains: set[str] = set()
    if isinstance(pack.get('allowed_domains'), list):
        for item in pack['allowed_domains']:
            text = str(item or '').strip().lower().removeprefix('https://').removeprefix('http://').split('/')[0].removeprefix('www.')
            if text:
                domains.add(text)
    if isinstance(pack.get('selected_urls'), list):
        for url in pack['selected_urls']:
            domain = domain_from_url(url)
            if domain:
                domains.add(domain)
    return sorted(domains)


def is_scoped(pack: dict[str, Any]) -> bool:
    return bool(selected_domains(pack) or pack.get('goggles'))


def validate_pack(pack: dict[str, Any]) -> list[str]:
    reasons = []
    if not str(pack.get('query') or '').strip():
        reasons.append('missing_query')
    if not is_scoped(pack):
        reasons.append('unscoped_reader_query')
    if pack.get('purpose') not in {None, 'source_reading', 'claim_closure', 'followup_slice'}:
        reasons.append('invalid_reader_purpose')
    return reasons


def trim_query(query: Any) -> str:
    words = ' '.join(str(query or '').split()).split()
    trimmed = ' '.join(words[:50])
    return trimmed[:400]


def build_context_params(pack: dict[str, Any]) -> dict[str, Any]:
    domains = selected_domains(pack)
    snippet_cap = clamp_int(pack.get('maximum_number_of_snippets_cap'), default=100, low=1, high=256)
    params: dict[str, Any] = {
        'q': query_with_domains(trim_query(pack.get('query')), domains),
        'count': clamp_int(pack.get('count') or pack.get('max_results'), default=10, low=1, high=50),
        'maximum_number_of_urls': clamp_int(pack.get('maximum_number_of_urls'), default=10, low=1, high=50),
        'maximum_number_of_tokens': clamp_int(pack.get('maximum_number_of_tokens'), default=4096, low=1024, high=32768),
        'maximum_number_of_snippets': clamp_int(pack.get('maximum_number_of_snippets'), default=20, low=1, high=snippet_cap),
        'maximum_number_of_tokens_per_url': clamp_int(pack.get('maximum_number_of_tokens_per_url'), default=2048, low=512, high=8192),
        'maximum_number_of_snippets_per_url': clamp_int(pack.get('maximum_number_of_snippets_per_url'), default=10, low=1, high=100),
        'context_threshold_mode': pack.get('context_threshold_mode') or 'strict',
    }
    fresh = freshness_param(pack)
    if fresh:
        params['freshness'] = fresh
    for key in ('country', 'search_lang', 'goggles', 'enable_local', 'enable_source_metadata'):
        if pack.get(key) is not None:
            params[key] = pack[key]
    return params


def execute_context_request(params: dict[str, Any], *, api_key: str, timeout: int = 30) -> tuple[str, int | None, dict[str, Any], dict[str, Any], str | None]:
    request = urllib.request.Request(
        BRAVE_API_BASE + PATH,
        data=json.dumps(params).encode('utf-8'),
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'X-Subscription-Token': api_key,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode('utf-8', errors='replace')
            payload = json.loads(body) if body else {}
            return 'ok', response.status, dict(response.headers.items()), payload if isinstance(payload, dict) else {}, None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}
        status = 'rate_limited' if exc.code in {402, 429} else 'failed'
        return status, exc.code, dict(exc.headers.items()), payload if isinstance(payload, dict) else {}, str(exc.code)
    except Exception as exc:
        return 'failed', None, {}, {}, exc.__class__.__name__


def snippet_digest(snippets: list[Any]) -> str | None:
    clean = [' '.join(str(item or '').split()) for item in snippets if item]
    if not clean:
        return None
    return canonical_hash(clean)


def context_refs_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    grounding = payload.get('grounding') if isinstance(payload, dict) else {}
    generic = grounding.get('generic') if isinstance(grounding, dict) else []
    sources = payload.get('sources') if isinstance(payload.get('sources'), dict) else {}
    refs: list[dict[str, Any]] = []
    for item in generic if isinstance(generic, list) else []:
        if not isinstance(item, dict) or not item.get('url'):
            continue
        url = str(item['url'])
        snippets = item.get('snippets') if isinstance(item.get('snippets'), list) else []
        source_meta = sources.get(url) if isinstance(sources.get(url), dict) else {}
        refs.append({
            'context_ref_id': stable_id('context-ref', url, snippet_digest(snippets)),
            'url': url,
            'hostname': source_meta.get('hostname') or domain_from_url(url),
            'title': source_meta.get('title') or item.get('title'),
            'age': source_meta.get('age'),
            'snippet_count': len(snippets),
            'snippet_digest': snippet_digest(snippets),
            'raw_snippets_persisted': False,
            'metadata_only': True,
        })
    return refs


def local_recall_summary(payload: dict[str, Any]) -> dict[str, Any]:
    grounding = payload.get('grounding') if isinstance(payload, dict) else {}
    poi = grounding.get('poi') if isinstance(grounding, dict) else None
    maps = grounding.get('map') if isinstance(grounding, dict) else []
    return {
        'poi_present': bool(poi),
        'map_count': len(maps) if isinstance(maps, list) else 0,
        'raw_local_payload_persisted': False,
    }


def record_from_response(
    pack: dict[str, Any],
    *,
    params: dict[str, Any],
    status: str,
    status_code: int | None,
    headers: dict[str, Any],
    payload: dict[str, Any],
    error_code: str | None,
    dry_run: bool = False,
    fetched_at: str | None = None,
) -> dict[str, Any]:
    refs = [] if dry_run else context_refs_from_payload(payload)
    app_code = application_error_code(payload, error_code)
    error_meta = classify_error(status_code, app_code)
    request_params = {k: v for k, v in params.items() if 'token' not in k.lower() and 'key' not in k.lower()}
    return {
        'contract': 'source-fetch-record-v1',
        'fetch_id': stable_id('fetch', ENDPOINT, canonical_hash(request_params), fetched_at or now_iso(), status),
        'pack_id': pack.get('pack_id'),
        'source_id': SOURCE_ID,
        'lane': pack.get('lane') or 'news_policy_narrative',
        'endpoint': ENDPOINT,
        'request_params': request_params,
        'fetched_at': fetched_at or now_iso(),
        'status': 'dry_run' if dry_run else status,
        'quota_state': quota_state_from_headers(headers, status_code=status_code),
        'result_count': len(refs),
        'watermark_key': ':'.join([str(pack.get('lane') or 'news_policy_narrative'), 'llm_context', ','.join(selected_domains(pack)) or 'scoped']),
        'error_code': error_code,
        'application_error_code': app_code,
        'error_class': error_meta['error_class'],
        'retryable': error_meta['retryable'],
        'context_refs': refs,
        'local_recall_summary': local_recall_summary(payload) if not dry_run else {'poi_present': False, 'map_count': 0, 'raw_local_payload_persisted': False},
        'selected_source_reading': True,
        'evidence_candidate_only': True,
        'raw_context_persisted': False,
        'raw_snippets_persisted': False,
        'metadata_only': True,
        'no_execution': True,
    }


def fetch_context(pack: dict[str, Any], *, api_key: str | None = None, dry_run: bool = False, timeout: int = 30) -> dict[str, Any]:
    reasons = validate_pack(pack)
    params = build_context_params(pack) if not reasons or 'missing_query' not in reasons else {}
    if reasons:
        return {
            'contract': 'source-fetch-record-v1',
            'fetch_id': stable_id('fetch', ENDPOINT, canonical_hash(params), 'blocked'),
            'pack_id': pack.get('pack_id'),
            'source_id': SOURCE_ID,
            'lane': pack.get('lane') or 'news_policy_narrative',
            'endpoint': ENDPOINT,
            'request_params': params,
            'fetched_at': now_iso(),
            'status': 'blocked',
            'blocking_reasons': reasons,
            'result_count': 0,
            'selected_source_reading': True,
            'evidence_candidate_only': True,
            'raw_context_persisted': False,
            'raw_snippets_persisted': False,
            'metadata_only': True,
            'no_execution': True,
        }
    if dry_run:
        return record_from_response(pack, params=params, status='dry_run', status_code=None, headers={}, payload={}, error_code=None, dry_run=True)
    key = api_key or read_api_key()
    if not key:
        return record_from_response(pack, params=params, status='failed', status_code=None, headers={}, payload={}, error_code='missing_api_key')
    status, status_code, headers, payload, error_code = execute_context_request(params, api_key=key, timeout=timeout)
    return record_from_response(pack, params=params, status=status, status_code=status_code, headers=headers, payload=payload, error_code=error_code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--pack', required=True)
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--timeout', type=int, default=30)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_state_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    pack = load_json(Path(args.pack), {}) or {}
    record = fetch_context(pack, dry_run=args.dry_run, timeout=args.timeout)
    existing = [] if not out.exists() else [json.loads(line) for line in out.read_text(encoding='utf-8', errors='replace').splitlines() if line.strip()]
    existing.append(record)
    write_jsonl(out, existing)
    print(json.dumps({'status': record['status'], 'endpoint': record['endpoint'], 'result_count': record['result_count'], 'out': str(out)}, ensure_ascii=False))
    return 0 if record['status'] in {'ok', 'partial', 'dry_run', 'blocked'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
