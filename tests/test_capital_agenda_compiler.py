#!/usr/bin/env python3
"""Tests for capital_agenda_compiler: comparative ranking, binding refs, delivery cap."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from capital_agenda_compiler import compile_agenda, displacement_items, hedge_gap_items, crowding_items


def _graph(hedge_coverage=None, bucket_util=None, nodes=None):
    return {
        'nodes': nodes or [],
        'edges': [],
        'hedge_coverage': hedge_coverage or {},
        'bucket_utilization': bucket_util or {},
        'graph_hash': 'sha256:test',
    }


def _displacement(cases=None):
    return {'cases': cases or []}


def _opp(*items):
    return {'candidates': [
        {'candidate_id': f'opp:{s}', 'instrument': s, 'status': 'candidate', 'score': sc}
        for s, sc in items
    ]}


def _thesis(*items):
    return {'theses': [
        {'thesis_id': f'thesis:{s}', 'instrument': s, 'status': st, 'scenario_refs': []}
        for s, st in items
    ]}


def _inv(*items):
    return {'invalidators': [
        {'invalidator_id': f'inv:{i}', 'target_id': tid, 'status': 'open', 'hit_count': hc, 'description': f'inv {i}'}
        for i, (tid, hc) in enumerate(items)
    ]}


def test_hedge_gap_items():
    graph = _graph(hedge_coverage={'core_compounders': 'uncovered'}, bucket_util={'core_compounders': 0.5})
    items = hedge_gap_items(graph)
    assert len(items) == 1
    assert items[0]['agenda_type'] == 'hedge_gap_alert'
    assert items[0]['no_execution'] is True


def test_crowding_items():
    graph = _graph(
        bucket_util={'speculative_optionality': 0.9},
        nodes=[{
            'node_type': 'bucket', 'bucket_id': 'speculative_optionality',
            'current_thesis_refs': ['t1', 't2', 't3'],
        }],
    )
    items = crowding_items(graph)
    assert len(items) == 1
    assert items[0]['agenda_type'] == 'exposure_crowding_warning'


def test_displacement_items():
    disp = _displacement([{
        'case_id': 'dc:1',
        'candidate_thesis_ref': 'opp:AAPL',
        'displaced_thesis_ref': 'thesis:AAPL',
        'candidate_instrument': 'AAPL',
        'displaced_instrument': 'AAPL',
    }])
    opp = _opp(('AAPL', 5.0))
    items = displacement_items(disp, opp)
    assert len(items) == 1
    assert items[0]['agenda_type'] == 'new_opportunity'
    assert 'dc:1' in items[0]['displacement_case_refs']


def test_agenda_ranking_is_comparative():
    """Agenda items must be ranked by priority_score descending."""
    graph = _graph(hedge_coverage={'core_compounders': 'uncovered', 'macro_hedges': 'partial'},
                   bucket_util={'core_compounders': 0.5, 'macro_hedges': 0.3})
    agenda = compile_agenda(graph, _displacement(), {}, _thesis(), _inv(('thesis:X', 3)), _opp())
    scores = [item['priority_score'] for item in agenda['agenda_items']]
    assert scores == sorted(scores, reverse=True)


def test_all_items_have_no_execution():
    graph = _graph(hedge_coverage={'core_compounders': 'uncovered'},
                   bucket_util={'core_compounders': 0.5})
    agenda = compile_agenda(graph, _displacement(), {}, _thesis(('AAPL', 'active')),
                            _inv(('thesis:AAPL', 3)), _opp())
    for item in agenda['agenda_items']:
        assert item['no_execution'] is True


def test_empty_inputs_produces_empty_agenda():
    agenda = compile_agenda({}, {}, {}, {}, {}, {})
    assert agenda['total_generated'] == 0
    assert agenda['agenda_items'] == []


def test_agenda_cap():
    """Agenda should never exceed MAX_AGENDA_ITEMS (8)."""
    inv = _inv(*[('thesis:X', i + 2) for i in range(20)])
    graph = _graph(
        hedge_coverage={f'bucket{i}': 'uncovered' for i in range(5)},
        bucket_util={f'bucket{i}': 0.5 for i in range(5)},
    )
    agenda = compile_agenda(graph, _displacement(), {}, _thesis(), inv, _opp())
    assert len(agenda['agenda_items']) <= 8
