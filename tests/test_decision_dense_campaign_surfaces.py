from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from campaign_projection_compiler import compile_campaign_board
from finance_campaign_cache_builder import build_cache
from finance_discord_campaign_board_deliver import thread_seed


def _undercurrents() -> dict:
    return {'undercurrents': [{
        'undercurrent_id': 'und:unknown',
        'human_title': '未知发现方向冲突（18次）',
        'source_type': 'invalidator_cluster',
        'persistence_score': 18,
        'velocity': 18,
        'divergence': 'high',
        'crowding': 'unknown',
        'hedge_gap': 'unknown',
        'promotion_reason': '未知发现方向冲突（18次） 持续累积，需要判断是否影响 attention slot',
        'kill_conditions': ['后续两次扫描不再命中'],
        'linked_refs': {
            'opportunity': ['opportunity:bno'],
            'atom': ['atom:bno'],
            'claim': ['claim:bno'],
            'context_gap': ['gap:filing'],
            'invalidator': ['inv:unknown'],
        },
        'source_freshness': {'status': 'mixed', 'source_refs': ['ev:bno']},
        'source_diversity': 3,
        'cross_lane_confirmation': 2,
        'contradiction_load': 2,
        'known_unknowns': [{
            'gap_id': 'gap:filing',
            'missing_lane': 'corporate_filing',
            'why_load_bearing': 'Issuer/security claim lacks official filing or issuer confirmation.',
            'cost_of_ignorance': 'medium',
            'subject': 'BNO',
        }],
        'source_health_summary': {'degraded_count': 1, 'degraded_sources': ['source:yfinance']},
        'no_execution': True,
    }]}


def test_campaign_projection_humanizes_raw_invalidator_titles_and_adds_implication() -> None:
    board = compile_campaign_board({}, {}, {}, {}, {}, {}, {}, _undercurrents())
    campaign = board['campaigns'][0]
    assert 'direction_conflict' not in campaign['human_title']
    assert campaign['operator_brief']['implication']
    assert 'BNO' in campaign['operator_brief']['affected_objects']


def test_campaign_board_contains_implication_and_known_unknown() -> None:
    board = compile_campaign_board({}, {}, {}, {}, {}, {}, {}, _undercurrents())
    text = board['discord_risk_board_markdown'] + board['discord_live_board_markdown']
    assert 'Implication：' in text
    assert 'Evidence：' in text
    assert 'Unknown：' in text
    assert '缺官方/issuer 确认' in text


def test_campaign_cache_prepares_decision_dense_why_card() -> None:
    board = compile_campaign_board({}, {}, {}, {}, {}, {}, {}, _undercurrents())
    cache = build_cache(board)
    card = next(iter(cache['cache'].values()))['why']
    assert card['conclusion']
    assert 'BNO' in card['fact_slice'][2]
    assert card['known_unknowns']


def test_thread_seed_contains_prebrief_not_menu_only() -> None:
    board = compile_campaign_board({}, {}, {}, {}, {}, {}, {}, _undercurrents())
    seed = thread_seed(board['campaigns'][0])
    assert '结论' in seed
    assert 'Fact' in seed
    assert 'Interpretation' in seed
    assert 'Known Unknown' in seed
    assert '可问：' in seed
