#!/usr/bin/env python3
"""Deterministic live scanner producer for the offhours lane."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from atomic_io import atomic_write_json
from offhours_session_clock import build_state as build_session_aperture

WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
OPS_SCRIPTS = WORKSPACE / 'ops' / 'scripts'
OPS_STATE = WORKSPACE / 'ops' / 'state'

if str(OPS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OPS_SCRIPTS))

from finance_native_scanner_shadow import build_shadow_output, current_window, load_json

TZ_CHI = ZoneInfo('America/Chicago')

PRICES = FINANCE / 'state' / 'prices.json'
ALERTS = FINANCE / 'state' / 'portfolio-alerts.json'
HELD = FINANCE / 'state' / 'held-tickers-resolved.json'
OPTION_RISK = FINANCE / 'state' / 'portfolio-option-risk.json'
WATCHLIST = FINANCE / 'state' / 'watchlist-resolved.json'
WATCHERS = FINANCE / 'state' / 'event-watchers.json'
BUFFER_DIR = FINANCE / 'buffer'
REPORT_PATH = OPS_STATE / 'finance-native-offhours-live-report.json'


def artifact_name(scan_dt: datetime) -> str:
    now_chi = scan_dt.astimezone(TZ_CHI)
    return f"{now_chi.strftime('%Y-%m-%d')}-scan-{now_chi.strftime('%H%M')}.json"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--prices', default=str(PRICES))
    parser.add_argument('--alerts', default=str(ALERTS))
    parser.add_argument('--held', default=str(HELD))
    parser.add_argument('--option-risk', default=str(OPTION_RISK))
    parser.add_argument('--watchlist', default=str(WATCHLIST))
    parser.add_argument('--watchers', default=str(WATCHERS))
    parser.add_argument('--output-dir', default=str(BUFFER_DIR))
    parser.add_argument('--report', default=str(REPORT_PATH))
    parser.add_argument('--scan-time')
    parser.add_argument('--window')
    parser.add_argument('--skip-downstream', action='store_true')
    args = parser.parse_args(argv)

    scan_dt = datetime.fromisoformat(args.scan_time.replace('Z', '+00:00')) if args.scan_time else datetime.now(timezone.utc)
    scan_time = scan_dt.isoformat()
    session_aperture = build_session_aperture(scan_dt)
    window = args.window or current_window(scan_dt.astimezone(TZ_CHI))

    output, shadow_report = build_shadow_output(
        prices=load_json(Path(args.prices), {}),
        alerts=load_json(Path(args.alerts), {}),
        held=load_json(Path(args.held), {}),
        option_risk=load_json(Path(args.option_risk), {}),
        watchlist=load_json(Path(args.watchlist), {}),
        watchers=load_json(Path(args.watchers), {}),
        scan_time=scan_time,
        window=window,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / artifact_name(scan_dt)
    atomic_write_json(output_path, output)

    downstream = {'worker_rc': None, 'gate_rc': None}
    if not args.skip_downstream:
        worker = subprocess.run([sys.executable, str(FINANCE / 'scripts' / 'finance_worker.py')], cwd=str(FINANCE / 'scripts'))
        gate = subprocess.run([sys.executable, str(FINANCE / 'scripts' / 'gate_evaluator.py')], cwd=str(FINANCE / 'scripts'))
        downstream = {'worker_rc': worker.returncode, 'gate_rc': gate.returncode}

    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pass',
        'scan_time': scan_time,
        'window': window,
        'session_aperture': session_aperture,
        'calendar_aware_offhours': True,
        'output_path': str(output_path),
        'observation_count': len(output.get('observations', [])),
        'decision': output.get('decision'),
        'downstream': downstream,
        'shadow_report': shadow_report,
    }
    atomic_write_json(Path(args.report), report)
    print(json.dumps({
        'status': report['status'],
        'output_path': report['output_path'],
        'observation_count': report['observation_count'],
        'report_path': str(args.report),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
