#!/usr/bin/env python3
"""Patch existing midday finance report job into fixed marketday core review."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

CRON = Path('/Users/leofitz/.openclaw/cron/jobs.json')
TARGET = 'finance-midday-operator-review'
SCHEDULE = '15 13 * * 1-5'
PYTHON = '/opt/homebrew/bin/python3'
FINANCE = '/Users/leofitz/.openclaw/workspace/finance'


def report_prompt() -> str:
    return f'''【OpenClaw Finance Deterministic Report Job】
Run exactly:
{PYTHON} {FINANCE}/scripts/finance_discord_report_job.py --mode marketday-core-review

Contract markers:
- This is the fixed second marketday core review attempt.
- It complements threshold wake reports; it does not replace wake policy.
- It uses the deterministic renderer/product-validator/decision-log/delivery-safety chain.
- It does not perform broker actions and does not mutate thresholds.

Output discipline:
- Return stdout exactly.
- If stdout is NO_REPLY, return only NO_REPLY.
- Do not summarize.
- Do not emit progress text.
- Do not send messages yourself; OpenClaw delivery handles Discord.
- Review-only; no execution.'''


def patch_jobs(payload: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    changed: list[str] = []
    for job in payload.get('jobs', []) if isinstance(payload.get('jobs'), list) else []:
        if not isinstance(job, dict) or job.get('name') != TARGET:
            continue
        schedule = job.setdefault('schedule', {})
        if schedule.get('expr') != SCHEDULE:
            schedule['kind'] = 'cron'
            schedule['expr'] = SCHEDULE
            schedule['tz'] = 'America/Chicago'
            changed.append('schedule_1315_ct')
        delivery = job.setdefault('delivery', {})
        if delivery.get('mode') != 'announce':
            raise ValueError('marketday_core_review_delivery_must_already_be_announce')
        payload_obj = job.setdefault('payload', {})
        prompt = report_prompt()
        if payload_obj.get('message') != prompt:
            payload_obj['message'] = prompt
            changed.append('prompt_marketday_core_review')
        if payload_obj.get('lightContext') is not True:
            payload_obj['lightContext'] = True
            changed.append('light_context')
        if int(payload_obj.get('timeoutSeconds') or 0) != 420:
            payload_obj['timeoutSeconds'] = 420
            changed.append('timeout_420')
        job['enabled'] = True
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
