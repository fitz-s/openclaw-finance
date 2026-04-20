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

from atomic_io import atomic_write_json
from finance_delivery_observed_audit import build_audit as build_delivery_audit
from finance_delivery_observed_audit import observed_delivered_since
from offhours_session_clock import build_state as build_session_aperture

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
PYTHON = Path('/opt/homebrew/bin/python3')
STATE = FINANCE / 'state'
REGISTRY = STATE / 'finance-discord-followup-threads.json'
ENVELOPE = STATE / 'finance-decision-report-envelope.json'
SAFETY = STATE / 'report-delivery-safety-check.json'
HEALTH_MD = STATE / 'report-delivery-health-only.md'
CONTEXT_PACK = STATE / 'llm-job-context' / 'report-orchestrator.json'
BOARD_PACKAGE = STATE / 'discord-campaign-board-package.json'
BOARD_RUNTIME = STATE / 'discord-campaign-board-runtime.json'
BOARD_DELIVERY_REPORT = STATE / 'discord-campaign-board-delivery-report.json'
MARKETDAY_CORE_POLICY = STATE / 'marketday-core-review-policy.json'
REPORT_CALENDAR_GUARD = STATE / 'marketday-report-calendar-guard.json'
DELIVERY_OBSERVED_AUDIT = STATE / 'finance-delivery-observed-audit.json'
CT = ZoneInfo('America/Chicago')
FOLLOWUP_REGISTRY_WARNING = (
    'followup_registry_updated_after_cutoff_is_warning_only_not_delivery_proof'
)


def run(args: list[str], *, stdout_path: Path | None = None) -> None:
    kwargs = {'cwd': str(FINANCE), 'check': True, 'text': True}
    if stdout_path is not None:
        with stdout_path.open('w', encoding='utf-8') as out:
            subprocess.run(args, stdout=out, stderr=subprocess.PIPE, **kwargs)
        return
    subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)


