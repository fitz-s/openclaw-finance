#!/usr/bin/env python3
"""Activate Brave source lanes from deterministic QueryPacks.

This runner converts planner-only QueryPacks into SourceFetchRecords. It does
not promote answer prose, mutate wake thresholds, or make market judgments.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json
from brave_search_fetcher_common import default_out, fetch_from_pack, write_jsonl
from query_registry_compiler import (
    build_query_run_record,
    load_jsonl as load_registry_jsonl,
    should_skip_query,
    write_jsonl as write_registry_jsonl,
)


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
QUERY_PACKS = STATE / 'query-packs' / 'scanner-planned.jsonl'
QUERY_REGISTRY = STATE / 'query-registry.jsonl'
REPORT = STATE / 'brave-source-activation-report.json'
CONTRACT = 'brave-source-activation-v1'
MAX_RECORDS_PER_ENDPOINT = 200
DEFAULT_MAX_PACKS = 4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
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


def append_records(path: Path, rows: list[dict[str, Any]], *, keep: int = MAX_RECORDS_PER_ENDPOINT) -> None:
    existing = load_jsonl(path)
    write_jsonl(path, (existing + rows)[-keep:])


def endpoint_plan(pack: dict[str, Any]) -> list[str]:
    lane = str(pack.get('lane') or '')
    purpose = str(pack.get('purpose') or '')
    domains = pack.get('allowed_domains') if isinstance(pack.get('allowed_domains'), list) else []
    if lane == 'news_policy_narrative' or purpose in {'source_discovery', 'claim_closure'}:
        return ['news', 'web']
    if domains:
        return ['web', 'news']
    return ['news', 'web']


def should_try_next_endpoint(record: dict[str, Any]) -> bool:
    status = str(record.get('status') or '')
    result_count = int(record.get('result_count') or 0)
    app_code = str(record.get('application_error_code') or record.get('error_code') or '')
    error_class = str(record.get('error_class') or '')
    if status in {'ok', 'partial'} and result_count > 0:
        return False
    if status == 'rate_limited' or error_class == 'throttle_or_quota':
        return False
    if app_code == 'missing_api_key' or error_class == 'missing_credentials':
        return False
    if app_code in {'OPTION_NOT_IN_PLAN', 'RESOURCE_NOT_ALLOWED'}:
        return True
    if status in {'ok', 'partial'} and result_count == 0:
        return True
    if status == 'failed' and error_class in {'network_error', 'server_error', 'application_error'}:
        return True
    return False


def pack_priority(pack: dict[str, Any]) -> tuple[int, str]:
    query = str(pack.get('query') or '').lower()
    purpose = str(pack.get('purpose') or '')
    score = 0
    if purpose == 'source_discovery':
        score -= 10
    if 'unknown' in query or 'non-watchlist' in query:
        score -= 5
    if 'fresh' in query:
        score -= 3
    return score, str(pack.get('pack_id') or '')


def selected_packs(packs: list[dict[str, Any]], *, max_packs: int) -> list[dict[str, Any]]:
    valid = [
        pack for pack in packs
        if isinstance(pack, dict)
        and pack.get('query')
        and pack.get('no_execution') is True
        and pack.get('pack_is_not_authority') is True
    ]
    return sorted(valid, key=pack_priority)[:max(0, max_packs)]


def activate_pack(
    pack: dict[str, Any],
    *,
    registry_path: Path,
    dry_run: bool,
    force: bool,
    timeout: int,
    recent_registry: list[dict[str, Any]],
) -> dict[str, Any]:
    if should_skip_query(pack, recent_registry) and not force:
        return {
            'pack_id': pack.get('pack_id'),
            'query': pack.get('query'),
            'status': 'skipped',
            'reason': 'query_registry_cooldown',
            'records': [],
            'no_execution': True,
        }

    records: list[dict[str, Any]] = []
    plan = endpoint_plan(pack)
    for idx, endpoint in enumerate(plan):
        record = fetch_from_pack(
            pack,
            endpoint_type=endpoint,
            dry_run=dry_run,
            registry_path=registry_path,
            timeout=timeout,
        )
        record['activation_runner'] = CONTRACT
        record['activation_endpoint_index'] = idx
        record['fallback_from_endpoint'] = plan[idx - 1] if idx > 0 else None
        records.append(record)
        if idx == len(plan) - 1 or not should_try_next_endpoint(record):
            break

    return {
        'pack_id': pack.get('pack_id'),
        'query': pack.get('query'),
        'status': records[-1].get('status') if records else 'skipped',
        'endpoint_count': len(records),
        'fallback_attempted': len(records) > 1,
        'records': records,
        'no_execution': True,
    }


def write_fetch_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_endpoint: dict[str, list[dict[str, Any]]] = {'web': [], 'news': []}
    for record in records:
        endpoint = 'news' if record.get('endpoint') == 'brave/news/search' else 'web' if record.get('endpoint') == 'brave/web/search' else None
        if endpoint:
            by_endpoint[endpoint].append(record)
    outputs: dict[str, Any] = {}
    for endpoint, rows in by_endpoint.items():
        if not rows:
            continue
        path = default_out(endpoint)
        append_records(path, rows)
        outputs[endpoint] = {'path': str(path), 'record_count': len(rows)}
    return outputs


def update_query_registry(registry_path: Path, packs: list[dict[str, Any]], pack_results: list[dict[str, Any]]) -> dict[str, Any]:
    registry = load_registry_jsonl(registry_path)
    by_pack_id = {result.get('pack_id'): result for result in pack_results}
    added = 0
    for pack in packs:
        result = by_pack_id.get(pack.get('pack_id'))
        if not result or result.get('status') == 'skipped':
            continue
        records = [record for record in result.get('records', []) if isinstance(record, dict)]
        registry.append(build_query_run_record(pack, records))
        added += 1
    write_registry_jsonl(registry_path, registry[-500:])
    return {'path': str(registry_path), 'added_records': added, 'total_retained': min(len(registry), 500)}


def build_report(
    *,
    packs: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    pack_results: list[dict[str, Any]],
    fetch_outputs: dict[str, Any],
    registry_update: dict[str, Any],
    dry_run: bool,
) -> dict[str, Any]:
    records = [
        record
        for result in pack_results
        for record in result.get('records', [])
        if isinstance(record, dict)
    ]
    statuses: dict[str, int] = {}
    endpoints: dict[str, int] = {}
    for record in records:
        status = str(record.get('status') or 'unknown')
        endpoint = str(record.get('endpoint') or 'unknown')
        statuses[status] = statuses.get(status, 0) + 1
        endpoints[endpoint] = endpoints.get(endpoint, 0) + 1
    return {
        'generated_at': now_iso(),
        'status': 'pass',
        'contract': CONTRACT,
        'dry_run': dry_run,
        'input_pack_count': len(packs),
        'selected_pack_count': len(selected),
        'fetch_record_count': len(records),
        'status_counts': statuses,
        'endpoint_counts': endpoints,
        'fallback_count': sum(1 for result in pack_results if result.get('fallback_attempted')),
        'skipped_count': sum(1 for result in pack_results if result.get('status') == 'skipped'),
        'pack_results': [
            {
                'pack_id': result.get('pack_id'),
                'status': result.get('status'),
                'endpoint_count': result.get('endpoint_count', 0),
                'fallback_attempted': result.get('fallback_attempted', False),
                'query': result.get('query'),
            }
            for result in pack_results
        ],
        'fetch_outputs': fetch_outputs,
        'query_registry_update': registry_update,
        'source_health_should_run_after': True,
        'records_are_not_evidence': True,
        'no_execution': True,
    }


def run_activation(
    *,
    query_packs_path: Path = QUERY_PACKS,
    registry_path: Path = QUERY_REGISTRY,
    report_path: Path = REPORT,
    max_packs: int = DEFAULT_MAX_PACKS,
    dry_run: bool = False,
    force: bool = False,
    timeout: int = 12,
) -> dict[str, Any]:
    if not safe_state_path(query_packs_path) or not safe_state_path(registry_path) or not safe_state_path(report_path):
        return {'status': 'blocked', 'blocking_reasons': ['unsafe_state_path'], 'no_execution': True}
    packs = load_jsonl(query_packs_path)
    selected = selected_packs(packs, max_packs=max_packs)
    recent_registry = load_registry_jsonl(registry_path)
    pack_results = [
        activate_pack(pack, registry_path=registry_path, dry_run=dry_run, force=force, timeout=timeout, recent_registry=recent_registry)
        for pack in selected
    ]
    records = [
        record
        for result in pack_results
        for record in result.get('records', [])
        if isinstance(record, dict)
    ]
    fetch_outputs = write_fetch_records(records)
    registry_update = update_query_registry(registry_path, selected, pack_results)
    report = build_report(
        packs=packs,
        selected=selected,
        pack_results=pack_results,
        fetch_outputs=fetch_outputs,
        registry_update=registry_update,
        dry_run=dry_run,
    )
    atomic_write_json(report_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--query-packs', default=str(QUERY_PACKS))
    parser.add_argument('--registry', default=str(QUERY_REGISTRY))
    parser.add_argument('--report', default=str(REPORT))
    parser.add_argument('--max-packs', type=int, default=DEFAULT_MAX_PACKS)
    parser.add_argument('--timeout', type=int, default=12)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args(argv)
    report = run_activation(
        query_packs_path=Path(args.query_packs),
        registry_path=Path(args.registry),
        report_path=Path(args.report),
        max_packs=args.max_packs,
        timeout=args.timeout,
        dry_run=args.dry_run,
        force=args.force,
    )
    print(json.dumps({
        'status': report.get('status'),
        'selected_pack_count': report.get('selected_pack_count'),
        'fetch_record_count': report.get('fetch_record_count'),
        'status_counts': report.get('status_counts'),
        'fallback_count': report.get('fallback_count'),
        'out': str(args.report),
    }, ensure_ascii=False))
    return 0 if report.get('status') in {'pass', 'blocked'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
