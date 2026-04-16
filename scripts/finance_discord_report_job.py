#!/usr/bin/env python3
"""Deterministic stdout surface for OpenClaw finance report cron jobs.

This script is intentionally small: OpenClaw cron may call it and deliver stdout.
It never trades; it only runs the existing report validation/safety chain and
prints either NO_REPLY, health-only markdown, or discord_primary_markdown.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
PYTHON = Path('/opt/homebrew/bin/python3')
STATE = FINANCE / 'state'
REGISTRY = STATE / 'finance-discord-followup-threads.json'
ENVELOPE = STATE / 'finance-decision-report-envelope.json'
SAFETY = STATE / 'report-delivery-safety-check.json'
HEALTH_MD = STATE / 'report-delivery-health-only.md'
CONTEXT_PACK = STATE / 'llm-job-context' / 'report-orchestrator.json'
CT = ZoneInfo('America/Chicago')


def run(args: list[str], *, stdout_path: Path | None = None) -> None:
    kwargs = {'cwd': str(FINANCE), 'check': True, 'text': True}
    if stdout_path is not None:
        with stdout_path.open('w', encoding='utf-8') as out:
            subprocess.run(args, stdout=out, stderr=subprocess.PIPE, **kwargs)
        return
    subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)


def today_ct() -> datetime:
    return datetime.now(timezone.utc).astimezone(CT)


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(CT)
    except ValueError:
        return None


def has_report_since_today(hour: int, minute: int) -> bool:
    now = today_ct()
    cutoff = datetime.combine(now.date(), time(hour, minute), tzinfo=CT)
    try:
        data = json.loads(REGISTRY.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    for record in (data.get('threads') or {}).values():
        if not isinstance(record, dict):
            continue
        updated = parse_iso(str(record.get('updated_at') or ''))
        if updated and updated >= cutoff:
            return True
    return False


def run_chain() -> str:
    run([str(PYTHON), 'scripts/finance_llm_context_pack.py'])
    run([
        str(PYTHON), 'scripts/judgment_envelope_gate.py',
        '--allow-fallback',
        '--adjudication-mode', 'scheduled_context',
        '--context-pack', str(CONTEXT_PACK),
    ])
    run([str(PYTHON), 'scripts/undercurrent_compiler.py'])
    run([str(PYTHON), 'scripts/campaign_projection_compiler.py'])
    run([str(PYTHON), 'scripts/finance_decision_report_render.py'])
    run([str(PYTHON), 'scripts/finance_report_product_validator.py'])
    run([str(PYTHON), 'scripts/finance_decision_log_compiler.py'])
    run([str(PYTHON), 'scripts/finance_report_delivery_safety.py', '--out', str(SAFETY), '--health-markdown'], stdout_path=HEALTH_MD)
    safety = json.loads(SAFETY.read_text(encoding='utf-8'))
    if safety.get('status') != 'pass':
        return HEALTH_MD.read_text(encoding='utf-8').strip() + '\n'
    run([str(PYTHON), 'scripts/finance_report_reader_bundle.py'])
    run([str(PYTHON), 'scripts/finance_campaign_cache_builder.py'])
    envelope = json.loads(ENVELOPE.read_text(encoding='utf-8'))
    primary = str(envelope.get('discord_live_board_markdown') or envelope.get('discord_primary_markdown') or envelope.get('markdown') or '').strip()
    if not primary:
        return 'Finance｜health-only\n\nReport generated but primary markdown was empty. Check finance-decision-report-envelope.json.\n'
    return primary + '\n'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['morning-watchdog', 'marketday-review'], required=True)
    args = parser.parse_args()

    now = today_ct()
    if now.weekday() >= 5:
        print('NO_REPLY')
        return 0
    if args.mode == 'morning-watchdog' and has_report_since_today(7, 30):
        print('NO_REPLY')
        return 0
    sys.stdout.write(run_chain())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
