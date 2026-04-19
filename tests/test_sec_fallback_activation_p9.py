from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from sec_fallback_activation import build_activation_report

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = ROOT / 'state'
FIXTURE = ROOT / 'tests' / 'fixtures' / 'sec-current-sample.atom'


def _paths(name: str) -> dict[str, Path]:
    return {
        'report': STATE / f'test-p9-{name}-report.json',
        'discovery': STATE / f'test-p9-{name}-discovery.json',
        'semantics': STATE / f'test-p9-{name}-semantics.json',
    }


def _clean(paths: dict[str, Path]) -> None:
    for path in paths.values():
        path.unlink(missing_ok=True)


def test_sec_fallback_skips_when_breaker_closed_without_force() -> None:
    paths = _paths('skip')
    _clean(paths)
    report = build_activation_report(recovery_policy={'breaker_open': False, 'reason': 'clear'}, out=paths['report'], discovery_out=paths['discovery'], semantics_out=paths['semantics'])
    assert report['status'] == 'skipped'
    assert report['reason'] == 'brave_recovery_breaker_closed'
    assert report['steps'] == []


def test_sec_fallback_runs_when_forced_with_fixture() -> None:
    paths = _paths('forced')
    _clean(paths)
    report = build_activation_report(recovery_policy={'breaker_open': False, 'reason': 'clear'}, force=True, fixture_xml=FIXTURE, out=paths['report'], discovery_out=paths['discovery'], semantics_out=paths['semantics'])
    assert report['status'] == 'pass'
    assert report['reason'] == 'forced'
    assert report['discovery_count'] == 1
    assert report['semantic_count'] == 1
    assert report['records_are_not_evidence'] is True
    assert report['no_wake_mutation'] is True


def test_sec_fallback_runs_when_brave_breaker_open() -> None:
    paths = _paths('breaker')
    _clean(paths)
    report = build_activation_report(recovery_policy={'breaker_open': True, 'reason': 'recent_brave_quota_or_rate_limit'}, fixture_xml=FIXTURE, out=paths['report'], discovery_out=paths['discovery'], semantics_out=paths['semantics'])
    assert report['status'] == 'pass'
    assert report['reason'] == 'brave_recovery_breaker_open'
    assert report['fallback_lane'] == 'sec_current_filings_metadata_only'
