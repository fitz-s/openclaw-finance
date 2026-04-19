#!/usr/bin/env python3
"""Patch finance offhours scanner cron to all-days conservative cadence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CRON = Path('/Users/leofitz/.openclaw/cron/jobs.json')
TARGET = 'finance-subagent-scanner-offhours'
ALL_DAYS_EXPR = '0 0,4,7,17,20 * * *'
CONSERVATIVE_PREFIX = ['0', '0,4,7,17,20', '*', '*']


def all_days_expr(expr: str) -> str:
    fields = str(expr or '').split()
    if len(fields) != 5:
        raise ValueError('cron_expr_must_have_5_fields')
    if fields[:4] != CONSERVATIVE_PREFIX:
        raise ValueError('cron_expr_not_conservative_offhours_cadence')
    fields[4] = '*'
    return ' '.join(fields)


def patch_jobs(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    changed: list[str] = []
    jobs = payload.get('jobs') if isinstance(payload.get('jobs'), list) else []
    for job in jobs:
        if not isinstance(job, dict) or job.get('name') != TARGET:
            continue
        schedule = job.setdefault('schedule', {})
        patched_expr = all_days_expr(str(schedule.get('expr') or ''))
        if schedule.get('expr') != patched_expr:
            schedule['expr'] = patched_expr
            schedule['tz'] = schedule.get('tz') or 'America/Chicago'
            changed.append('schedule_expr_all_days')
        delivery = job.setdefault('delivery', {})
        if delivery.get('mode') != 'none':
            raise ValueError('offhours_delivery_must_already_be_none')
    return payload, changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--cron', default=str(CRON))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    path = Path(args.cron)
    payload = json.loads(path.read_text(encoding='utf-8'))
    patched, changed = patch_jobs(payload)
    if not args.dry_run and changed:
        path.write_text(json.dumps(patched, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'pass', 'changed': changed, 'dry_run': args.dry_run, 'cron': str(path)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
