#!/usr/bin/env python3
"""Tests for displacement_case_builder: only genuine overlaps produce cases."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from displacement_case_builder import build_cases


def _graph(thesis_nodes=None, bucket_util=None, hedge_coverage=None):
    nodes = thesis_nodes or []
    return {
        'nodes': nodes,
        'edges': [],
        'bucket_utilization': bucket_util or {},
        'hedge_coverage': hedge_coverage or {},
        'graph_hash': 'sha256:test',
    }


def _opp_queue(*items):
    return {'candidates': [
        {'candidate_id': f'opp:{sym}', 'instrument': sym, 'theme': f'{sym} theme', 'status': 'candidate', 'score': 5.0}
        for sym in items
    ]}


def test_no_overlap_no_case():
    """Candidate that doesn't overlap anything should produce no case."""
    graph = _graph(thesis_nodes=[
        {'node_type': 'thesis', 'node_id': 'thesis:AAPL', 'symbol': 'AAPL', 'bucket_ref': 'core_compounders'},
    ])
    opp = _opp_queue('XYZ')
    result = build_cases(opp, graph, {}, {})
    assert result['case_count'] == 0


def test_instrument_overlap_produces_case():
    """Candidate overlapping an existing thesis instrument should produce a case."""
    graph = _graph(thesis_nodes=[
        {'node_type': 'thesis', 'node_id': 'thesis:AAPL', 'symbol': 'AAPL', 'bucket_ref': 'core_compounders'},
    ])
    opp = _opp_queue('AAPL')
    result = build_cases(opp, graph, {}, {})
    assert result['case_count'] == 1
    case = result['cases'][0]
    assert case['overlap_type'] == 'instrument_overlap'
    assert case['no_execution'] is True
    assert 'AAPL' in case['justification']


def test_bucket_crowding_produces_case():
    """Candidate for a crowded bucket should produce case even without instrument overlap."""
    graph = _graph(
        thesis_nodes=[],
        bucket_util={'speculative_optionality': 0.9},
    )
    opp = _opp_queue('XYZ')
    result = build_cases(opp, graph, {}, {})
    assert result['case_count'] == 1
    assert result['cases'][0]['overlap_type'] == 'bucket_crowding'


def test_no_cases_for_non_candidate():
    """Suppressed candidates should not generate displacement cases."""
    graph = _graph(thesis_nodes=[
        {'node_type': 'thesis', 'node_id': 'thesis:AAPL', 'symbol': 'AAPL', 'bucket_ref': 'core_compounders'},
    ])
    opp = {'candidates': [
        {'candidate_id': 'opp:AAPL', 'instrument': 'AAPL', 'status': 'suppressed', 'score': 5.0},
    ]}
    result = build_cases(opp, graph, {}, {})
    assert result['case_count'] == 0


def test_all_cases_have_no_execution():
    graph = _graph(thesis_nodes=[
        {'node_type': 'thesis', 'node_id': 'thesis:AAPL', 'symbol': 'AAPL', 'bucket_ref': 'core_compounders'},
        {'node_type': 'thesis', 'node_id': 'thesis:GOOG', 'symbol': 'GOOG', 'bucket_ref': 'core_compounders'},
    ])
    opp = _opp_queue('AAPL', 'GOOG')
    result = build_cases(opp, graph, {}, {})
    for case in result['cases']:
        assert case['no_execution'] is True


def test_empty_graph_no_cases():
    result = build_cases(_opp_queue('XYZ'), _graph(), {}, {})
    assert result['case_count'] == 0
