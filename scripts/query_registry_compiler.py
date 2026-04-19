#!/usr/bin/env python3
"""Shadow query registry for source-ingestion repetition control."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from atomic_io import atomic_write_json

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
QUERY_REGISTRY = STATE / 'query-registry.jsonl'
CONTRACT = 'query-registry-v1-shadow'
QUERY_SCHEMA_VERSION = 1
NORMALIZATION_PROFILE_VERSION = 'query-normalization-v1'
SITE_RE = re.compile(r'\bsite:([^\s]+)', re.IGNORECASE)
URL_RE = re.compile(r'https?://[^\s)>"]+')
LOW_YIELD_COOLDOWN_HOURS = 6
STALE_REPEAT_COOLDOWN_HOURS = 12
FAILED_COOLDOWN_HOURS = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(part or '') for part in parts)
    return f'{prefix}:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]


def normalize_query(query: Any) -> str:
    return ' '.join(str(query or '').lower().strip().split())


def domain_from_value(value: Any) -> str | None:
    text = str(value or '').strip()
    if not text:
        return None
    if '://' not in text and '.' in text and '/' not in text:
        return text.lower().removeprefix('www.')
    for match in URL_RE.findall(text):
        host = urlparse(match).netloc.lower().removeprefix('www.')
        if host:
            return host
    try:
        host = urlparse(text).netloc.lower().removeprefix('www.')
    except Exception:
        return None
    return host or None


def domains_from_pack(pack: dict[str, Any]) -> list[str]:
    domains: set[str] = set()
    query = str(pack.get('query') or '')
    for match in SITE_RE.findall(query):
        domain = domain_from_value(match.rstrip('/'))
        if domain:
            domains.add(domain)
    allowed = pack.get('allowed_domains')
    if isinstance(allowed, list):
        for item in allowed:
            domain = domain_from_value(item)
            if domain:
                domains.add(domain)
    return sorted(domains)


def query_hash(pack: dict[str, Any]) -> str:
    identity = {
        'query_schema_version': QUERY_SCHEMA_VERSION,
        'normalization_profile_version': NORMALIZATION_PROFILE_VERSION,
        'lane': pack.get('lane'),
        'purpose': pack.get('purpose'),
        'query': normalize_query(pack.get('query')),
        'freshness': pack.get('freshness'),
        'date_after': pack.get('date_after'),
        'date_before': pack.get('date_before'),
        'domains': domains_from_pack(pack),
    }
    return canonical_hash(identity)


def rate_limit_state(fetch_records: list[dict[str, Any]], fetched_at: datetime) -> dict[str, Any]:
    state: dict[str, Any] = {
        'retry_after_sec': None,
        'x_ratelimit_remaining': None,
        'x_ratelimit_reset': None,
        'next_eligible_at': None,
        'last_error_class': None,
        'is_idempotent': True,
    }
    for record in fetch_records:
        headers = record.get('headers') if isinstance(record.get('headers'), dict) else {}
        retry_after = record.get('retry_after_sec') or headers.get('retry-after') or headers.get('Retry-After')
        remaining = record.get('x_ratelimit_remaining') or headers.get('x-ratelimit-remaining') or headers.get('X-RateLimit-Remaining')
        reset = record.get('x_ratelimit_reset') or headers.get('x-ratelimit-reset') or headers.get('X-RateLimit-Reset')
        error_class = record.get('error_class') or record.get('error_code')
        if retry_after is not None and state['retry_after_sec'] is None:
            try:
                state['retry_after_sec'] = int(float(retry_after))
                state['next_eligible_at'] = iso(fetched_at + timedelta(seconds=state['retry_after_sec']))
            except Exception:
                pass
        if remaining is not None and state['x_ratelimit_remaining'] is None:
            try:
                state['x_ratelimit_remaining'] = int(float(remaining))
            except Exception:
                state['x_ratelimit_remaining'] = str(remaining)
        if reset is not None and state['x_ratelimit_reset'] is None:
            state['x_ratelimit_reset'] = str(reset)
        if error_class and state['last_error_class'] is None:
            state['last_error_class'] = str(error_class)
    return state


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp')
    tmp.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows), encoding='utf-8')
    tmp.replace(path)


def result_urls(fetch_records: list[dict[str, Any]]) -> list[str]:
    urls: set[str] = set()
    for record in fetch_records:
        for key in ('result_urls', 'urls'):
            values = record.get(key)
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str) and value.startswith(('http://', 'https://')):
                        urls.add(value)
        raw_results = record.get('results')
        if isinstance(raw_results, list):
            for item in raw_results:
                if isinstance(item, dict) and isinstance(item.get('url'), str):
                    urls.add(item['url'])
    return sorted(urls)


def domains_from_urls(urls: list[str]) -> list[str]:
    domains = {domain_from_value(url) for url in urls}
    return sorted(domain for domain in domains if domain)


def status_from_fetches(fetch_records: list[dict[str, Any]]) -> str:
    statuses = {str(record.get('status') or '').lower() for record in fetch_records if isinstance(record, dict)}
    if 'rate_limited' in statuses:
        return 'rate_limited'
    if 'failed' in statuses:
        return 'failed'
    if 'partial' in statuses:
        return 'partial'
    if 'ok' in statuses:
        return 'ok'
    return 'unknown'


def total_result_count(fetch_records: list[dict[str, Any]]) -> int:
    total = 0
    for record in fetch_records:
        try:
            total += int(record.get('result_count') or 0)
        except Exception:
            continue
    return total


def infer_outcome(status: str, *, result_count: int, novel_claim_count: int, fresh_result_ratio: float) -> str:
    if status in {'failed', 'rate_limited'}:
        return 'failed'
    if novel_claim_count > 0 and fresh_result_ratio >= 0.2:
        return 'high_yield'
    if result_count == 0:
        return 'low_yield'
    if novel_claim_count == 0 and fresh_result_ratio < 0.2:
        return 'stale_repeat'
    return 'low_yield'


def cooldown_for_outcome(outcome: str, fetched_at: datetime) -> datetime | None:
    if outcome == 'stale_repeat':
        return fetched_at + timedelta(hours=STALE_REPEAT_COOLDOWN_HOURS)
    if outcome == 'low_yield':
        return fetched_at + timedelta(hours=LOW_YIELD_COOLDOWN_HOURS)
    if outcome == 'failed':
        return fetched_at + timedelta(hours=FAILED_COOLDOWN_HOURS)
    return None


def build_query_run_record(
    pack: dict[str, Any],
    fetch_records: list[dict[str, Any]] | None = None,
    *,
    novel_claim_count: int = 0,
    repeated_claim_count: int = 0,
    fresh_result_ratio: float = 0.0,
    fetched_at: str | None = None,
    quota_cost: float | None = None,
) -> dict[str, Any]:
    fetch_records = fetch_records or []
    fetched_dt = parse_ts(fetched_at) or datetime.now(timezone.utc)
    urls = result_urls(fetch_records)
    status = status_from_fetches(fetch_records)
    result_count = total_result_count(fetch_records)
    outcome = infer_outcome(status, result_count=result_count, novel_claim_count=novel_claim_count, fresh_result_ratio=fresh_result_ratio)
    cooldown_until = cooldown_for_outcome(outcome, fetched_dt)
    qhash = query_hash(pack)
    rate_limit = rate_limit_state(fetch_records, fetched_dt)
    next_eligible_at = rate_limit.get('next_eligible_at') or iso(cooldown_until)
    return {
        'contract': 'query-run-record-v1',
        'record_id': stable_id('query-run', qhash, iso(fetched_dt), outcome),
        'query_schema_version': QUERY_SCHEMA_VERSION,
        'normalization_profile_version': NORMALIZATION_PROFILE_VERSION,
        'query_fingerprint': qhash,
        'query_hash': qhash,
        'pack_id': pack.get('pack_id') or stable_id('query-pack', qhash),
        'lane': pack.get('lane'),
        'purpose': pack.get('purpose'),
        'query': normalize_query(pack.get('query')),
        'source_scope': domains_from_pack(pack),
        'data_source_restrictions': domains_from_pack(pack),
        'freshness_policy': {
            'freshness': pack.get('freshness'),
            'date_after': pack.get('date_after'),
            'date_before': pack.get('date_before'),
        },
        'domains_seen': domains_from_urls(urls) or domains_from_pack(pack),
        'result_urls': urls,
        'fetched_at': iso(fetched_dt),
        'status': status,
        'result_count': result_count,
        'novel_claim_count': int(novel_claim_count),
        'repeated_claim_count': int(repeated_claim_count),
        'fresh_result_ratio': float(fresh_result_ratio),
        'quota_cost': quota_cost,
        'outcome': outcome,
        'cooldown_until': iso(cooldown_until),
        'retry_after_sec': rate_limit.get('retry_after_sec'),
        'x_ratelimit_remaining': rate_limit.get('x_ratelimit_remaining'),
        'x_ratelimit_reset': rate_limit.get('x_ratelimit_reset'),
        'next_eligible_at': next_eligible_at,
        'last_error_class': rate_limit.get('last_error_class'),
        'is_idempotent': rate_limit.get('is_idempotent'),
        'retention_class': 'metadata_only',
        'restricted_payload_present': False,
        'shadow_only': True,
        'no_execution': True,
    }


def active_cooldown(record: dict[str, Any], now: datetime) -> bool:
    cooldown = parse_ts(record.get('cooldown_until'))
    return bool(cooldown and cooldown > now)


def matching_records(pack: dict[str, Any], recent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    qhash = query_hash(pack)
    lane = pack.get('lane')
    pack_domains = set(domains_from_pack(pack))
    matches = []
    for record in recent:
        if record.get('query_hash') == qhash:
            matches.append(record)
            continue
        if lane and record.get('lane') == lane and pack_domains:
            record_domains = set(record.get('domains_seen') or [])
            if pack_domains & record_domains and record.get('outcome') in {'low_yield', 'stale_repeat'}:
                matches.append(record)
    return sorted(matches, key=lambda item: str(item.get('fetched_at') or ''))


def should_skip_query(pack: dict[str, Any], recent: list[dict[str, Any]], *, now: str | None = None) -> bool:
    now_dt = parse_ts(now) or datetime.now(timezone.utc)
    matches = matching_records(pack, recent)
    if not matches:
        return False
    if any(active_cooldown(record, now_dt) for record in matches):
        return True
    latest = matches[-1]
    return (
        latest.get('outcome') in {'stale_repeat', 'low_yield'}
        and float(latest.get('fresh_result_ratio') or 0.0) < 0.2
        and int(latest.get('novel_claim_count') or 0) == 0
    )


def registry_report(rows: list[dict[str, Any]], *, generated_at: str | None = None) -> dict[str, Any]:
    outcomes: dict[str, int] = {}
    for row in rows:
        outcome = str(row.get('outcome') or 'unknown')
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    return {
        'generated_at': generated_at or now_iso(),
        'status': 'pass',
        'contract': CONTRACT,
        'record_count': len(rows),
        'outcomes': outcomes,
        'shadow_only': True,
        'no_execution': True,
    }


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--registry', default=str(QUERY_REGISTRY))
    parser.add_argument('--pack', default=None)
    parser.add_argument('--fetch-records', default=None)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--report', default=None)
    args = parser.parse_args(argv)

    registry_path = Path(args.registry)
    if not safe_state_path(registry_path):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_registry_path']}, ensure_ascii=False))
        return 2

    rows = load_jsonl(registry_path)
    pack = load_json(Path(args.pack), {}) if args.pack else None
    fetch_records = load_json(Path(args.fetch_records), []) if args.fetch_records else []
    if isinstance(fetch_records, dict):
        fetch_records = [fetch_records]
    if fetch_records is None or not isinstance(fetch_records, list):
        fetch_records = []

    if isinstance(pack, dict) and pack:
        skip = should_skip_query(pack, rows)
        if not args.check_only:
            rows.append(build_query_run_record(pack, [r for r in fetch_records if isinstance(r, dict)]))
            write_jsonl(registry_path, rows)
        payload = {'status': 'pass', 'should_skip': skip, 'record_count': len(rows), 'registry': str(registry_path)}
    else:
        payload = registry_report(rows)

    if args.report:
        report_path = Path(args.report)
        if not safe_state_path(report_path):
            print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_report_path']}, ensure_ascii=False))
            return 2
        atomic_write_json(report_path, registry_report(rows))
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
