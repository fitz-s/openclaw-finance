#!/usr/bin/env python3
"""Compile shadow Source Health from atoms, fetch records, and quota signals."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
SOURCE_ATOMS = STATE / 'source-atoms' / 'latest.jsonl'
BRAVE_WEB = STATE / 'brave-web-search-results.jsonl'
BRAVE_NEWS = STATE / 'brave-news-search-results.jsonl'
BRAVE_CONTEXT = STATE / 'brave-llm-context-results.jsonl'
BRAVE_ANSWERS = STATE / 'brave-answer-sidecars' / 'latest.jsonl'
QUERY_REGISTRY = STATE / 'query-registry.jsonl'
REDUCER_REPORT = STATE / 'finance-worker-reducer-report.json'
BRAVE_AUDIT = FINANCE / 'docs' / 'openclaw-runtime' / 'brave-api-capability-audit.json'
OUT = STATE / 'source-health.json'
HISTORY = STATE / 'source-health-history.jsonl'
CONTRACT = 'source-health-v2-shadow'
DEFAULT_FRESHNESS_BUDGET_SECONDS = 24 * 60 * 60
SOURCE_IDS_BY_ENDPOINT = {
    'brave/web/search': 'source:brave_web',
    'brave/news/search': 'source:brave_news',
    'brave/llm/context': 'source:brave_llm_context',
    'brave/answers/chat_completions': 'source:brave_answers',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')


def freshness_status(age_seconds: float | None, budget_seconds: int | None) -> str:
    if age_seconds is None or not budget_seconds:
        return 'unknown'
    if age_seconds <= budget_seconds:
        return 'fresh'
    if age_seconds <= budget_seconds * 2:
        return 'aging'
    return 'stale'


def rights_status(compliance: Any, redistribution: Any) -> str:
    compliance = str(compliance or 'unknown')
    redistribution = str(redistribution or 'unknown')
    if compliance in {'public', 'official', 'allowed'} and redistribution in {'raw_ok', 'ok'}:
        return 'ok'
    if compliance == 'unknown' or redistribution == 'unknown':
        return 'unknown'
    return 'restricted'


def empty_row(source_id: str, evaluated_at: str) -> dict[str, Any]:
    return {
        'source_id': source_id,
        'evaluated_at': evaluated_at,
        'freshness_status': 'unknown',
        'freshness_age_seconds': None,
        'latency_status': 'unknown',
        'observed_latency_seconds': None,
        'schema_status': 'unknown',
        'validation_status': 'unknown',
        'rights_status': 'unknown',
        'coverage_status': 'unknown',
        'quota_status': 'unknown',
        'rate_limit_status': 'unknown',
        'last_seen_at': None,
        'last_success_at': None,
        'last_error_at': None,
        'last_quota_error': None,
        'retry_after_sec': None,
        'x_ratelimit_remaining': None,
        'x_ratelimit_reset': None,
        'success_count': 0,
        'failure_count': 0,
        'timeout_count': 0,
        'rate_limited_count': 0,
        'freshness_lag_seconds': None,
        'quota_remaining': None,
        'quota_reset_at': None,
        'retry_after_seconds': None,
        'breaker_state': 'unknown',
        'degraded_state': None,
        'health_score': None,
        'breach_reasons': [],
        'metric_refs': [],
        'source_refs': [],
        'no_execution': True,
    }


def finalize_row(row: dict[str, Any]) -> dict[str, Any]:
    row['breach_reasons'] = sorted(set(str(x) for x in row.get('breach_reasons', []) if x))
    row['metric_refs'] = sorted(set(str(x) for x in row.get('metric_refs', []) if x))[:20]
    row['source_refs'] = sorted(set(str(x) for x in row.get('source_refs', []) if x))[:20]
    penalty = 0.0
    penalty += min(0.4, 0.15 * int(row.get('failure_count') or 0))
    penalty += min(0.4, 0.2 * int(row.get('rate_limited_count') or 0))
    if row.get('freshness_status') in {'stale', 'unknown'}:
        penalty += 0.25
    if row.get('coverage_status') == 'unavailable':
        penalty += 0.25
    row['health_score'] = max(0.0, round(1.0 - penalty, 3))
    if row['breach_reasons']:
        row['problem_details'] = {
            'type': 'source-health-degradation',
            'title': 'Source health degraded',
            'detail': '; '.join(row['breach_reasons']),
            'instance': row.get('source_id'),
            'retry_after_sec': row.get('retry_after_seconds') or row.get('retry_after_sec'),
        }
    health_input = dict(row)
    health_input.pop('health_hash', None)
    row['health_hash'] = canonical_hash(health_input)
    return row


def merge_atom(rows: dict[str, dict[str, Any]], atom: dict[str, Any], *, evaluated_at: datetime) -> None:
    source_id = str(atom.get('source_id') or 'source:unknown')
    row = rows.setdefault(source_id, empty_row(source_id, evaluated_at.isoformat().replace('+00:00', 'Z')))
    observed = parse_ts(atom.get('ingested_at')) or parse_ts(atom.get('event_time')) or parse_ts(atom.get('published_at'))
    if observed:
        age = max(0.0, (evaluated_at - observed).total_seconds())
        budget = int(atom.get('freshness_budget_seconds') or DEFAULT_FRESHNESS_BUDGET_SECONDS)
        row['freshness_age_seconds'] = int(age) if row.get('freshness_age_seconds') is None else min(int(age), int(row['freshness_age_seconds']))
        row['freshness_lag_seconds'] = row['freshness_age_seconds']
        row['freshness_status'] = freshness_status(row['freshness_age_seconds'], budget)
        row['last_seen_at'] = max(filter(None, [row.get('last_seen_at'), observed.isoformat().replace('+00:00', 'Z')]))
    row['rights_status'] = rights_status(atom.get('compliance_class'), atom.get('redistribution_policy'))
    row['coverage_status'] = 'ok'
    row['validation_status'] = 'pass'
    row['schema_status'] = 'ok'
    if row['freshness_status'] in {'stale', 'unknown'}:
        row['breach_reasons'].append(f"freshness_{row['freshness_status']}")
    if row['rights_status'] in {'restricted', 'unknown'}:
        row['breach_reasons'].append(f"rights_{row['rights_status']}")
    if atom.get('atom_id'):
        row['source_refs'].append(str(atom['atom_id']))


def fetch_records_from_paths(paths: list[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        for record in load_jsonl(path):
            record['_source_path'] = str(path)
            rows.append(record)
    return rows


def merge_fetch_record(rows: dict[str, dict[str, Any]], record: dict[str, Any], *, evaluated_at: datetime) -> None:
    source_id = str(record.get('source_id') or SOURCE_IDS_BY_ENDPOINT.get(str(record.get('endpoint')), 'source:unknown_fetch'))
    row = rows.setdefault(source_id, empty_row(source_id, evaluated_at.isoformat().replace('+00:00', 'Z')))
    fetched = parse_ts(record.get('fetched_at'))
    if fetched:
        age = max(0.0, (evaluated_at - fetched).total_seconds())
        row['freshness_age_seconds'] = int(age) if row.get('freshness_age_seconds') is None else min(int(age), int(row['freshness_age_seconds']))
        row['last_seen_at'] = max(filter(None, [row.get('last_seen_at'), fetched.isoformat().replace('+00:00', 'Z')]))
    status = str(record.get('status') or 'unknown')
    quota = record.get('quota_state') if isinstance(record.get('quota_state'), dict) else {}
    status_code = quota.get('status_code')
    if status in {'ok', 'partial'}:
        row['success_count'] += 1
        row['coverage_status'] = 'ok' if status == 'ok' else 'partial'
        row['quota_status'] = 'ok'
        row['rate_limit_status'] = 'ok'
        row['breaker_state'] = 'closed'
        if fetched:
            row['last_success_at'] = fetched.isoformat().replace('+00:00', 'Z')
    elif status == 'dry_run':
        row['coverage_status'] = 'unknown'
        row['quota_status'] = 'unknown'
        row['rate_limit_status'] = 'unknown'
        row['breaker_state'] = 'unknown'
        row['freshness_age_seconds'] = None
        row['freshness_lag_seconds'] = None
        row['freshness_status'] = 'unknown'
        row['breach_reasons'].append('dry_run_no_live_fetch')
    elif status == 'rate_limited' or status_code in {402, 429}:
        row['rate_limited_count'] += 1
        row['coverage_status'] = 'unavailable'
        row['quota_status'] = 'degraded'
        row['rate_limit_status'] = 'limited'
        row['breaker_state'] = 'open'
        row['degraded_state'] = 'quota_limited'
        row['source_lane_unavailable_reason'] = 'quota_limited'
        row['last_error_at'] = record.get('fetched_at')
        row['last_quota_error'] = record.get('application_error_code') or record.get('error_code') or str(status_code or 'rate_limited')
        row['breach_reasons'].append('quota_or_rate_limited')
    elif status == 'failed':
        row['failure_count'] += 1
        row['coverage_status'] = 'unavailable'
        row['quota_status'] = 'unknown'
        row['rate_limit_status'] = 'unknown'
        row['breaker_state'] = 'open'
        error_class = str(record.get('error_class') or '')
        error_code = str(record.get('application_error_code') or record.get('error_code') or '')
        if error_class == 'missing_credentials' or error_code == 'missing_api_key':
            row['degraded_state'] = 'missing_credentials'
            row['breach_reasons'].append('missing_api_key')
        elif error_class == 'network_error':
            row['degraded_state'] = 'network_error'
            row['breach_reasons'].append('network_fetch_failed')
        else:
            row['degraded_state'] = 'fetch_failed'
            row['breach_reasons'].append('fetch_failed')
        row['last_error_at'] = record.get('fetched_at')
        if str(record.get('error_code') or '').lower().find('timeout') >= 0:
            row['timeout_count'] += 1
        row['source_lane_unavailable_reason'] = row['degraded_state']
    row['retry_after_sec'] = quota.get('retry_after_sec') or row.get('retry_after_sec')
    row['x_ratelimit_remaining'] = quota.get('x_ratelimit_remaining') or row.get('x_ratelimit_remaining')
    row['x_ratelimit_reset'] = quota.get('x_ratelimit_reset') or row.get('x_ratelimit_reset')
    row['retry_after_seconds'] = row.get('retry_after_sec')
    row['quota_remaining'] = row.get('x_ratelimit_remaining')
    row['quota_reset_at'] = row.get('x_ratelimit_reset')
    if status != 'dry_run':
        row['freshness_status'] = freshness_status(row.get('freshness_age_seconds'), DEFAULT_FRESHNESS_BUDGET_SECONDS)
        row['freshness_lag_seconds'] = row.get('freshness_age_seconds')
    row['validation_status'] = 'warn' if row.get('breach_reasons') else 'pass'
    row['schema_status'] = 'ok'
    row['rights_status'] = 'restricted' if source_id.startswith('source:brave') else row.get('rights_status') or 'unknown'
    row['metric_refs'].append(str(record.get('_source_path') or 'fetch_record'))
    if record.get('fetch_id') or record.get('answer_id'):
        row['source_refs'].append(str(record.get('fetch_id') or record.get('answer_id')))


def merge_brave_audit(rows: dict[str, dict[str, Any]], audit: dict[str, Any], *, evaluated_at: datetime) -> None:
    failures = audit.get('quota_failures') if isinstance(audit.get('quota_failures'), list) else []
    if not failures:
        return
    source_id = 'source:brave_llm_context'
    row = rows.setdefault(source_id, empty_row(source_id, evaluated_at.isoformat().replace('+00:00', 'Z')))
    row['quota_status'] = 'degraded'
    row['rate_limit_status'] = 'limited'
    row['coverage_status'] = 'unavailable'
    row['validation_status'] = 'warn'
    row['rate_limited_count'] += len(failures)
    row['breaker_state'] = 'open'
    row['degraded_state'] = 'quota_limited'
    row['last_quota_error'] = 'USAGE_LIMIT_EXCEEDED'
    row['breach_reasons'].append('brave_audit_usage_limit_exceeded')
    row['metric_refs'].append(str(BRAVE_AUDIT))
    if failures[-1].get('line_time'):
        row['last_error_at'] = str(failures[-1]['line_time'])


def merge_reducer_report(rows: dict[str, dict[str, Any]], reducer: dict[str, Any], *, evaluated_at: datetime) -> None:
    if not reducer:
        return
    row = rows.setdefault('source:finance_worker_reducer', empty_row('source:finance_worker_reducer', evaluated_at.isoformat().replace('+00:00', 'Z')))
    row['coverage_status'] = 'ok' if reducer.get('status') == 'pass' else 'partial'
    row['validation_status'] = 'pass' if reducer.get('status') == 'pass' else 'warn'
    row['schema_status'] = 'ok'
    row['rights_status'] = 'ok'
    row['quota_status'] = 'not_applicable'
    row['rate_limit_status'] = 'not_applicable'
    row['breaker_state'] = 'closed'
    row['degraded_state'] = None
    row['last_success_at'] = reducer.get('generated_at')
    row['last_seen_at'] = reducer.get('generated_at')
    row['metric_refs'].append(str(REDUCER_REPORT))
    if int(reducer.get('source_atom_count') or 0) == 0:
        row['breach_reasons'].append('no_source_atoms_in_reducer')


def report_status(rows: list[dict[str, Any]]) -> str:
    if any(row.get('quota_status') == 'degraded' or row.get('coverage_status') == 'unavailable' for row in rows):
        return 'degraded'
    if any(row.get('freshness_status') in {'stale', 'unknown'} or row.get('rights_status') in {'restricted', 'unknown'} for row in rows):
        return 'degraded'
    return 'pass'


def build_report(
    *,
    atoms: list[dict[str, Any]] | None = None,
    fetch_records: list[dict[str, Any]] | None = None,
    brave_audit: dict[str, Any] | None = None,
    reducer_report: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or now_iso()
    evaluated_at = parse_ts(generated) or datetime.now(timezone.utc)
    rows: dict[str, dict[str, Any]] = {}
    for atom in atoms or []:
        merge_atom(rows, atom, evaluated_at=evaluated_at)
    for record in fetch_records or []:
        merge_fetch_record(rows, record, evaluated_at=evaluated_at)
    merge_brave_audit(rows, brave_audit or {}, evaluated_at=evaluated_at)
    merge_reducer_report(rows, reducer_report or {}, evaluated_at=evaluated_at)
    finalized = [finalize_row(row) for row in rows.values()]
    finalized.sort(key=lambda item: item['source_id'])
    summary = {
        'freshness': {},
        'quota_degraded_count': sum(1 for row in finalized if row.get('quota_status') == 'degraded'),
        'rate_limited_count': sum(1 for row in finalized if row.get('rate_limit_status') == 'limited'),
        'unavailable_count': sum(1 for row in finalized if row.get('coverage_status') == 'unavailable'),
        'stale_or_unknown_count': sum(1 for row in finalized if row.get('freshness_status') in {'stale', 'unknown'}),
        'restricted_or_unknown_rights_count': sum(1 for row in finalized if row.get('rights_status') in {'restricted', 'unknown'}),
    }
    for row in finalized:
        status = str(row.get('freshness_status') or 'unknown')
        summary['freshness'][status] = summary['freshness'].get(status, 0) + 1
    stale_guard = {
        'status': 'active' if summary['quota_degraded_count'] or summary['rate_limited_count'] or summary['stale_or_unknown_count'] else 'clear',
        'reason': 'source access degraded or freshness unknown; downstream reports must disclose instead of silently recycling old narratives',
        'degraded_sources': [row['source_id'] for row in finalized if row.get('quota_status') == 'degraded' or row.get('coverage_status') == 'unavailable' or row.get('freshness_status') in {'stale', 'unknown'}],
        'source_lane_unavailable_reasons': {
            row['source_id']: row.get('source_lane_unavailable_reason') or row.get('degraded_state') or row.get('last_quota_error') or row.get('freshness_status')
            for row in finalized
            if row.get('quota_status') == 'degraded' or row.get('coverage_status') == 'unavailable' or row.get('freshness_status') in {'stale', 'unknown'}
        },
    }
    return {
        'generated_at': generated,
        'status': report_status(finalized),
        'registry_version': 'finance-source-registry-v2',
        'health_policy_version': CONTRACT,
        'source_count': len(finalized),
        'sources': finalized,
        'summary': summary,
        'stale_reuse_guard': stale_guard,
        'shadow_only': True,
        'no_execution': True,
        'health_hash': canonical_hash(finalized),
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
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--history', default=str(HISTORY))
    args = parser.parse_args(argv)
    out = Path(args.out)
    history = Path(args.history)
    if not safe_state_path(out) or not safe_state_path(history):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_state_path']}, ensure_ascii=False))
        return 2
    records = fetch_records_from_paths([BRAVE_WEB, BRAVE_NEWS, BRAVE_CONTEXT, BRAVE_ANSWERS])
    report = build_report(
        atoms=load_jsonl(SOURCE_ATOMS),
        fetch_records=records,
        brave_audit=load_json_safe(BRAVE_AUDIT, {}) or {},
        reducer_report=load_json_safe(REDUCER_REPORT, {}) or {},
    )
    atomic_write_json(out, report)
    append_jsonl(history, {'generated_at': report['generated_at'], 'status': report['status'], 'source_count': report['source_count'], 'health_hash': report['health_hash'], 'summary': report['summary']})
    print(json.dumps({'status': report['status'], 'source_count': report['source_count'], 'out': str(out), 'stale_reuse_guard': report['stale_reuse_guard']['status']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
