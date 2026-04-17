from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from finance_campaign_cache_builder import build_cache
from finance_followup_context_router import route_context


def _campaign() -> dict:
    return {
        'campaign_id': 'campaign:abc',
        'thread_key': 'campaign-thread:abc',
        'board_class': 'live',
        'priority_score': 12,
        'human_title': 'TSLA risk',
        'why_now_delta': 'risk changed',
        'source_freshness': {'status': 'mixed'},
        'capital_relevance': 'attention slot competition',
        'confirmations_needed': ['price confirm'],
        'why_not_now': 'review only',
        'kill_switches': ['risk clears'],
        'linked_thesis': ['thesis:tsla'],
        'linked_displacement_cases': [],
        'linked_scenarios': [],
        'linked_opportunities': ['opp:tsla'],
        'linked_invalidators': ['inv:tsla'],
        'linked_atoms': ['atom:1'],
        'linked_claims': ['claim:1'],
        'linked_context_gaps': ['gap:1'],
        'known_unknowns': [{
            'gap_id': 'gap:1',
            'missing_lane': 'displacement_case',
            'why_load_bearing': 'Need displacement case before compare.',
            'closure_condition': 'Build displacement case.',
            'gap_status': 'open',
        }],
        'source_health_summary': {'degraded_count': 1},
    }


def _board() -> dict:
    return {'contract': 'campaign-projection-v1', 'campaigns': [_campaign()]}


def _bundle() -> dict:
    return {'bundle_id': 'rb:test', 'campaign_alias_map': {'C1': 'campaign:abc'}, 'object_cards': [{'handle': 'A1', 'type': 'agenda'}], 'handles': {'A1': {'type': 'agenda'}}}


def test_followup_router_resolves_campaign_and_bundle_aliases() -> None:
    cache = build_cache(_board())
    routed = route_context(query='why C1', bundle=_bundle(), campaign_board=_board(), campaign_cache=cache)
    assert routed['status'] == 'pass'
    assert routed['resolved_primary_handle'] == 'campaign:abc'
    assert routed['selected_campaign']['campaign_id'] == 'campaign:abc'
    assert routed['evidence_slice_id'].startswith('slice:')


def test_followup_router_emits_trace_slice_and_cache_card() -> None:
    cache = build_cache(_board())
    routed = route_context(query='trace campaign:abc', bundle=_bundle(), campaign_board=_board(), campaign_cache=cache)
    assert routed['status'] == 'pass'
    assert 'linked_atoms' in routed['evidence_slice_keys']
    assert routed['cache_slice']['lineage_refs']['atoms'] == ['atom:1']


def test_missing_compare_context_returns_insufficient_data_metadata() -> None:
    cache = build_cache(_board())
    routed = route_context(query='compare campaign:abc thesis:tsla', bundle=_bundle(), campaign_board=_board(), campaign_cache=cache)
    assert routed['status'] == 'pass'
    assert routed['insufficient_data'] is True
    assert 'linked_displacement_cases' in routed['missing_fields']
    assert routed['recommended_answer_status'] == 'insufficient_data'
    assert routed['evidence_slice_coverage']['coverage_status'] == 'insufficient'
    assert routed['context_gap_guidance'][0]['gap_id'] == 'gap:1'


def test_followup_router_emits_verb_specific_evidence_groups() -> None:
    cache = build_cache(_board())
    why = route_context(query='why campaign:abc', bundle=_bundle(), campaign_board=_board(), campaign_cache=cache)
    sources = route_context(query='sources campaign:abc', bundle=_bundle(), campaign_board=_board(), campaign_cache=cache)
    assert 'promotion_reason' in why['required_evidence_groups']
    assert 'claim_lineage' in sources['required_evidence_groups']
    assert why['required_evidence_groups'] != sources['required_evidence_groups']


def test_compare_still_requires_secondary_handle() -> None:
    routed = route_context(query='compare campaign:abc', bundle=_bundle(), campaign_board=_board(), campaign_cache=build_cache(_board()))
    assert routed['status'] == 'fail'
    assert 'missing_secondary_handle' in routed['errors']
