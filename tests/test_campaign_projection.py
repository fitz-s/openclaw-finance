from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from undercurrent_compiler import compile_undercurrents
from campaign_projection_compiler import compile_campaign_board
from finance_campaign_cache_builder import build_cache
from finance_followup_context_router import route_context


def _invalidators():
    return {'invalidators': [{
        'invalidator_id': 'inv:unknown',
        'status': 'hit',
        'description': 'direction_conflict:theme:unknown_discovery',
        'hit_count': 11,
        'evidence_refs': ['ev:1', 'ev:2'],
    }]}


def _opportunities():
    return {'candidates': [
        {'candidate_id': 'opp:rgti', 'instrument': 'RGTI', 'status': 'candidate', 'score': 15.8, 'theme': 'RGTI elevated implied volatility', 'source_refs': ['https://example.com/iv']},
        {'candidate_id': 'opp:bno', 'instrument': 'BNO', 'status': 'candidate', 'score': 14.2, 'theme': 'BNO Hormuz physical supply constraints', 'source_refs': ['https://example.com/oil']},
        {'candidate_id': 'opp:xlb', 'instrument': 'XLB', 'status': 'candidate', 'score': 6.85, 'theme': 'XLB vs XLY bearish dislocation', 'source_refs': ['state:invalidator-ledger.json']},
    ]}


def _agenda():
    return {'agenda_items': [{
        'agenda_id': 'ag:unknown',
        'agenda_type': 'invalidator_escalation',
        'priority_score': 22,
        'linked_thesis_ids': ['packet:SPY'],
        'attention_justification': 'invalidator direction_conflict:theme:unknown_discovery has hit 11 times',
        'required_questions': ['is thesis packet:SPY still valid after 11 invalidator hits?'],
    }]}


def test_undercurrent_compiler_projects_invalidator_clusters():
    result = compile_undercurrents(_invalidators(), _opportunities(), {})
    assert result['status'] == 'pass'
    first = next(card for card in result['undercurrents'] if card['source_type'] == 'invalidator_cluster')
    assert first['undercurrent_id'].startswith('undercurrent:')
    assert first['no_execution'] is True
    assert '未知发现' in first['human_title']


def test_campaign_projection_builds_human_live_board():
    undercurrents = compile_undercurrents(_invalidators(), _opportunities(), {})
    board = compile_campaign_board(_agenda(), {}, _opportunities(), _invalidators(), {}, {}, {}, undercurrents)
    assert board['status'] == 'pass'
    assert board['campaigns'][0]['campaign_id'].startswith('campaign:')
    assert board['campaigns'][0]['board_class'] == 'live'
    text = board['discord_live_board_markdown']
    assert 'Finance｜Live Board' in text
    assert 'RGTI' in text and 'BNO' in text and 'XLB' in text
    assert 'invalidator direction_conflict' not in text


def test_campaign_cache_and_followup_router_select_verb_slice():
    undercurrents = compile_undercurrents(_invalidators(), _opportunities(), {})
    board = compile_campaign_board(_agenda(), {}, _opportunities(), _invalidators(), {}, {}, {}, undercurrents)
    cache = build_cache(board)
    campaign_id = board['campaigns'][0]['campaign_id']
    bundle = {'bundle_id': 'rb:test', 'object_cards': [], 'handles': {}}
    routed = route_context(query=f'challenge {campaign_id}', bundle=bundle, campaign_board=board, campaign_cache=cache)
    assert routed['status'] == 'pass'
    assert routed['verb'] == 'challenge'
    assert routed['cache_slice']['countercase_slice']
    assert 'kill_switches' in routed['evidence_slice_keys']


def test_compare_requires_secondary_handle():
    undercurrents = compile_undercurrents(_invalidators(), _opportunities(), {})
    board = compile_campaign_board(_agenda(), {}, _opportunities(), _invalidators(), {}, {}, {}, undercurrents)
    cache = build_cache(board)
    campaign_id = board['campaigns'][0]['campaign_id']
    routed = route_context(query=f'compare {campaign_id}', bundle={'bundle_id': 'rb:test'}, campaign_board=board, campaign_cache=cache)
    assert routed['status'] == 'fail'
    assert 'missing_secondary_handle' in routed['errors']
