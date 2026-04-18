#!/usr/bin/env python3
"""Shared deterministic Brave Web/News fetcher helpers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from query_registry_compiler import should_skip_query, load_jsonl as load_query_registry

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
QUERY_REGISTRY = STATE / 'query-registry.jsonl'
OPENCLAW_CONFIG = Path('/Users/leofitz/.openclaw/openclaw.json')
BRAVE_API_BASE = 'https://api.search.brave.com/res/v1'
ENDPOINTS = {
    'web': {
        'endpoint': 'brave/web/search',
        'path': '/web/search',
        'source_id': 'source:brave_web',
        'result_container': 'web',
        'max_count': 20,
        'default_safesearch': 'moderate',
    },
    'news': {
        'endpoint': 'brave/news/search',
        'path': '/news/search',
        'source_id': 'source:brave_news',
        'result_container': 'news',
        'max_count': 50,
        'default_safesearch': 'strict',
    },
}
FRESHNESS_MAP = {
    'day': 'pd',
    'last_24h': 'pd',
    'pd': 'pd',
    'week': 'pw',
    'last_7d': 'pw',
    'pw': 'pw',
    'month': 'pm',
    'pm': 'pm',
    'year': 'py',
    'py': 'py',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(part or '') for part in parts)
    return f'{prefix}:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp')
    tmp.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows), encoding='utf-8')
    tmp.replace(path)


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def normalize_domain(domain: Any) -> str | None:
    text = str(domain or '').strip().lower()
    if not text:
        return None
    text = text.removeprefix('https://').removeprefix('http://').split('/')[0].removeprefix('www.')
    return text or None


def domain_from_url(url: Any) -> str | None:
    try:
        host = urllib.parse.urlparse(str(url or '')).netloc.lower().removeprefix('www.')
    except Exception:
        return None
    return host or None


def query_with_domains(query: str, domains: list[str]) -> str:
    clean = ' '.join(str(query or '').split())
    domains = [domain for domain in (normalize_domain(item) for item in domains) if domain]
    if not domains or 'site:' in clean.lower():
        return clean
    if len(domains) == 1:
        return f'{clean} site:{domains[0]}'.strip()
    domain_clause = '(' + ' OR '.join(f'site:{domain}' for domain in domains) + ')'
    return f'{clean} {domain_clause}'.strip()


def freshness_param(pack: dict[str, Any]) -> str | None:
    date_after = pack.get('date_after')
    date_before = pack.get('date_before')
    if date_after and date_before:
        return f'{date_after}to{date_before}'
    freshness = pack.get('freshness')
    if freshness is None:
        return None
    return FRESHNESS_MAP.get(str(freshness), str(freshness))


def build_request_params(pack: dict[str, Any], *, endpoint_type: str) -> dict[str, Any]:
    cfg = ENDPOINTS[endpoint_type]
    requested_count = pack.get('max_results') or pack.get('count') or 10
    try:
        count = int(requested_count)
    except Exception:
        count = 10
    count = max(1, min(count, int(cfg['max_count'])))
    try:
        offset = int(pack.get('offset') or 0)
    except Exception:
        offset = 0
    offset = max(0, min(offset, 9))
    allowed_domains = pack.get('allowed_domains') if isinstance(pack.get('allowed_domains'), list) else []
    params: dict[str, Any] = {
        'q': query_with_domains(str(pack.get('query') or ''), [str(item) for item in allowed_domains]),
        'count': count,
        'offset': offset,
        'safesearch': pack.get('safesearch') or cfg['default_safesearch'],
        'extra_snippets': 'true' if pack.get('extra_snippets', False) else 'false',
    }
    fresh = freshness_param(pack)
    if fresh:
        params['freshness'] = fresh
    for key in ('country', 'search_lang', 'ui_lang', 'goggles', 'spellcheck', 'include_fetch_metadata', 'operators'):
        if pack.get(key):
            params[key] = pack[key]
    return params


def sanitized_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if key.lower() not in {'x-subscription-token', 'api_key', 'apikey', 'token'}}


def quota_state_from_headers(headers: dict[str, Any], *, status_code: int | None = None) -> dict[str, Any]:
    lower = {str(key).lower(): str(value) for key, value in headers.items()}
    return {
        'status_code': status_code,
        'retry_after_sec': lower.get('retry-after'),
        'x_ratelimit_limit': lower.get('x-ratelimit-limit'),
        'x_ratelimit_remaining': lower.get('x-ratelimit-remaining'),
        'x_ratelimit_reset': lower.get('x-ratelimit-reset'),
    }


def resolve_exec_secret(ref: dict[str, Any], config: dict[str, Any]) -> str | None:
    if ref.get('source') != 'exec' or not ref.get('provider') or not ref.get('id'):
        return None
    provider = ((config.get('secrets') or {}).get('providers') or {}).get(str(ref.get('provider')))
    if not isinstance(provider, dict) or provider.get('source') != 'exec' or not provider.get('command'):
        return None
    try:
        proc = subprocess.run(
            [str(provider['command'])],
            input=json.dumps({'ids': [ref['id']]}),
            capture_output=True,
            text=True,
            timeout=max(1, int(provider.get('timeoutMs') or 5000) / 1000),
        )
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        return None
    value = ((payload.get('values') or {}).get(str(ref.get('id'))))
    return str(value) if value else None


def read_api_key(env_name: str = 'BRAVE_SEARCH_API_KEY', *, config_path: Path = OPENCLAW_CONFIG) -> str | None:
    for name in (env_name, 'BRAVE_API_KEY'):
        value = os.environ.get(name)
        if value:
            return value
    config = load_json(config_path, {}) or {}
    try:
        ref = config['plugins']['entries']['brave']['config']['webSearch']['apiKey']
    except Exception:
        ref = None
    if isinstance(ref, dict):
        return resolve_exec_secret(ref, config)
    return None


def execute_request(params: dict[str, Any], *, endpoint_type: str, api_key: str, timeout: int = 20) -> tuple[str, int | None, dict[str, Any], dict[str, Any], str | None]:
    cfg = ENDPOINTS[endpoint_type]
    url = BRAVE_API_BASE + str(cfg['path']) + '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={'Accept': 'application/json', 'X-Subscription-Token': api_key})
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


def result_refs_from_response(payload: dict[str, Any], *, endpoint_type: str) -> list[dict[str, Any]]:
    cfg = ENDPOINTS[endpoint_type]
    container = payload.get(cfg['result_container']) if isinstance(payload, dict) else None
    results = container.get('results') if isinstance(container, dict) else []
    refs: list[dict[str, Any]] = []
    for item in results if isinstance(results, list) else []:
        if not isinstance(item, dict) or not item.get('url'):
            continue
        url = str(item.get('url'))
        refs.append({
            'result_id': stable_id('brave-result', endpoint_type, url, item.get('age') or item.get('page_age')),
            'url': url,
            'domain': domain_from_url(url),
            'page_age': item.get('page_age'),
            'page_fetched': item.get('page_fetched'),
            'published_at_hint': item.get('page_age'),
            'source_name': (item.get('profile') or {}).get('name') if isinstance(item.get('profile'), dict) else item.get('source'),
            'source_url': (item.get('profile') or {}).get('url') if isinstance(item.get('profile'), dict) else None,
            'breaking': item.get('breaking') if endpoint_type == 'news' else None,
            'metadata_only': True,
        })
    return refs


def application_error_code(payload: dict[str, Any], fallback: str | None) -> str | None:
    for key in ('code', 'error_code', 'type'):
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, str) and value:
            return value
    errors = payload.get('errors') if isinstance(payload, dict) else None
    if isinstance(errors, list):
        for item in errors:
            if isinstance(item, dict):
                value = item.get('code') or item.get('type')
                if isinstance(value, str) and value:
                    return value
    return fallback


def classify_error(status_code: int | None, app_code: str | None) -> dict[str, Any]:
    if app_code == 'missing_api_key':
        return {'error_class': 'missing_credentials', 'retryable': False}
    if app_code in {'TimeoutError', 'URLError', 'ConnectionError', 'OSError'}:
        return {'error_class': 'network_error', 'retryable': True}
    if status_code in {402, 429} or app_code in {'QUOTA_LIMITED', 'RATE_LIMITED', 'USAGE_LIMIT_EXCEEDED'}:
        return {'error_class': 'throttle_or_quota', 'retryable': True}
    if status_code == 422 or app_code in {'SUBSCRIPTION_TOKEN_INVALID', 'SUBSCRIPTION_NOT_FOUND', 'RESOURCE_NOT_ALLOWED', 'OPTION_NOT_IN_PLAN', 'INVALID_URL'}:
        return {'error_class': 'non_retryable_validation_or_auth', 'retryable': False}
    if status_code == 404:
        return {'error_class': 'hard_miss', 'retryable': False}
    if status_code and status_code >= 500:
        return {'error_class': 'server_error', 'retryable': True}
    if app_code:
        return {'error_class': 'application_error', 'retryable': False}
    return {'error_class': None, 'retryable': None}


def watermark_key(pack: dict[str, Any], result_refs: list[dict[str, Any]], *, endpoint_type: str) -> str:
    lane = str(pack.get('lane') or 'news_policy_narrative')
    domains = sorted({ref.get('domain') for ref in result_refs if ref.get('domain')})
    if not domains and isinstance(pack.get('allowed_domains'), list):
        domains = sorted({domain for domain in (normalize_domain(item) for item in pack['allowed_domains']) if domain})
    entity = ','.join(str(item) for item in pack.get('required_entities', [])[:3]) if isinstance(pack.get('required_entities'), list) else ''
    return ':'.join(part for part in [lane, endpoint_type, entity or 'general', ','.join(domains) or 'unknown-domain'] if part)


def fetch_record_from_response(
    pack: dict[str, Any],
    *,
    endpoint_type: str,
    params: dict[str, Any],
    status: str,
    status_code: int | None,
    headers: dict[str, Any],
    payload: dict[str, Any],
    error_code: str | None,
    fetched_at: str | None = None,
    dry_run: bool = False,
    query_registry_should_skip: bool = False,
) -> dict[str, Any]:
    cfg = ENDPOINTS[endpoint_type]
    fetched = fetched_at or now_iso()
    result_refs = [] if dry_run else result_refs_from_response(payload, endpoint_type=endpoint_type)
    record_status = 'dry_run' if dry_run else status
    request_params = sanitized_params(params)
    app_code = application_error_code(payload, error_code)
    error_meta = classify_error(status_code, app_code)
    record = {
        'contract': 'source-fetch-record-v1',
        'fetch_id': stable_id('fetch', cfg['endpoint'], canonical_hash(request_params), fetched, record_status),
        'pack_id': pack.get('pack_id'),
        'source_id': cfg['source_id'],
        'lane': pack.get('lane') or 'news_policy_narrative',
        'endpoint': cfg['endpoint'],
        'request_params': request_params,
        'fetched_at': fetched,
        'status': record_status,
        'quota_state': quota_state_from_headers(headers, status_code=status_code),
        'result_count': len(result_refs),
        'watermark_key': watermark_key(pack, result_refs, endpoint_type=endpoint_type),
        'error_code': error_code,
        'application_error_code': app_code,
        'error_class': error_meta['error_class'],
        'retryable': error_meta['retryable'],
        'query_registry_should_skip': query_registry_should_skip,
        'result_refs': result_refs,
        'raw_response_persisted': False,
        'raw_snippets_persisted': False,
        'metadata_only': True,
        'sidecar_only': False,
        'no_execution': True,
    }
    if dry_run:
        record['dry_run'] = True
    return record


def fetch_from_pack(
    pack: dict[str, Any],
    *,
    endpoint_type: str,
    api_key: str | None = None,
    dry_run: bool = False,
    registry_path: Path = QUERY_REGISTRY,
    timeout: int = 20,
) -> dict[str, Any]:
    params = build_request_params(pack, endpoint_type=endpoint_type)
    recent = load_query_registry(registry_path) if registry_path.exists() else []
    skip = should_skip_query(pack, recent)
    if dry_run:
        return fetch_record_from_response(pack, endpoint_type=endpoint_type, params=params, status='dry_run', status_code=None, headers={}, payload={}, error_code=None, dry_run=True, query_registry_should_skip=skip)
    key = api_key or read_api_key()
    if not key:
        return fetch_record_from_response(pack, endpoint_type=endpoint_type, params=params, status='failed', status_code=None, headers={}, payload={}, error_code='missing_api_key', query_registry_should_skip=skip)
    status, status_code, headers, payload, error_code = execute_request(params, endpoint_type=endpoint_type, api_key=key, timeout=timeout)
    return fetch_record_from_response(pack, endpoint_type=endpoint_type, params=params, status=status, status_code=status_code, headers=headers, payload=payload, error_code=error_code, query_registry_should_skip=skip)


def default_out(endpoint_type: str) -> Path:
    return STATE / f'brave-{endpoint_type}-search-results.jsonl'


def main_for_endpoint(endpoint_type: str, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--pack', required=True)
    parser.add_argument('--out', default=str(default_out(endpoint_type)))
    parser.add_argument('--registry', default=str(QUERY_REGISTRY))
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--timeout', type=int, default=20)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_state_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    pack = load_json(Path(args.pack), {}) or {}
    if not isinstance(pack, dict) or not pack.get('query'):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['invalid_query_pack']}, ensure_ascii=False))
        return 2
    record = fetch_from_pack(pack, endpoint_type=endpoint_type, dry_run=args.dry_run, registry_path=Path(args.registry), timeout=args.timeout)
    existing = [] if not out.exists() else [json.loads(line) for line in out.read_text(encoding='utf-8', errors='replace').splitlines() if line.strip()]
    existing.append(record)
    write_jsonl(out, existing)
    print(json.dumps({'status': record['status'], 'endpoint': record['endpoint'], 'result_count': record['result_count'], 'out': str(out), 'query_registry_should_skip': record['query_registry_should_skip']}, ensure_ascii=False))
    return 0 if record['status'] in {'ok', 'partial', 'dry_run'} else 1
