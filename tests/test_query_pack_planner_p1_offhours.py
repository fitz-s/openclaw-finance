from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from query_pack_planner import build_query_packs


GENERATED = '2026-04-19T05:00:00Z'
ROUTER = {
    'generated_at': GENERATED,
    'scanner_mode': 'offhours-scan',
    'budget_decision': {'allowed': True, 'kind': 'search', 'dry_run': True},
    'session_aperture': {
        'generated_at': GENERATED,
        'aperture_id': 'aperture:XNYS:2026-04-18:weekend_aperture',
        'session_class': 'weekend_aperture',
        'global_liquidity_band': 'us_dark',
        'is_offhours': True,
        'is_long_gap': True,
        'gap_hours': 20.0,
        'discovery_multiplier': 1.8,
        'answers_budget_class': 'high',
        'monday_open_risk': 0.8,
        'calendar_confidence': 'ok',
    },
}


def _scanner_pack() -> dict:
    return {
        'pack_id': 'scanner:test',
        'scanner_canonical_role': 'planner_first_legacy_observation_bridge',
        'fixed_search_budget': {'unknown_discovery_minimum_attempts': 1},
        'known_symbols_must_not_satisfy_unknown_discovery': ['TSLA'],
    }


def test_query_pack_planner_attaches_aperture_budget_only_for_offhours() -> None:
    report = build_query_packs(_scanner_pack(), generated_at=GENERATED, scanner_mode='offhours-scan', router_state=ROUTER)
    assert report['session_aperture_attached'] is True
    pack = report['query_packs'][0]
    assert pack['session_aperture']['session_class'] == 'weekend_aperture'
    assert pack['budget_request']['requires_budget_guard'] is True
    assert pack['budget_request']['answers_units'] == 0
    assert pack['budget_guard_not_evidence'] is True
    assert pack['pack_is_not_authority'] is True

    market = build_query_packs(_scanner_pack(), generated_at=GENERATED, scanner_mode='market-hours-scan', router_state=ROUTER)
    assert market['session_aperture_attached'] is False
    assert 'session_aperture' not in market['query_packs'][0]


def test_query_pack_planner_missing_router_state_is_nonfatal() -> None:
    report = build_query_packs(_scanner_pack(), generated_at=GENERATED, scanner_mode='offhours-scan', router_state={})
    assert report['status'] == 'pass'
    assert report['session_aperture_attached'] is False
    assert report['router_skip_reason'] == 'router_state_missing'
    assert report['query_pack_count'] >= 1
