from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from undercurrent_compiler import compile_undercurrents


def _invalidators():
    return {'invalidators': [{
        'invalidator_id': 'inv:tsla-risk',
        'status': 'hit',
        'description': 'direction_conflict:theme:unknown_discovery',
        'hit_count': 9,
        'evidence_refs': ['ev:1'],
    }]}


def _opportunities():
    return {'candidates': [{
        'candidate_id': 'opp:tsla',
        'instrument': 'TSLA',
        'status': 'candidate',
        'score': 12,
        'theme': 'TSLA delivery risk scout',
        'source_refs': ['https://example.com/tsla'],
    }]}


def _atoms():
    return [
        {'atom_id': 'atom:news', 'source_id': 'source:reuters', 'source_lane': 'news_policy_narrative'},
        {'atom_id': 'atom:price', 'source_id': 'source:yfinance', 'source_lane': 'market_structure'},
    ]


def _claim_graph():
    return {'claims': [
        {
            'claim_id': 'claim:news',
            'atom_id': 'atom:news',
            'subject': 'TSLA',
            'predicate': 'mentions',
            'object': 'TSLA delivery risk scout',
            'direction': 'bearish',
            'contradicts': ['claim:price'],
            'event_class': 'narrative',
        },
        {
            'claim_id': 'claim:price',
            'atom_id': 'atom:price',
            'subject': 'TSLA',
            'predicate': 'moves',
            'object': 'TSLA price up',
            'direction': 'bullish',
            'contradicts': ['claim:news'],
            'event_class': 'price',
        },
    ]}


def _context_gaps():
    return {'gaps': [{
        'gap_id': 'gap:filing',
        'claim_id': 'claim:news',
        'missing_lane': 'corporate_filing',
        'why_load_bearing': 'Issuer claim lacks filing confirmation',
        'cost_of_ignorance': 'medium',
    }]}


def _source_health():
    return {'sources': [
        {'source_id': 'source:reuters', 'freshness_status': 'fresh', 'rights_status': 'restricted'},
        {'source_id': 'source:yfinance', 'freshness_status': 'unknown', 'rights_status': 'ok'},
    ]}


def test_undercurrent_uses_claim_graph_for_source_diversity():
    result = compile_undercurrents(
        _invalidators(), _opportunities(), {},
        source_health=_source_health(),
        atoms=_atoms(),
        claim_graph=_claim_graph(),
        context_gaps=_context_gaps(),
    )
    first = result['undercurrents'][0]
    assert first['source_diversity'] == 2
    assert first['cross_lane_confirmation'] == 2
    assert first['contradiction_load'] >= 1
    assert set(first['linked_refs']['claim']) == {'claim:news', 'claim:price'}


def test_undercurrent_links_context_gaps_as_known_unknowns():
    result = compile_undercurrents(
        _invalidators(), _opportunities(), {},
        source_health=_source_health(),
        atoms=_atoms(),
        claim_graph=_claim_graph(),
        context_gaps=_context_gaps(),
    )
    first = result['undercurrents'][0]
    assert first['known_unknowns']
    assert first['known_unknowns'][0]['missing_lane'] == 'corporate_filing'
    assert first['linked_refs']['context_gap'] == ['gap:filing']


def test_source_health_degradation_is_explicit_not_blocking():
    result = compile_undercurrents(
        _invalidators(), _opportunities(), {},
        source_health=_source_health(),
        atoms=_atoms(),
        claim_graph=_claim_graph(),
        context_gaps=_context_gaps(),
    )
    assert result['status'] == 'pass'
    first = result['undercurrents'][0]
    assert first['source_health_summary']['degraded_count'] == 2
    assert set(first['source_health_refs']) == {'source:reuters', 'source:yfinance'}
    assert first['no_execution'] is True


def test_undercurrent_output_remains_compatible_without_shadow_inputs():
    result = compile_undercurrents(_invalidators(), _opportunities(), {})
    first = result['undercurrents'][0]
    assert first['source_diversity'] == 0
    assert first['known_unknowns'] == []
    assert first['shadow_inputs']['claim_graph'] is False
