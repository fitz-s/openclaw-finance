from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from source_health_monitor import build_report


def test_source_health_monitor_surfaces_budget_guard_observability_only() -> None:
    report = build_report(
        budget_state={
            'generated_at': '2026-04-19T05:00:00Z',
            'last_decision': {'allowed': False, 'reason': 'aperture_cap_exhausted'},
        },
        router_state={'generated_at': '2026-04-19T05:00:00Z', 'session_aperture': {'aperture_id': 'aperture:test'}},
        aperture_state={'generated_at': '2026-04-19T05:00:00Z', 'aperture_id': 'aperture:test'},
        generated_at='2026-04-19T05:05:00Z',
    )
    row = next(item for item in report['sources'] if item['source_id'] == 'source:brave_budget_guard')

    assert row['quota_status'] == 'degraded'
    assert 'aperture_cap_exhausted' in row['breach_reasons']
    assert report['shadow_only'] is True
    assert report['no_execution'] is True
    assert 'wake_authority' not in row