def run_optional(args: list[str]) -> None:
    subprocess.run(args, cwd=str(FINANCE), check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def board_runtime_enabled() -> bool:
    try:
        data = json.loads(BOARD_RUNTIME.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return bool(data.get('boards_enabled') or data.get('threads_enabled'))


def today_ct() -> datetime:
    return datetime.now(timezone.utc).astimezone(CT)


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(CT)
    except ValueError:
        return None


def followup_registry_activity_since_today(
    hour: int, minute: int, *, now: datetime | None = None
) -> dict[str, object]:
    now_value = now or today_ct()
    cutoff = datetime.combine(now_value.date(), time(hour, minute), tzinfo=CT)
    latest_updated: datetime | None = None
    matching_thread_count = 0
    try:
        data = json.loads(REGISTRY.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    for record in (data.get('threads') or {}).values():
        if not isinstance(record, dict):
            continue
        updated = parse_iso(str(record.get('updated_at') or ''))
        if not updated or updated < cutoff:
            continue
        matching_thread_count += 1
        if latest_updated is None or updated > latest_updated:
            latest_updated = updated
    observed_since_cutoff = matching_thread_count > 0
    return {
        'boundary': 'followup_thread_registry',
        'authoritative_delivery_proof': False,
        'observed_since_cutoff': observed_since_cutoff,
        'cutoff': cutoff.isoformat(),
        'matching_thread_count': matching_thread_count,
        'latest_updated_at': latest_updated.isoformat() if latest_updated else None,
        'warning': FOLLOWUP_REGISTRY_WARNING if observed_since_cutoff else None,
    }


def has_report_since_today(hour: int, minute: int) -> bool:
    activity = followup_registry_activity_since_today(hour, minute)
    return bool(activity.get('observed_since_cutoff'))


def report_calendar_guard(now: datetime, mode: str) -> dict:
    aperture = build_session_aperture(now.astimezone(timezone.utc))
    session_class = str(aperture.get('session_class') or '')
    should_run = True
    skip_reason = None
    if session_class in {'weekend_aperture', 'holiday_aperture'}:
        should_run = False
        skip_reason = session_class
    elif mode == 'marketday-core-review' and aperture.get('early_close') is True and session_class != 'rth':
        should_run = False
        skip_reason = 'halfday_core_review_after_close'
    guard = {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'mode': mode,
        'should_run': should_run,
        'skip_reason': skip_reason,
        'session_aperture': aperture,
        'review_source': '/Users/leofitz/Downloads/review 2026-04-18.md',
        'no_delivery_mutation': True,
        'no_wake_mutation': True,
        'no_threshold_mutation': True,
        'no_execution': True,
    }
    return guard


def run_chain(*, fast_core: bool = False) -> str:
    # Core reports must refresh the macro triad before rendering so Gold / Bitcoin / SPX
    # direction is present or explicitly unavailable in the operator surface.
    run([str(PYTHON), 'scripts/price_fetcher.py'])
    run([str(PYTHON), 'scripts/broad_market_proxy_fetcher.py'])
    run_optional([str(PYTHON), 'scripts/options_iv_provider_fetcher.py'])
    run_optional([str(PYTHON), 'scripts/options_iv_surface_compiler.py'])
    run_optional([str(PYTHON), 'scripts/opportunity_queue_builder.py'])
    run_optional([str(PYTHON), 'scripts/source_atom_compiler.py', '--report', str(STATE / 'source-atoms' / 'latest-report.json')])
    run_optional([str(PYTHON), 'scripts/claim_graph_compiler.py'])
    run_optional([str(PYTHON), 'scripts/context_gap_compiler.py'])
    if fast_core:
        write_json(MARKETDAY_CORE_POLICY, {
            'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'mode': 'marketday-core-review',
            'fast_core': True,
            'live_parent_ingest_skipped': True,
            'reason': 'fixed_second_core_report_timeliness',
            'review_source': '/Users/leofitz/Downloads/review 2026-04-18.md',
            'no_delivery_mutation': True,
            'no_wake_mutation': True,
            'no_threshold_mutation': True,
            'no_execution': True,
        })
    else:
        run([str(PYTHON), 'scripts/finance_parent_market_ingest_cutover.py'])
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
    run([str(PYTHON), 'scripts/finance_discord_campaign_board_package.py', '--out', str(BOARD_PACKAGE)])
    run_optional([str(PYTHON), 'scripts/finance_report_archive_compiler.py'])
    run_optional([str(PYTHON), 'scripts/finance_source_to_campaign_cutover_gate.py'])
    run_optional([str(PYTHON), 'scripts/finance_followup_thread_registry_repair.py', '--quiet'])
    if board_runtime_enabled():
        run_optional([str(PYTHON), 'scripts/finance_discord_campaign_board_deliver.py', '--apply', '--report', str(BOARD_DELIVERY_REPORT)])
        run_optional([str(PYTHON), 'scripts/finance_followup_thread_registry_repair.py', '--quiet'])
    envelope = json.loads(ENVELOPE.read_text(encoding='utf-8'))
    package = json.loads(BOARD_PACKAGE.read_text(encoding='utf-8')) if BOARD_PACKAGE.exists() else {}
    if board_runtime_enabled():
        primary = str(package.get('primary_fallback_markdown') or envelope.get('discord_primary_markdown') or envelope.get('markdown') or '').strip()
    else:
        primary = str(envelope.get('discord_live_board_markdown') or envelope.get('discord_primary_markdown') or envelope.get('markdown') or '').strip()
    if not primary:
        return 'Finance｜health-only\n\nReport generated but primary markdown was empty. Check finance-decision-report-envelope.json.\n'
    return primary + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['morning-watchdog', 'marketday-review', 'marketday-core-review'], required=True)
    args = parser.parse_args(argv)

    now = today_ct()
    guard = report_calendar_guard(now, args.mode)
    atomic_write_json(REPORT_CALENDAR_GUARD, guard)
    if guard.get('should_run') is not True:
        print('NO_REPLY')
        return 0
    if args.mode == 'morning-watchdog':
        audit = build_delivery_audit(now=now)
        followup_registry_activity = followup_registry_activity_since_today(7, 30, now=now)
        audit['watchdog_duplicate_suppression_boundary'] = 'observed_parent_delivery_only'
        audit['followup_registry_activity'] = followup_registry_activity
        if followup_registry_activity.get('observed_since_cutoff'):
            warnings = audit.get('warnings')
            if not isinstance(warnings, list):
                warnings = []
            if FOLLOWUP_REGISTRY_WARNING not in warnings:
                warnings.append(FOLLOWUP_REGISTRY_WARNING)
            audit['warnings'] = warnings
        atomic_write_json(DELIVERY_OBSERVED_AUDIT, audit)
        if observed_delivered_since(audit, hour=7, minute=30, now=now):
            print('NO_REPLY')
            return 0
    sys.stdout.write(run_chain(fast_core=args.mode in {'morning-watchdog', 'marketday-review', 'marketday-core-review'}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
