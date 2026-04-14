#!/usr/bin/env python3
"""Native premarket brief live runner with optional Discord delivery."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from atomic_io import atomic_write_json
from finance_report_delivery_safety import evaluate as evaluate_delivery_safety, health_only_markdown

WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
OPS_STATE = WORKSPACE / 'ops' / 'state'

PACKET_SCRIPT = FINANCE / 'scripts' / 'finance_report_packet.py'
RENDER_SCRIPT = FINANCE / 'scripts' / 'finance_deterministic_report_render.py'
VALIDATOR_SCRIPT = FINANCE / 'scripts' / 'finance_report_validator.py'
INPUT_PACKET = FINANCE / 'state' / 'report-input-packet.json'
ENVELOPE_PATH = FINANCE / 'state' / 'finance-report-envelope.json'
VALIDATION_REPORT = FINANCE / 'state' / 'finance-report-validation.json'
LIVE_REPORT = OPS_STATE / 'finance-native-premarket-brief-live-report.json'
LAST_DELIVERY = FINANCE / 'state' / 'finance-report-last-delivery.json'
SAFETY_CHECK = FINANCE / 'state' / 'report-delivery-safety-check.json'
DISCORD_TARGET = 'channel:1479790104490016808'
DEFAULT_OPENCLAW = Path('/Users/leofitz/.npm-global/bin/openclaw')
REPORT_ENVELOPE_MAX_AGE_MINUTES = 30


def openclaw_binary() -> str:
    configured = Path(os.environ.get('OPENCLAW_BIN', str(DEFAULT_OPENCLAW)))
    if configured.exists():
        return str(configured)
    found = shutil.which('openclaw')
    if found:
        return found
    raise FileNotFoundError(f'openclaw binary not found at {configured}')

def load_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return default or {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default or {}


def run_step(script: Path) -> None:
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or f'{script.name} failed')


def run_report_generation() -> None:
    run_step(PACKET_SCRIPT)
    run_step(RENDER_SCRIPT)
    run_step(VALIDATOR_SCRIPT)


def envelope_age_minutes(path: Path) -> float | None:
    if not path.exists():
        return None
    return (datetime.now(timezone.utc).timestamp() - path.stat().st_mtime) / 60


def preflight_delivery(max_age_minutes: float) -> tuple[dict, dict, dict, list[str]]:
    packet = load_json(INPUT_PACKET)
    envelope = load_json(ENVELOPE_PATH)
    validation = load_json(VALIDATION_REPORT)
    blockers: list[str] = []
    if validation.get('status') != 'pass':
        blockers.append('validator_not_pass')
    if envelope.get('input_packet_hash') != packet.get('packet_hash'):
        blockers.append('input_packet_hash_mismatch')
    if envelope.get('envelope_hash') != validation.get('envelope_hash') and validation.get('envelope_hash'):
        blockers.append('validation_envelope_hash_mismatch')
    age = envelope_age_minutes(ENVELOPE_PATH)
    if age is None:
        blockers.append('missing_envelope')
    elif age > max_age_minutes:
        blockers.append('envelope_stale')
    if not envelope.get('markdown'):
        blockers.append('missing_markdown')
    return packet, envelope, validation, blockers


def deliver_message(markdown: str, dry_run: bool) -> dict:
    cmd = [
        openclaw_binary(), 'message', 'send',
        '--channel', 'discord',
        '--target', DISCORD_TARGET,
        '--message', markdown,
        '--json',
    ]
    if dry_run:
        cmd.append('--dry-run')
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        'returncode': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr,
        'dry_run': dry_run,
        'messageId': extract_message_id(result.stdout),
    }


def extract_message_id(stdout: str) -> str | None:
    try:
        payload = json.loads(stdout)
    except Exception:
        return None
    if isinstance(payload, dict):
        for key in ['messageId', 'message_id', 'id']:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        nested = payload.get('message') or payload.get('result')
        if isinstance(nested, dict):
            for key in ['messageId', 'message_id', 'id']:
                value = nested.get(key)
                if isinstance(value, str) and value:
                    return value
    return None


def update_last_delivery(report: dict) -> None:
    if report.get('delivered') is True:
        atomic_write_json(LAST_DELIVERY, report)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--deliver', action='store_true')
    parser.add_argument('--dry-run-delivery', action='store_true')
    parser.add_argument('--envelope-max-age-minutes', type=float, default=REPORT_ENVELOPE_MAX_AGE_MINUTES)
    args = parser.parse_args(argv)

    run_report_generation()
    packet, envelope, validation, blockers = preflight_delivery(args.envelope_max_age_minutes)
    delivery = None
    if args.deliver:
        report = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'status': 'blocked',
            'blocking_reasons': ['direct_report_delivery_deprecated'],
            'input_packet_hash': packet.get('packet_hash'),
            'envelope_hash': envelope.get('envelope_hash'),
            'validation_report_path': str(VALIDATION_REPORT),
            'envelope_path': str(ENVELOPE_PATH),
            'delivered': False,
            'delivery': None,
        }
        atomic_write_json(LIVE_REPORT, report)
        print(json.dumps({'status': report['status'], 'blocking_reasons': report['blocking_reasons'], 'live_report_path': str(LIVE_REPORT), 'delivered': False}, ensure_ascii=False))
        return 1
    if blockers:
        report = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'status': 'fail',
            'blocking_reasons': blockers,
            'input_packet_hash': packet.get('packet_hash'),
            'envelope_hash': envelope.get('envelope_hash'),
            'validation_report_path': str(VALIDATION_REPORT),
            'envelope_path': str(ENVELOPE_PATH),
            'delivered': False,
            'delivery': None,
        }
        atomic_write_json(LIVE_REPORT, report)
        print(json.dumps({'status': report['status'], 'blocking_reasons': blockers, 'live_report_path': str(LIVE_REPORT)}, ensure_ascii=False))
        return 1

    markdown = envelope['markdown']
    safety = evaluate_delivery_safety()
    atomic_write_json(SAFETY_CHECK, safety)
    if safety['status'] != 'pass' and (args.deliver or args.dry_run_delivery):
        report = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'status': 'blocked',
            'blocking_reasons': safety['blocking_reasons'],
            'input_packet_path': str(INPUT_PACKET),
            'envelope_path': str(ENVELOPE_PATH),
            'validation_report_path': str(VALIDATION_REPORT),
            'safety_check_path': str(SAFETY_CHECK),
            'input_packet_hash': packet.get('packet_hash'),
            'envelope_hash': envelope.get('envelope_hash'),
            'validator_status': validation.get('status'),
            'delivered': False,
            'messageId': None,
            'delivery': None,
            'health_only_markdown': health_only_markdown(safety),
        }
        atomic_write_json(LIVE_REPORT, report)
        print(json.dumps({
            'status': report['status'],
            'blocking_reasons': report['blocking_reasons'],
            'live_report_path': str(LIVE_REPORT),
            'safety_check_path': str(SAFETY_CHECK),
            'delivered': False,
        }, ensure_ascii=False))
        return 1 if args.deliver else 0

    if args.deliver or args.dry_run_delivery:
        delivery = deliver_message(markdown, dry_run=args.dry_run_delivery or not args.deliver)

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pass',
        'input_packet_path': str(INPUT_PACKET),
        'envelope_path': str(ENVELOPE_PATH),
        'validation_report_path': str(VALIDATION_REPORT),
        'input_packet_hash': packet.get('packet_hash'),
        'envelope_hash': envelope.get('envelope_hash'),
        'validator_status': validation.get('status'),
        'safety_check_path': str(SAFETY_CHECK),
        'safety_status': safety['status'],
        'delivered': bool(args.deliver and delivery and delivery['returncode'] == 0 and not delivery['dry_run']),
        'messageId': delivery.get('messageId') if delivery else None,
        'delivery': delivery,
    }
    atomic_write_json(LIVE_REPORT, report)
    update_last_delivery(report)
    print(json.dumps({
        'status': report['status'],
        'envelope_path': report['envelope_path'],
        'live_report_path': str(LIVE_REPORT),
        'delivered': report['delivered'],
        'messageId': report['messageId'],
    }, ensure_ascii=False))
    return 0 if not delivery or delivery['returncode'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
