#!/usr/bin/env python3
"""Run the parent market-ingest bridge for finance artifacts.

This is a review-only bridge. It refreshes parent ContextPacket/WakeDecision
from finance-local artifacts but does not deliver Discord messages and does not
change execution authority.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
WORKSPACE = FINANCE.parent
MARKET_INGEST = WORKSPACE / 'services' / 'market-ingest'
STATE = FINANCE / 'state'
MI_STATE = MARKET_INGEST / 'state'
PYTHON = Path('/opt/homebrew/bin/python3')
REPORT = STATE / 'parent-market-ingest-cutover-report.json'


def run_step(name: str, args: list[str], *, required: bool = True) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=str(FINANCE), capture_output=True, text=True, timeout=180)
    payload: dict[str, Any] = {
        'name': name,
        'returncode': proc.returncode,
        'ok': proc.returncode == 0,
        'stdout_tail': proc.stdout.strip().splitlines()[-3:],
        'stderr_tail': proc.stderr.strip().splitlines()[-3:],
        'required': required,
    }
    if required and proc.returncode != 0:
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def build_steps(*, dry_run: bool = False, scanner_mode: str = 'auto', include_sec_fallback: bool = False) -> list[tuple[str, list[str], bool]]:
    query_planner = [str(PYTHON), str(FINANCE / 'scripts' / 'query_pack_planner.py'), '--scanner-mode', scanner_mode]
    brave_activation = [str(PYTHON), str(FINANCE / 'scripts' / 'brave_source_activation.py')]
    compression_activation = [str(PYTHON), str(FINANCE / 'scripts' / 'brave_compression_activation.py')]
    sec_fallback_activation = [str(PYTHON), str(FINANCE / 'scripts' / 'sec_fallback_activation.py')]
    source_health = [str(PYTHON), str(FINANCE / 'scripts' / 'source_health_monitor.py')]
    if scanner_mode == 'offhours-scan':
        source_health.append('--include-runtime-control-state')
    if dry_run:
        brave_activation.append('--dry-run')
    steps: list[tuple[str, list[str], bool]] = []
    if scanner_mode == 'offhours-scan':
        steps.append(('offhours_source_router', [str(PYTHON), str(FINANCE / 'scripts' / 'offhours_source_router.py')], True))
    steps.extend([
        ('finance_context_pack', [str(PYTHON), str(FINANCE / 'scripts' / 'finance_llm_context_pack.py')], True),
        ('query_pack_planner', query_planner, True),
        ('brave_source_activation', brave_activation, True),
    ])
    if include_sec_fallback or scanner_mode == 'offhours-scan':
        steps.append(('sec_fallback_activation', sec_fallback_activation, False))
    if scanner_mode == 'offhours-scan':
        steps.append(('brave_compression_activation', compression_activation, True))
    steps.extend([
        ('finance_source_health', source_health, True),
        ('parent_live_finance_adapter', [str(PYTHON), str(MARKET_INGEST / 'adapters' / 'live_finance_adapter.py')], True),
        (
            'parent_source_health',
            [
                str(PYTHON), str(MARKET_INGEST / 'source_health' / 'compiler.py'),
                '--finance-source-health', str(STATE / 'source-health.json'),
                '--include-finance-source-health',
            ],
            True,
        ),
        ('parent_temporal_alignment', [str(PYTHON), str(MARKET_INGEST / 'temporal_alignment' / 'alignment.py')], True),
        (
            'parent_packet_compiler',
            [
                str(PYTHON), str(MARKET_INGEST / 'packet_compiler' / 'compiler.py'),
                '--evidence-jsonl', str(MI_STATE / 'live-evidence-records.jsonl'),
                '--alignment-report', str(MI_STATE / 'temporal-alignment-report.json'),
                '--report', str(MI_STATE / 'live-packet-report.json'),
                '--latest-packet', str(MI_STATE / 'latest-context-packet.json'),
            ],
            True,
        ),
        (
            'parent_wake_policy',
            [
                str(PYTHON), str(MARKET_INGEST / 'wake_policy' / 'policy.py'),
                '--packet', str(MI_STATE / 'latest-context-packet.json'),
                '--evidence-jsonl', str(MI_STATE / 'live-evidence-records.jsonl'),
                '--report', str(MI_STATE / 'wake-report.json'),
                '--latest-wake', str(STATE / 'latest-wake-decision.json'),
            ],
            True,
        ),
    ])
    if dry_run:
        dry_steps: list[tuple[str, list[str], bool]] = []
        for step in steps:
            dry_steps.append(step)
            if step[0] == 'finance_source_health':
                break
        return dry_steps
    return steps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--scanner-mode', choices=['auto', 'market-hours-scan', 'offhours-scan'], default='auto')
    parser.add_argument('--include-sec-fallback', action='store_true')
    parser.add_argument('--report', default=str(REPORT))
    args = parser.parse_args(argv)
    results = []
    status = 'pass'
    try:
        for name, cmd, required in build_steps(dry_run=args.dry_run, scanner_mode=args.scanner_mode, include_sec_fallback=args.include_sec_fallback):
            results.append(run_step(name, cmd, required=required))
    except Exception as exc:
        status = 'fail'
        results.append({'name': 'exception', 'ok': False, 'error': str(exc)[:1200], 'required': True})
    payload = {
        'status': status,
        'mode': 'dry_run' if args.dry_run else 'apply',
        'scanner_mode': args.scanner_mode,
        'steps': results,
        'parent_outputs': {
            'live_evidence': str(MI_STATE / 'live-evidence-records.jsonl'),
            'source_health': str(MI_STATE / 'source-health.json'),
            'temporal_alignment': str(MI_STATE / 'temporal-alignment-report.json'),
            'latest_packet': str(MI_STATE / 'latest-context-packet.json'),
            'wake': str(STATE / 'latest-wake-decision.json'),
        },
        'no_execution': True,
    }
    write_json(Path(args.report), payload)
    print(json.dumps({'status': status, 'mode': payload['mode'], 'report': str(args.report)}, ensure_ascii=False))
    return 0 if status == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
