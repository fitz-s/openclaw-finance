#!/usr/bin/env python3
"""Tests for capital_graph_compiler: deterministic hash stability, edge correctness, graceful degradation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from capital_graph_compiler import compile_graph, assign_bucket, graph_hash, build_nodes, build_edges


def _watch_intent(*items):
    return {'intents': [{'symbol': s, 'roles': r, 'intent_id': f'wi:{s}'} for s, r in items]}


def _thesis_registry(*items):
    return {'theses': [{'thesis_id': f'thesis:{s}', 'instrument': s, 'status': st, 'linked_watch_intent': f'wi:{s}'} for s, st in items]}


def _portfolio(stocks=None):
    return {'stocks': [{'symbol': s} for s in (stocks or [])], 'options': []}


def _scenarios(*items):
    return {'scenarios': [{'scenario_id': f'sc:{t}', 'title': t, 'scenario_type': 'macro', 'linked_thesis_ids': linked} for t, linked in items]}


def _invalidators(*items):
    return {'invalidators': [{'invalidator_id': f'inv:{i}', 'target_id': tid, 'status': 'open', 'hit_count': 1} for i, tid in enumerate(items)]}


def test_assign_bucket_held_core():
    assert assign_bucket('AAPL', ['held_core', 'event_sensitive'], []) == 'core_compounders'


def test_assign_bucket_cyclical():
    assert assign_bucket('LUMN', ['held_core'], []) == 'cyclical_beta'


def test_assign_bucket_hedge():
    assert assign_bucket('IAU', ['hedge', 'held_core'], []) == 'macro_hedges'


def test_assign_bucket_event():
    assert assign_bucket('INTC', ['event_sensitive'], []) == 'event_driven'


def test_assign_bucket_curiosity():
    assert assign_bucket('XYZ', ['curiosity'], []) == 'speculative_optionality'


def test_deterministic_hash_stability():
    """Same inputs must produce the same graph hash."""
    wi = _watch_intent(('AAPL', ['held_core']), ('GOOG', ['held_core', 'event_sensitive']))
    tr = _thesis_registry(('AAPL', 'active'), ('GOOG', 'watch'))
    pf = _portfolio(['AAPL', 'GOOG'])
    sc = _scenarios(('tech_rally', ['thesis:AAPL', 'thesis:GOOG']))
    inv = _invalidators('thesis:AAPL')
    g1 = compile_graph(wi, tr, pf, sc, inv, {})
    g2 = compile_graph(wi, tr, pf, sc, inv, {})
    assert g1['graph_hash'] == g2['graph_hash']
    assert g1['graph_hash'].startswith('sha256:')


def test_overlap_edges():
    """Two theses for the same instrument should produce an overlap edge."""
    wi = _watch_intent(('AAPL', ['held_core']))
    tr = {'theses': [
        {'thesis_id': 'thesis:A1', 'instrument': 'AAPL', 'status': 'active'},
        {'thesis_id': 'thesis:A2', 'instrument': 'AAPL', 'status': 'watch'},
    ]}
    pf = _portfolio()
    sc = _scenarios()
    inv = {'invalidators': []}
    g = compile_graph(wi, tr, pf, sc, inv, {})
    overlap_edges = [e for e in g['edges'] if e['edge_type'] == 'overlap']
    assert len(overlap_edges) == 1
    assert overlap_edges[0]['instrument'] == 'AAPL'


def test_dependency_edges():
    """Theses sharing a scenario should produce dependency edges."""
    wi = _watch_intent(('AAPL', ['held_core']), ('GOOG', ['held_core']))
    tr = _thesis_registry(('AAPL', 'active'), ('GOOG', 'active'))
    pf = _portfolio()
    sc = _scenarios(('tech_rally', ['thesis:AAPL', 'thesis:GOOG']))
    inv = {'invalidators': []}
    g = compile_graph(wi, tr, pf, sc, inv, {})
    dep_edges = [e for e in g['edges'] if e['edge_type'] == 'dependency']
    assert len(dep_edges) == 1


def test_invalidation_edges():
    wi = _watch_intent(('AAPL', ['held_core']))
    tr = _thesis_registry(('AAPL', 'active'))
    pf = _portfolio()
    sc = _scenarios()
    inv = _invalidators('thesis:AAPL')
    g = compile_graph(wi, tr, pf, sc, inv, {})
    inv_edges = [e for e in g['edges'] if e['edge_type'] == 'invalidation']
    assert len(inv_edges) == 1


def test_empty_inputs():
    """Empty inputs should produce a valid graph with bucket nodes only."""
    g = compile_graph({}, {}, {}, {}, {}, {})
    assert g['graph_hash'].startswith('sha256:')
    assert g['node_count'] >= 5  # 5 default bucket nodes
    assert g['edge_count'] == 0


def test_hedge_coverage():
    wi = _watch_intent(('IAU', ['hedge', 'held_core']))
    tr = _thesis_registry(('IAU', 'active'))
    pf = _portfolio(['IAU'])
    sc = _scenarios()
    inv = {'invalidators': []}
    g = compile_graph(wi, tr, pf, sc, inv, {})
    assert 'macro_hedges' in g['hedge_coverage']
