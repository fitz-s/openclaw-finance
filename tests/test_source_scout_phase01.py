from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
CONTRACTS = ROOT / 'docs' / 'openclaw-runtime' / 'contracts'
sys.path.insert(0, str(SCRIPTS))

from source_scout import OPTIONS_IV_METRICS, REQUIRED_LANES, build_report


def test_source_scout_outputs_all_review_lanes() -> None:
    report = build_report()
    lanes = report['summary']['lanes']
    for lane in REQUIRED_LANES:
        assert lanes.get(lane, 0) >= 1
    assert report['activation_boundary'].startswith('shadow-only')
    assert report['no_execution'] is True


def test_options_iv_candidates_require_iv_specific_metrics() -> None:
    report = build_report()
    iv_candidates = [row for row in report['candidates'] if row['sublane'] == 'options_iv']
    assert len(iv_candidates) >= 4
    for row in iv_candidates:
        for metric in OPTIONS_IV_METRICS:
            assert metric in row['required_metrics']
        assert row['lane'] == 'market_structure'
        assert 'IV' in row['expected_value'] or 'options' in row['expected_value'].lower()
        assert row['activation_mode'] in {'candidate_only', 'credential_gated', 'local_terminal', 'proxy_fallback'}
        assert row['source_health_id'].startswith('source:')
        assert 'primary_eligible' in row


def test_options_iv_candidate_provider_boundaries_are_explicit() -> None:
    report = build_report()
    by_provider = {row['provider']: row for row in report['candidates'] if row['sublane'] == 'options_iv'}
    assert by_provider['ThetaData']['activation_mode'] == 'local_terminal'
    assert by_provider['ThetaData']['credential_ref'] == 'THETADATA_BASE_URL'
    assert by_provider['Polygon Options']['credential_ref'] == 'POLYGON_API_KEY'
    assert by_provider['Tradier Options']['primary_eligible'] is False
    assert 'courtesy_greeks_not_primary_iv_truth' in by_provider['Tradier Options']['promotion_blockers']
    assert by_provider['ORATS']['primary_eligible'] is False
    assert 'live_agreement_not_verified' in by_provider['ORATS']['promotion_blockers']


def test_source_scout_candidates_are_shadow_only_and_rights_scored() -> None:
    report = build_report()
    for row in report['candidates']:
        assert row['status'] == 'shadow_candidate'
        assert row['eligible_for_wake'] is False
        assert row['eligible_for_judgment_support'] is False
        assert row['no_execution'] is True
        assert row['rights_policy'] in {'raw_ok', 'derived_only', 'none', 'unknown'}
        assert row['cost_class']
        assert 'promotion_blockers' in row
    blocked = [row for row in report['candidates'] if row['rights_policy'] in {'unknown', 'none'}]
    assert blocked
    assert all(row['promotion_blockers'] for row in blocked)


def test_source_scout_contract_mentions_rights_cost_replay_and_options_iv() -> None:
    contract = (CONTRACTS / 'source-scout-contract.md').read_text(encoding='utf-8')
    registry = (CONTRACTS / 'source-registry-v2-contract.md').read_text(encoding='utf-8')
    for needle in ['rights_policy', 'cost_class', 'point_in_time_support', 'options_iv', 'activation_mode', 'source_health_id', 'primary_eligible']:
        assert needle in contract
    for needle in ['source_sublane', 'market_structure.options_iv', 'iv_rank', 'iv_percentile', 'provider_confidence']:
        assert needle in registry
