#!/usr/bin/env python3
"""Prune inactive finance follow-up thread routing records.

This removes threads from the active finance follow-up hot path. It does not
archive or delete Discord threads.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from finance_followup_thread_registry_repair import DEFAULT_INACTIVE_HOURS, DEFAULT_MAX_RECORDS, DEFAULT_TTL_DAYS, REGISTRY, repair_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Prune inactive finance follow-up thread registry records.')
    parser.add_argument('--registry', default=str(REGISTRY))
    parser.add_argument('--inactive-hours', type=int, default=DEFAULT_INACTIVE_HOURS)
    parser.add_argument('--ttl-days', type=int, default=DEFAULT_TTL_DAYS)
    parser.add_argument('--max-records', type=int, default=DEFAULT_MAX_RECORDS)
    parser.add_argument('--keep-missing-bundles', action='store_true')
    args = parser.parse_args(argv)
    report = repair_registry(
        Path(args.registry),
        ttl_days=args.ttl_days,
        max_records=args.max_records,
        inactive_after_hours=args.inactive_hours,
        prune_missing_bundle=not args.keep_missing_bundles,
    )
    report['operation'] = 'finance_thread_lifecycle_gc'
    report['discord_thread_delete_attempted'] = False
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get('status') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
