#!/usr/bin/env python3
"""SEC current-filings fallback activation for Brave source recovery."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
PYTHON = Path('/opt/homebrew/bin/python3')
STATE = FINANCE / 'state'
RECOVERY_POLICY = STATE / 'brave-source-recovery-policy.json'
SEC_DISCOVERY = STATE / 'sec-discovery.json'
SEC_SEMANTICS = STATE / 'sec-filing-semantics.json'
OUT = STATE / 'sec-fallback-activation-report.json'
CONTRACT = 'sec-fallback-activation-v1'


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def run_step(name: str, cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=str(FINANCE), capture_output=True, text=True, timeout=120)
    return {
        'name': name,
        'ok': proc.returncode == 0,
        'returncode': proc.returncode,
        'stdout_tail': proc.stdout.strip().splitlines()[-3:],
        'stderr_tail': proc.stderr.strip().splitlines()[-3:],
    }


def should_run(policy: dict[str, Any], *, force: bool) -> tuple[bool, str | None]:
    if force:
        return True, 'forced'
    if policy.get('breaker_open') is True:
        return True, 'brave_recovery_breaker_open'
    return False, 'brave_recovery_breaker_closed'


def build_activation_report(
    *,
    recovery_policy: dict[str, Any],
    force: bool = False,
    fixture_xml: Path | None = None,
    out: Path = OUT,
    discovery_out: Path = SEC_DISCOVERY,
    semantics_out: Path = SEC_SEMANTICS,
) -> dict[str, Any]:
    allowed, reason = should_run(recovery_policy, force=force)
    steps: list[dict[str, Any]] = []
    if allowed:
        discovery_cmd = [str(PYTHON), 'scripts/sec_discovery_fetcher.py', '--out', str(discovery_out)]
        if fixture_xml:
            discovery_cmd.extend(['--fixture-xml', str(fixture_xml)])
        steps.append(run_step('sec_discovery_fetcher', discovery_cmd))
        steps.append(run_step('sec_filing_semantics', [str(PYTHON), 'scripts/sec_filing_semantics.py', '--discovery', str(discovery_out), '--out', str(semantics_out)]))
    discovery = load_json_safe(discovery_out, {}) or {}
    semantics = load_json_safe(semantics_out, {}) or {}
    status = 'skipped' if not allowed else 'pass' if all(step.get('ok') for step in steps) and (discovery.get('discovery_count', 0) or semantics.get('semantic_count', 0)) else 'degraded'
    report = {
        'contract': CONTRACT,
        'status': status,
        'reason': reason,
        'force': force,
        'recovery_policy': {
            'breaker_open': recovery_policy.get('breaker_open'),
            'reason': recovery_policy.get('reason'),
            'breaker_until': recovery_policy.get('breaker_until'),
        },
        'steps': steps,
        'discovery_path': str(discovery_out),
        'semantics_path': str(semantics_out),
        'discovery_count': int(discovery.get('discovery_count') or 0),
        'semantic_count': int(semantics.get('semantic_count') or 0),
        'wake_candidate_count': int(semantics.get('wake_candidate_count') or 0),
        'support_only_count': int(semantics.get('support_only_count') or 0),
        'records_are_not_evidence': True,
        'fallback_lane': 'sec_current_filings_metadata_only',
        'review_source': '/Users/leofitz/Downloads/review 2026-04-18.md',
        'no_execution': True,
        'no_delivery_mutation': True,
        'no_wake_mutation': True,
        'no_threshold_mutation': True,
    }
    atomic_write_json(out, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery-policy', default=str(RECOVERY_POLICY))
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--discovery-out', default=str(SEC_DISCOVERY))
    parser.add_argument('--semantics-out', default=str(SEC_SEMANTICS))
    parser.add_argument('--fixture-xml')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args(argv)
    out = Path(args.out)
    discovery_out = Path(args.discovery_out)
    semantics_out = Path(args.semantics_out)
    if not all(safe_state_path(path) for path in [out, discovery_out, semantics_out, Path(args.recovery_policy)]):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_state_path']}, ensure_ascii=False))
        return 2
    report = build_activation_report(
        recovery_policy=load_json_safe(Path(args.recovery_policy), {}) or {},
        force=args.force,
        fixture_xml=Path(args.fixture_xml) if args.fixture_xml else None,
        out=out,
        discovery_out=discovery_out,
        semantics_out=semantics_out,
    )
    print(json.dumps({'status': report['status'], 'reason': report['reason'], 'discovery_count': report['discovery_count'], 'semantic_count': report['semantic_count'], 'out': str(out)}, ensure_ascii=False))
    return 0 if report['status'] in {'pass', 'degraded', 'skipped'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
