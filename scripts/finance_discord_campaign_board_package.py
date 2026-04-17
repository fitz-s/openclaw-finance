#!/usr/bin/env python3
"""Compile a finance-local Discord Campaign Board package.

This script has no external side effects. It does not call Discord, edit messages,
create threads, mutate cron jobs, or bypass delivery safety.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
CAMPAIGN_BOARD = STATE / 'campaign-board.json'
CAMPAIGN_THREADS = STATE / 'campaign-threads.json'
REPORT_ENVELOPE = STATE / 'finance-decision-report-envelope.json'
SAFETY = STATE / 'report-delivery-safety-check.json'
OUT = STATE / 'discord-campaign-board-package.json'
CONTRACT = 'discord-campaign-board-package-v1'


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


def text(value: Any) -> str:
    return str(value or '').strip()


def fallback_primary(report_envelope: dict[str, Any]) -> str:
    return text(report_envelope.get('discord_primary_markdown')) or text(report_envelope.get('markdown'))


def build_package(
    *,
    campaign_board: dict[str, Any],
    campaign_threads: dict[str, Any],
    report_envelope: dict[str, Any],
    safety: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    live = text(campaign_board.get('discord_live_board_markdown'))
    scout = text(campaign_board.get('discord_scout_board_markdown'))
    risk = text(campaign_board.get('discord_risk_board_markdown'))
    primary_fallback = fallback_primary(report_envelope)
    thread_seed = text(report_envelope.get('discord_thread_seed_markdown'))
    status = 'pass' if (live or primary_fallback) else 'degraded'
    if safety and safety.get('status') not in {None, 'pass'}:
        status = 'degraded'
    return {
        'generated_at': generated_at or now_iso(),
        'status': status,
        'contract': CONTRACT,
        'mode': 'finance_local_shadow_package',
        'live_board_markdown': live,
        'scout_board_markdown': scout,
        'risk_board_markdown': risk,
        'primary_fallback_markdown': primary_fallback,
        'thread_seed_markdown': thread_seed,
        'campaign_board_ref': str(CAMPAIGN_BOARD),
        'thread_registry_ref': str(CAMPAIGN_THREADS),
        'report_envelope_ref': str(REPORT_ENVELOPE),
        'delivery_safety_ref': str(SAFETY),
        'thread_registry_summary': {
            'status': campaign_threads.get('status'),
            'thread_count': campaign_threads.get('thread_count') or len(campaign_threads.get('threads', {}) if isinstance(campaign_threads.get('threads'), dict) else {}),
            'thread_is_ui_not_memory': campaign_threads.get('thread_is_ui_not_memory') is True,
        },
        'delivery_instructions': {
            'main_channel_primary': 'live_board_markdown_or_primary_fallback',
            'persistent_board_updates': 'parent_runtime_only',
            'thread_creation': 'parent_runtime_only',
            'fallback_floor': 'primary_fallback_markdown_not_route_card_only',
        },
        'safety_summary': {
            'delivery_safety_status': safety.get('status'),
            'discord_primary_ok': safety.get('discord_primary_ok'),
            'campaign_boards_ok': safety.get('campaign_boards_ok'),
            'thread_followup_ok': safety.get('thread_followup_ok'),
        },
        'no_external_side_effects': True,
        'no_discord_api_calls': True,
        'no_thread_creation': True,
        'no_cron_or_gateway_mutation': True,
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign-board', default=str(CAMPAIGN_BOARD))
    parser.add_argument('--campaign-threads', default=str(CAMPAIGN_THREADS))
    parser.add_argument('--report-envelope', default=str(REPORT_ENVELOPE))
    parser.add_argument('--safety', default=str(SAFETY))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_state_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    package = build_package(
        campaign_board=load_json_safe(Path(args.campaign_board), {}) or {},
        campaign_threads=load_json_safe(Path(args.campaign_threads), {}) or {},
        report_envelope=load_json_safe(Path(args.report_envelope), {}) or {},
        safety=load_json_safe(Path(args.safety), {}) or {},
    )
    atomic_write_json(out, package)
    print(json.dumps({'status': package['status'], 'out': str(out), 'mode': package['mode']}, ensure_ascii=False))
    return 0 if package['status'] in {'pass', 'degraded'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
