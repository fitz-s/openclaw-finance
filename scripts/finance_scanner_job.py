#!/usr/bin/env python3
"""Deterministic stdout surface for finance scanner cron jobs."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
PYTHON = Path('/opt/homebrew/bin/python3')
STATE = FINANCE / 'state'
REPORT = STATE / 'finance-scanner-job-report.json'


def run_step(name: str, args: list[str], *, required: bool = True, timeout: int = 180) -> dict[str, Any]:
    try:
        proc = subprocess.run(args, cwd=str(FINANCE), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        payload = {
            'name': name,
            'ok': False,
            'returncode': 124,
            'required': required,
            'stdout_tail': (exc.stdout or '').splitlines()[-3:] if isinstance(exc.stdout, str) else [],
            'stderr_tail': (exc.stderr or '').splitlines()[-3:] if isinstance(exc.stderr, str) else [],
            'error': f'timed out after {timeout}s',
        }
        if required:
            raise RuntimeError(json.dumps(payload, ensure_ascii=False))
        return payload
    payload = {
        'name': name,
        'ok': proc.returncode == 0,
        'returncode': proc.returncode,
        'required': required,
        'stdout_tail': proc.stdout.strip().splitlines()[-3:],
        'stderr_tail': proc.stderr.strip().splitlines()[-3:],
    }
    if required and proc.returncode != 0:
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return payload


def write_report(payload: dict[str, Any], path: Path | None = None) -> None:
    path = path or REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def load_gate_summary() -> dict[str, Any]:
    path = STATE / 'report-gate-state.json'
    try:
        gate = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return {
        'recommendedReportType': gate.get('recommendedReportType'),
        'shouldSend': gate.get('shouldSend'),
        'dataStale': gate.get('dataStale'),
        'candidateCount': gate.get('candidateCount'),
        'decisionReason': gate.get('decisionReason'),
    }


def load_governor_summary() -> dict[str, Any]:
    path = STATE / 'offhours-cadence-governor-state.json'
    try:
        governor = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return {
        'should_run': governor.get('should_run'),
        'skip_reason': governor.get('skip_reason'),
        'session_class': governor.get('session_class'),
        'min_spacing_minutes': governor.get('min_spacing_minutes'),
    }


def build_steps(mode: str = 'market-hours-scan') -> list[tuple[str, list[str], bool, int]]:
    steps: list[tuple[str, list[str], bool, int]] = []
    if mode == 'offhours-scan':
        steps.append(('offhours_source_router', [str(PYTHON), 'scripts/offhours_source_router.py'], True, 60))
        steps.append(('offhours_cadence_governor', [str(PYTHON), 'scripts/offhours_cadence_governor.py'], True, 60))
    steps.extend([
        ('finance_context_pack', [str(PYTHON), 'scripts/finance_llm_context_pack.py'], True, 120),
        ('query_pack_planner', [str(PYTHON), 'scripts/query_pack_planner.py', '--scanner-mode', mode], True, 120),
        ('finance_worker', [str(PYTHON), 'scripts/finance_worker.py'], True, 120),
        ('parent_market_ingest_cutover', [str(PYTHON), 'scripts/finance_parent_market_ingest_cutover.py', '--scanner-mode', mode], True, 240),
        ('gate_evaluator', [str(PYTHON), 'scripts/gate_evaluator.py'], True, 240),
    ])
    return steps


def run_chain(mode: str) -> dict[str, Any]:
    steps = []
    status = 'pass'
    error = None
    try:
        try:
            step_specs = build_steps(mode)
        except TypeError:
            # Preserve compatibility with tests or callers that monkeypatch the
            # historical zero-arg build_steps() helper.
            step_specs = build_steps()
        for name, cmd, required, timeout in step_specs:
            steps.append(run_step(name, cmd, required=required, timeout=timeout))
            if mode == 'offhours-scan' and name == 'offhours_cadence_governor':
                governor = load_governor_summary()
                if governor.get('should_run') is False:
                    payload = {
                        'status': status,
                        'mode': mode,
                        'steps': steps,
                        'gate': {},
                        'governor': governor,
                        'skipped': True,
                        'error': None,
                        'no_execution': True,
                    }
                    write_report(payload)
                    return payload
    except Exception as exc:
        status = 'fail'
        error = str(exc)[:1200]
    payload = {
        'status': status,
        'mode': mode,
        'steps': steps,
        'gate': load_gate_summary(),
        'error': error,
        'no_execution': True,
    }
    write_report(payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['market-hours-scan', 'offhours-scan'], required=True)
    args = parser.parse_args(argv)
    report = run_chain(args.mode)
    gate = report.get('gate') or {}
    if report.get('status') == 'pass':
        if report.get('skipped') is True:
            governor = report.get('governor') or {}
            print(
                'scanner=skip'
                f" mode={args.mode}"
                f" reason={governor.get('skip_reason') or 'unknown'}"
                f" session={governor.get('session_class') or 'unknown'}"
            )
            return 0
        print(
            'scanner=ok'
            f" mode={args.mode}"
            f" gate={gate.get('recommendedReportType') or 'unknown'}"
            f" send={str(gate.get('shouldSend')).lower()}"
        )
        return 0
    print(f"scanner=fail mode={args.mode} check={REPORT}")
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
