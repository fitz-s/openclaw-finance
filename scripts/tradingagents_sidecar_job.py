#!/usr/bin/env python3
"""Orchestrate a bounded TradingAgents review-only sidecar run."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tradingagents_bridge_types import (
    DEFAULT_FORBIDDEN_ACTIONS,
    TRADINGAGENTS_CONTEXT_DIGEST,
    TRADINGAGENTS_READER_AUGMENTATION,
    TRADINGAGENTS_STATE,
    clean_instrument,
    ensure_dir,
    now_iso,
    write_json,
)
from tradingagents_request_packet import build_request
from tradingagents_advisory_translate import translate_run
from tradingagents_bridge_validator import validate_run
from tradingagents_runner import sanitize_environment
from tradingagents_surface_compiler import compile_surfaces


SCRIPTS = Path(__file__).resolve().parent


def run_job(mode: str, instrument: str | None = None) -> dict[str, Any]:
    ensure_dir(TRADINGAGENTS_STATE / 'job-reports')
    steps: list[dict[str, Any]] = []
    request = build_request(mode=mode, instrument=instrument)
    request_path = Path(request['request_path'])
    write_json(request_path, request)
    steps.append({'step': 'request', 'status': 'pass', 'path': str(request_path)})

    env = sanitize_environment()
    runner = subprocess.run(
        [sys.executable, str(SCRIPTS / 'tradingagents_runner.py'), '--request', str(request_path)],
        cwd=str(TRADINGAGENTS_STATE.parent.parent),
        capture_output=True,
        text=True,
        timeout=int(request['config'].get('timeout_seconds', 900)) + 5,
        env=env,
    )
    steps.append({
        'step': 'runner',
        'status': 'pass' if runner.returncode == 0 else 'fail',
        'stdout': runner.stdout.strip()[:800],
        'stderr': runner.stderr.strip()[:800],
    })

    run_root = request_path.parent
    raw_artifact = json.loads((run_root / 'raw' / 'run-artifact.json').read_text(encoding='utf-8'))
    if runner.returncode != 0 or raw_artifact.get('status') != 'pass':
        report = {
            'generated_at': now_iso(),
            'status': 'fail',
            'job_id': request['job_id'],
            'run_id': request['run_id'],
            'steps': steps,
            'forbidden_actions': DEFAULT_FORBIDDEN_ACTIONS,
            'review_only': True,
            'no_execution': True,
        }
        write_json(TRADINGAGENTS_STATE / 'job-reports' / f"{request['run_id']}.json", report)
        return report

    translate_result = translate_run(run_root)
    steps.append({'step': 'translate', 'status': translate_result['status']})
    validation = validate_run(run_root)
    steps.append({'step': 'validate', 'status': validation['status'], 'errors': validation['errors']})
    surfaces = compile_surfaces(run_root)
    steps.append({'step': 'surface', 'status': 'pass', 'paths': surfaces})

    report = {
        'generated_at': now_iso(),
        'status': 'pass' if validation['status'] == 'pass' else 'fail',
        'job_id': request['job_id'],
        'run_id': request['run_id'],
        'steps': steps,
        'latest_context_digest': str(TRADINGAGENTS_CONTEXT_DIGEST) if Path(TRADINGAGENTS_CONTEXT_DIGEST).exists() else None,
        'latest_reader_augmentation': str(TRADINGAGENTS_READER_AUGMENTATION) if Path(TRADINGAGENTS_READER_AUGMENTATION).exists() else None,
        'forbidden_actions': DEFAULT_FORBIDDEN_ACTIONS,
        'review_only': True,
        'no_execution': True,
    }
    write_json(TRADINGAGENTS_STATE / 'job-reports' / f"{request['run_id']}.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Run TradingAgents sidecar job.')
    parser.add_argument('--mode', default='manual')
    parser.add_argument('--instrument', default=None)
    args = parser.parse_args(argv)
    instrument = clean_instrument(args.instrument) if args.instrument else None
    report = run_job(args.mode, instrument)
    print(json.dumps({
        'status': report['status'],
        'job_id': report['job_id'],
        'run_id': report['run_id'],
    }, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
