#!/usr/bin/env python3
"""Tests for capital_delta report rendering and committee memo contract."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from finance_decision_report_render import build_report, render_capital_delta_markdown


def _packet():
    return {'packet_id': 'pkt:1', 'packet_hash': 'sha256:abc', 'layer_digest': {}, 'thesis_refs': ['t:1']}


def _judgment():
    return {
        'judgment_id': 'j:1', 'packet_id': 'pkt:1', 'packet_hash': 'sha256:abc',
        'thesis_state': 'no_trade', 'actionability': 'none', 'confidence': 0.0,
        'evidence_refs': ['ev:1'], 'thesis_refs': ['t:1'], 'scenario_refs': [], 'invalidator_refs': [],
        'required_confirmations': ['confirm1'], 'model_id': 'deterministic',
    }


def _validation():
    return {'outcome': 'accepted_for_log'}


def _capital_graph():
    return {
        'graph_hash': 'sha256:test123',
        'node_count': 10, 'edge_count': 5,
        'nodes': [], 'edges': [],
        'hedge_coverage': {'core_compounders': 'partial'},
        'bucket_utilization': {'core_compounders': 0.5},
    }


def _capital_agenda():
    return {
        'agenda_items': [{
            'agenda_id': 'ag:1', 'agenda_type': 'hedge_gap_alert',
            'priority_score': 3.0, 'linked_thesis_ids': ['t:1'],
            'linked_positions': [], 'linked_scenarios': [],
            'displacement_case_refs': [], 'opportunity_cost_refs': [],
            'required_questions': ['test question'],
            'attention_justification': 'test justification',
            'no_execution': True,
        }],
    }


def _displacement_cases():
    return {'cases': []}


def test_capital_delta_renders_agenda_section():
    md = render_capital_delta_markdown(
        _packet(), _judgment(), _validation(),
        prices={}, watchlist={}, scan_state={}, broad_market={},
        options_flow={}, portfolio={}, option_risk={},
        watch_intent={}, thesis_registry={}, opportunity_queue={},
        invalidator_ledger={}, capital_agenda=_capital_agenda(),
        capital_graph=_capital_graph(), displacement_cases=_displacement_cases(),
    )
    assert '## 资本议程' in md
    assert '## 替代分析' in md
    assert '## 护城河缺口' in md
    assert '资本竞争优先' in md
    assert '不下单' in md


def test_capital_delta_mode_with_graph():
    """build_report with capital_delta mode and valid graph should use capital renderer."""
    report = build_report(
        _packet(), _judgment(), _validation(),
        report_mode='capital_delta',
        capital_graph=_capital_graph(),
        capital_agenda=_capital_agenda(),
        displacement_cases=_displacement_cases(),
    )
    assert report['renderer_id'] == 'capital-delta-deterministic-v1'
    assert '## 资本议程' in report['markdown']
    assert report.get('capital_graph_hash') == 'sha256:test123'


def test_capital_delta_fallback_without_graph():
    """build_report with capital_delta mode but no graph should fall back to thesis_delta."""
    report = build_report(
        _packet(), _judgment(), _validation(),
        report_mode='capital_delta',
        capital_graph={},  # no graph_hash
        capital_agenda={},
        displacement_cases={},
    )
    assert 'thesis-delta' in report['renderer_id']
    assert '## 资本议程' not in report['markdown']


def test_capital_delta_fallback_none_graph():
    """build_report with capital_delta mode but None graph should fall back."""
    report = build_report(
        _packet(), _judgment(), _validation(),
        report_mode='capital_delta',
        capital_graph=None,
        capital_agenda=None,
        displacement_cases=None,
    )
    assert 'thesis-delta' in report['renderer_id']


def test_thesis_delta_unchanged():
    """thesis_delta mode should not be affected by capital changes."""
    report = build_report(
        _packet(), _judgment(), _validation(),
        report_mode='thesis_delta',
    )
    assert 'thesis-delta' in report['renderer_id']
    assert '## 今日看点' in report['markdown']


def test_committee_memo_forbidden_actions():
    """Verify committee memo stub has required forbidden_actions."""
    from capital_committee_sidecar import generate_role_memo
    agenda_item = {'agenda_id': 'ag:1', 'agenda_type': 'hedge_gap_alert', 'required_questions': ['q1']}
    memo = generate_role_memo('thesis_analyst', agenda_item, {})
    assert memo['role'] == 'thesis_analyst'
    assert 'no_execution' in memo['forbidden_actions']
    assert 'no_user_delivery' in memo['forbidden_actions']
    assert memo['confidence'] == 'insufficient_data'
