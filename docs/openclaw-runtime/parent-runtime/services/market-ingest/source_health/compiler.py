#!/usr/bin/env python3
"""Compile shadow SourceHealth records for market-ingest sources.

This is an audit surface only. It must not change wake, judgment, delivery,
or execution authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path('/Users/leofitz/.openclaw')
WORKSPACE = ROOT / 'workspace'
SERVICE = WORKSPACE / 'services' / 'market-ingest'
FINANCE_STATE = WORKSPACE / 'finance' / 'state'
STATE = SERVICE / 'state'
REGISTRY = SERVICE / 'config' / 'source-registry.json'
LIVE_EVIDENCE = STATE / 'live-evidence-records.jsonl'
OUT = STATE / 'source-health.json'
HISTORY = STATE / 'source-health-history.jsonl'
POLICY_VERSION = 'source-health-v1-shadow'
FINANCE_SOURCE_HEALTH = FINANCE_STATE / 'source-health.json'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception:
        return None


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


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + '\n')


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    for directory in [STATE, WORKSPACE / 'ops' / 'state']:
        try:
            path.resolve(strict=False).relative_to(directory.resolve(strict=False))
            return True
        except ValueError:
            continue
    return False


def registry_match_source_id(record: dict[str, Any], sources: list[dict[str, Any]]) -> str | None:
    facts = record.get('structured_facts') if isinstance(record.get('structured_facts'), dict) else {}
    source_text = ' '.join([
        str(facts.get('source') or ''),
        str(record.get('source_kind') or ''),
        str(record.get('raw_ref') or ''),
        str(record.get('source_quality', {}).get('source_domain') if isinstance(record.get('source_quality'), dict) else ''),
    ]).lower()
    if 'sec.gov' in source_text or 'sec_current_filing' in source_text or 'sec_filing' in source_text:
        return 'source:sec_edgar'
    if 'yfinance' in source_text or 'quote' in source_text or 'price' in source_text or 'broad_market' in source_text or 'option' in source_text:
        return 'source:yfinance'
    if 'ibkr' in source_text or 'portfolio' in source_text or 'flex' in source_text:
        return 'source:portfolio_flex'
    if 'reuters' in source_text:
        return 'source:reuters'
    if 'bloomberg' in source_text:
        return 'source:bloomberg'
    if 'prnewswire' in source_text or 'businesswire' in source_text or 'globenewswire' in source_text or 'investor relations' in source_text:
        return 'source:issuer_press_release'
    if 'mshale' in source_text or 'anonymous market forum' in source_text:
        return 'source:low_quality_blocked'
    if source_text.strip():
        return 'source:unknown_web'
    return None


def artifact_time(path: Path, *keys: str) -> str | None:
    payload = load_json(path, {}) or {}
    for key in keys:
        value = payload.get(key) if isinstance(payload, dict) else None
        if parse_dt(value):
            return value
    if path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace('+00:00', 'Z')
    return None


def observed_times_for_source(source_id: str, records: list[dict[str, Any]], sources: list[dict[str, Any]]) -> list[str]:
    times: list[str] = []
    for record in records:
        if registry_match_source_id(record, sources) != source_id:
            continue
        for key in ['ingested_at', 'detected_at', 'observed_at', 'published_at']:
            value = record.get(key)
            if parse_dt(value):
                times.append(str(value))
                break
    if source_id == 'source:yfinance':
        for path in [FINANCE_STATE / 'prices.json', FINANCE_STATE / 'broad-market-proxy.json', FINANCE_STATE / 'options-flow-proxy.json']:
            value = artifact_time(path, 'fetched_at', 'generated_at')
            if value:
                times.append(value)
    if source_id == 'source:portfolio_flex':
        for path in [FINANCE_STATE / 'portfolio-resolved.json', FINANCE_STATE / 'portfolio-option-risk.json']:
            value = artifact_time(path, 'resolved_at', 'generated_at')
            if value:
                times.append(value)
    if source_id == 'source:sec_edgar':
        for path in [FINANCE_STATE / 'sec-discovery.json', FINANCE_STATE / 'sec-filing-semantics.json']:
            value = artifact_time(path, 'generated_at')
            if value:
                times.append(value)
    return times


def newest_time(values: list[str]) -> str | None:
    parsed = [(parse_dt(value), value) for value in values]
    parsed = [(dt, value) for dt, value in parsed if dt is not None]
    if not parsed:
        return None
    return max(parsed, key=lambda item: item[0])[1]


def freshness_status(age: float | None, budget: int) -> str:
    if age is None:
        return 'unknown'
    if budget <= 0:
        return 'unknown'
    if age <= budget:
        return 'fresh'
    if age <= budget * 2:
        return 'aging'
    return 'stale'


def latency_status(age: float | None, expected: int) -> str:
    if age is None or expected <= 0:
        return 'unknown'
    if age <= expected:
        return 'ok'
    if age <= expected * 2:
        return 'degraded'
    return 'breached'


def rights_status(source: dict[str, Any]) -> str:
    compliance = str(source.get('compliance_class') or 'unknown')
    redistribution = str(source.get('redistribution_policy') or 'unknown')
    if compliance == 'blocked' or redistribution == 'blocked':
        return 'restricted'
    if compliance == 'unknown' or redistribution == 'unknown':
        return 'unknown'
    if compliance in {'restricted', 'licensed', 'internal_private'} or redistribution in {'summary_only', 'internal_only'}:
        return 'restricted'
    return 'ok'


def health_for_source(source: dict[str, Any], records: list[dict[str, Any]], sources: list[dict[str, Any]], as_of: datetime) -> dict[str, Any]:
    source_id = str(source.get('source_id') or 'source:unknown')
    times = observed_times_for_source(source_id, records, sources)
    last_seen = newest_time(times)
    last_seen_dt = parse_dt(last_seen)
    age = max(0.0, (as_of - last_seen_dt).total_seconds()) if last_seen_dt else None
    budget = int(source.get('freshness_budget_seconds') or 0)
    expected = int(source.get('expected_latency_seconds') or 0)
    fresh = freshness_status(age, budget)
    latency = latency_status(age, expected)
    source_refs = [str(LIVE_EVIDENCE)] if times else []
    if source_id == 'source:yfinance':
        source_refs.extend(str(p) for p in [FINANCE_STATE / 'prices.json', FINANCE_STATE / 'broad-market-proxy.json', FINANCE_STATE / 'options-flow-proxy.json'] if p.exists())
    elif source_id == 'source:portfolio_flex':
        source_refs.extend(str(p) for p in [FINANCE_STATE / 'portfolio-resolved.json', FINANCE_STATE / 'portfolio-option-risk.json'] if p.exists())
    elif source_id == 'source:sec_edgar':
        source_refs.extend(str(p) for p in [FINANCE_STATE / 'sec-discovery.json', FINANCE_STATE / 'sec-filing-semantics.json'] if p.exists())
    reasons: list[str] = []
    if fresh in {'stale', 'unknown'}:
        reasons.append(f'freshness:{fresh}')
    if latency == 'breached':
        reasons.append('latency:breached')
    rights = rights_status(source)
    if rights in {'restricted', 'unknown'}:
        reasons.append(f'rights:{rights}')
    health = {
        'source_id': source_id,
        'evaluated_at': as_of.isoformat().replace('+00:00', 'Z'),
        'freshness_status': fresh,
        'freshness_age_seconds': round(age, 2) if age is not None else None,
        'latency_status': latency,
        'observed_latency_seconds': round(age, 2) if age is not None else None,
        'schema_status': 'ok',
        'validation_status': 'pass' if source.get('promotion_policy') not in {'blocked'} else 'warn',
        'rights_status': rights,
        'coverage_status': 'ok' if source.get('coverage_universe') else 'unknown',
        'last_seen_at': last_seen,
        'last_success_at': last_seen if fresh in {'fresh', 'aging'} else None,
        'last_error_at': None,
        'breach_reasons': reasons,
        'metric_refs': [],
        'source_refs': sorted(set(source_refs)),
        'health_hash': 'sha256:pending',
        'no_execution': True,
    }
    hash_input = dict(health)
    hash_input['health_hash'] = 'sha256:pending'
    health['health_hash'] = canonical_hash(hash_input)
    return health


def compatible_finance_health_rows(finance_health: dict[str, Any], as_of: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in finance_health.get('sources', []) if isinstance(finance_health.get('sources'), list) else []:
        if not isinstance(row, dict) or not row.get('source_id'):
            continue
        compatible = {
            'source_id': str(row.get('source_id')),
            'evaluated_at': str(row.get('evaluated_at') or as_of.isoformat().replace('+00:00', 'Z')),
            'freshness_status': row.get('freshness_status') if row.get('freshness_status') in {'fresh', 'aging', 'stale', 'unknown'} else 'unknown',
            'freshness_age_seconds': row.get('freshness_age_seconds') if isinstance(row.get('freshness_age_seconds'), (int, float)) else None,
            'latency_status': row.get('latency_status') if row.get('latency_status') in {'ok', 'degraded', 'breached', 'unknown'} else 'unknown',
            'observed_latency_seconds': row.get('observed_latency_seconds') if isinstance(row.get('observed_latency_seconds'), (int, float)) else None,
            'schema_status': row.get('schema_status') if row.get('schema_status') in {'ok', 'drift', 'breaking_drift', 'unknown'} else 'unknown',
            'validation_status': row.get('validation_status') if row.get('validation_status') in {'pass', 'warn', 'fail', 'unknown'} else 'warn',
            'rights_status': row.get('rights_status') if row.get('rights_status') in {'ok', 'restricted', 'expired', 'unknown'} else 'unknown',
            'coverage_status': row.get('coverage_status') if row.get('coverage_status') in {'ok', 'partial', 'unavailable', 'unknown'} else 'unknown',
            'last_seen_at': row.get('last_seen_at') if parse_dt(row.get('last_seen_at')) else None,
            'last_success_at': row.get('last_success_at') if parse_dt(row.get('last_success_at')) else None,
            'last_error_at': row.get('last_error_at') if parse_dt(row.get('last_error_at')) else None,
            'breach_reasons': sorted(set(str(item) for item in row.get('breach_reasons', []) if item)) if isinstance(row.get('breach_reasons'), list) else [],
            'metric_refs': [str(FINANCE_SOURCE_HEALTH)],
            'source_refs': [str(item) for item in row.get('source_refs', [])[:10]] if isinstance(row.get('source_refs'), list) else [],
            'health_hash': 'sha256:pending',
            'no_execution': True,
        }
        if row.get('quota_status') == 'degraded' and 'finance_quota_degraded' not in compatible['breach_reasons']:
            compatible['breach_reasons'].append('finance_quota_degraded')
        hash_input = dict(compatible)
        hash_input['health_hash'] = 'sha256:pending'
        compatible['health_hash'] = canonical_hash(hash_input)
        rows.append(compatible)
    return rows


def build_report(
    registry: dict[str, Any],
    records: list[dict[str, Any]],
    as_of: datetime | None = None,
    finance_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    as_of = as_of or datetime.now(timezone.utc)
    sources = [item for item in registry.get('sources', []) if isinstance(item, dict)]
    health_rows = [health_for_source(source, records, sources, as_of) for source in sources]
    if finance_health:
        by_id = {row['source_id']: row for row in health_rows}
        for row in compatible_finance_health_rows(finance_health, as_of):
            # Finance-local health is an observed runtime signal. For matching source IDs,
            # prefer the more degraded row; for new finance-only sources, append it.
            current = by_id.get(row['source_id'])
            if current is None or row['breach_reasons']:
                by_id[row['source_id']] = row
        health_rows = list(by_id.values())
    status = 'pass'
    if any(row['freshness_status'] == 'stale' for row in health_rows):
        status = 'degraded'
    if any(row['validation_status'] == 'fail' for row in health_rows):
        status = 'fail'
    summary = {
        'freshness': {label: sum(1 for row in health_rows if row['freshness_status'] == label) for label in ['fresh', 'aging', 'stale', 'unknown']},
        'latency': {label: sum(1 for row in health_rows if row['latency_status'] == label) for label in ['ok', 'degraded', 'breached', 'unknown']},
        'rights': {label: sum(1 for row in health_rows if row['rights_status'] == label) for label in ['ok', 'restricted', 'expired', 'unknown']},
    }
    return {
        'generated_at': as_of.isoformat().replace('+00:00', 'Z'),
        'status': status,
        'registry_version': str(registry.get('version') or 'unknown'),
        'health_policy_version': POLICY_VERSION,
        'source_count': len(health_rows),
        'sources': health_rows,
        'summary': summary,
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--registry', default=str(REGISTRY))
    parser.add_argument('--evidence-jsonl', default=str(LIVE_EVIDENCE))
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--history', default=str(HISTORY))
    parser.add_argument('--no-history', action='store_true')
    parser.add_argument('--finance-source-health', default=None)
    parser.add_argument('--include-finance-source-health', action='store_true')
    args = parser.parse_args(argv)
    out = Path(args.out)
    history = Path(args.history)
    if not safe_state_path(out) or not safe_state_path(history):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_state_path']}, ensure_ascii=False))
        return 2
    registry = load_json(Path(args.registry), {}) or {}
    records = load_jsonl(Path(args.evidence_jsonl))
    finance_health = load_json(Path(args.finance_source_health), {}) if args.include_finance_source_health and args.finance_source_health else None
    report = build_report(registry, records, finance_health=finance_health)
    atomic_write_json(out, report)
    if not args.no_history:
        append_jsonl(history, {
            'generated_at': report['generated_at'],
            'status': report['status'],
            'registry_version': report['registry_version'],
            'health_policy_version': report['health_policy_version'],
            'source_count': report['source_count'],
            'summary': report['summary'],
            'report_hash': canonical_hash(report),
            'no_execution': True,
        })
    print(json.dumps({'status': report['status'], 'source_count': report['source_count'], 'out': str(out)}, ensure_ascii=False))
    return 0 if report['status'] in {'pass', 'degraded'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
