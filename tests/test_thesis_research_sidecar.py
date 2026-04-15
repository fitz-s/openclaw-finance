from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from custom_metric_compiler import compile_metrics
from scenario_card_builder import build_scenarios
from thesis_research_packet import build_packet
from thesis_research_sidecar import compile_dossiers


def test_research_packet_selects_only_isolated_wake_theses_and_top_opportunities() -> None:
    packet = build_packet(
        {'wake_class': 'PACKET_UPDATE_ONLY', 'thesis_refs': ['thesis:a']},
        {'theses': [{'thesis_id': 'thesis:a', 'instrument': 'AAPL'}]},
        {
            'candidates': [
                {'candidate_id': 'opportunity:low', 'status': 'candidate', 'score': 1},
                {'candidate_id': 'opportunity:high', 'status': 'candidate', 'score': 9},
                {'candidate_id': 'opportunity:retired', 'status': 'retired', 'score': 99},
            ]
        },
        {'invalidators': [{'invalidator_id': 'invalidator:a', 'status': 'hit', 'hit_count': 2}]},
        opportunity_limit=1,
    )

    assert packet['selected_theses'] == []
    assert [item['candidate_id'] for item in packet['selected_opportunities']] == ['opportunity:high']
    assert 'no_user_delivery' in packet['forbidden_actions']


def test_sidecar_artifacts_are_review_only_and_scenario_linked() -> None:
    research_packet = {
        'forbidden_actions': ['no_user_delivery', 'no_execution', 'no_threshold_mutation', 'no_live_authority_change'],
        'selected_opportunities': [
            {
                'candidate_id': 'opportunity:abc',
                'instrument': 'ABC',
                'theme': 'Brent oil disruption',
                'status': 'candidate',
                'promotion_reason': 'scanner_unknown_discovery',
            }
        ],
        'selected_theses': [],
    }
    metrics = compile_metrics(
        research_packet,
        {'quotes': {'ABC': {'status': 'ok', 'price': 10, 'pct_change': 2.5, 'volume': 100}}},
        {'top_events': [{'symbol': 'ABC', 'call_put': 'call', 'expiry': '2026-05-01', 'strike': 12, 'volume_oi_ratio': 3.5, 'score': 7}]},
    )
    scenarios = build_scenarios(
        {
            'candidates': [
                {
                    'candidate_id': 'opportunity:abc',
                    'instrument': 'ABC',
                    'theme': 'Brent oil disruption',
                    'status': 'candidate',
                    'score': 8,
                    'source_refs': ['source:abc'],
                }
            ]
        },
        {'invalidators': []},
    )
    dossiers = compile_dossiers(research_packet, metrics, scenarios)

    assert len(dossiers) == 1
    assert dossiers[0]['review_only'] is True
    assert 'no_execution' in dossiers[0]['forbidden_actions']
    assert dossiers[0]['metric_ref']['price_snapshot']['status'] == 'ok'
    assert dossiers[0]['scenario_refs'] == [scenarios['scenarios'][0]['scenario_id']]
