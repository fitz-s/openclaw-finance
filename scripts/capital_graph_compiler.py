#!/usr/bin/env python3
"""Compile deterministic CapitalGraph from thesis spine + portfolio state."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, POLICY_VERSION, load, now_iso, write


WATCH_INTENT = FINANCE / 'state' / 'watch-intent.json'
THESIS_REGISTRY = FINANCE / 'state' / 'thesis-registry.json'
PORTFOLIO = FINANCE / 'state' / 'portfolio-resolved.json'
SCENARIO_CARDS = FINANCE / 'state' / 'scenario-cards.json'
INVALIDATOR_LEDGER = FINANCE / 'state' / 'invalidator-ledger.json'
BUCKET_CONFIG = FINANCE / 'state' / 'capital-bucket-config.json'
OUT = FINANCE / 'state' / 'capital-graph.json'

DEFAULT_BUCKETS = [
    {'bucket_id': 'core_compounders', 'role_mapping': ['held_core'], 'max_thesis_slots': 8},
    {'bucket_id': 'cyclical_beta', 'role_mapping': ['held_core'], 'max_thesis_slots': 4},
    {'bucket_id': 'macro_hedges', 'role_mapping': ['hedge', 'macro_proxy'], 'max_thesis_slots': 4},
    {'bucket_id': 'event_driven', 'role_mapping': ['event_sensitive'], 'max_thesis_slots': 4},
    {'bucket_id': 'speculative_optionality', 'role_mapping': ['curiosity'], 'max_thesis_slots': 3},
]

CYCLICAL_SYMBOLS = {'USO', 'XLE', 'XLF', 'XLB', 'XLI', 'XLP', 'XLU', 'XLY', 'LUMN', 'RGTI'}


def load_buckets(config: dict[str, Any]) -> list[dict[str, Any]]:
    buckets = config.get('buckets') if isinstance(config.get('buckets'), list) else None
    return buckets or DEFAULT_BUCKETS


def intent_roles(watch_intent: dict[str, Any]) -> dict[str, list[str]]:
    """Map symbol -> roles from watch intent."""
    return {
        item.get('symbol'): item.get('roles', [])
        for item in watch_intent.get('intents', [])
        if isinstance(item, dict) and item.get('symbol')
    }


def assign_bucket(symbol: str, roles: list[str], buckets: list[dict[str, Any]]) -> str:
    """Deterministic bucket assignment from roles."""
    role_set = set(roles)
    if 'hedge' in role_set or 'macro_proxy' in role_set:
        return 'macro_hedges'
    if 'held_core' in role_set:
        if symbol in CYCLICAL_SYMBOLS:
            return 'cyclical_beta'
        return 'core_compounders'
    if 'event_sensitive' in role_set:
        return 'event_driven'
    return 'speculative_optionality'


def build_nodes(
    thesis_registry: dict[str, Any],
    portfolio: dict[str, Any],
    scenario_cards: dict[str, Any],
    roles_map: dict[str, list[str]],
    buckets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    # Position nodes from portfolio
    for stock in portfolio.get('stocks', []) if isinstance(portfolio.get('stocks'), list) else []:
        if isinstance(stock, dict) and stock.get('symbol'):
            nodes.append({
                'node_type': 'position',
                'node_id': f"pos:{stock['symbol']}",
                'symbol': stock['symbol'],
                'position_type': 'stock',
            })
    for option in portfolio.get('options', []) if isinstance(portfolio.get('options'), list) else []:
        if isinstance(option, dict):
            symbol = option.get('underlying') or option.get('symbol')
            if symbol:
                nodes.append({
                    'node_type': 'position',
                    'node_id': f"pos:opt:{symbol}",
                    'symbol': symbol,
                    'position_type': 'option',
                })
    # Thesis nodes
    for thesis in thesis_registry.get('theses', []) if isinstance(thesis_registry.get('theses'), list) else []:
        if not isinstance(thesis, dict) or not thesis.get('thesis_id'):
            continue
        if thesis.get('status') in {'suppressed', 'retired'}:
            continue
        instrument = thesis.get('instrument')
        roles = roles_map.get(instrument, [])
        bucket = assign_bucket(instrument or '', roles, buckets)
        nodes.append({
            'node_type': 'thesis',
            'node_id': thesis['thesis_id'],
            'symbol': instrument,
            'status': thesis.get('status'),
            'bucket_ref': bucket,
            'roles': roles,
        })
    # Scenario nodes
    for scenario in scenario_cards.get('scenarios', []) if isinstance(scenario_cards.get('scenarios'), list) else []:
        if isinstance(scenario, dict) and scenario.get('scenario_id'):
            nodes.append({
                'node_type': 'scenario',
                'node_id': scenario['scenario_id'],
                'title': scenario.get('title'),
                'scenario_type': scenario.get('scenario_type'),
                'linked_thesis_ids': scenario.get('linked_thesis_ids', []),
            })
    # Bucket nodes
    for bucket in buckets:
        thesis_refs = [n['node_id'] for n in nodes if n.get('node_type') == 'thesis' and n.get('bucket_ref') == bucket['bucket_id']]
        position_refs = [n['symbol'] for n in nodes if n.get('node_type') == 'position']
        nodes.append({
            'node_type': 'bucket',
            'node_id': f"bucket:{bucket['bucket_id']}",
            'bucket_id': bucket['bucket_id'],
            'max_thesis_slots': bucket.get('max_thesis_slots', 5),
            'current_thesis_refs': thesis_refs,
            'utilization': len(thesis_refs) / max(bucket.get('max_thesis_slots', 5), 1),
        })
    return nodes


def build_edges(
    nodes: list[dict[str, Any]],
    invalidator_ledger: dict[str, Any],
) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    thesis_nodes = [n for n in nodes if n.get('node_type') == 'thesis']
    position_nodes = [n for n in nodes if n.get('node_type') == 'position']
    position_symbols = {n['symbol'] for n in position_nodes if n.get('symbol')}
    # Overlap edges: theses sharing the same instrument
    by_symbol: dict[str, list[dict[str, Any]]] = {}
    for t in thesis_nodes:
        sym = t.get('symbol')
        if sym:
            by_symbol.setdefault(sym, []).append(t)
    for sym, group in by_symbol.items():
        if len(group) > 1:
            for i, a in enumerate(group):
                for b in group[i + 1:]:
                    edges.append({
                        'edge_type': 'overlap',
                        'source': a['node_id'],
                        'target': b['node_id'],
                        'instrument': sym,
                    })
    # Hedge edges: thesis with hedge/macro_proxy role covers a position
    for t in thesis_nodes:
        if t.get('symbol') in position_symbols:
            role_set = set(t.get('roles', []))
            if 'hedge' in role_set or 'macro_proxy' in role_set:
                for p in position_nodes:
                    edges.append({
                        'edge_type': 'hedge',
                        'source': t['node_id'],
                        'target': p.get('node_id'),
                        'instrument': t.get('symbol'),
                    })
    # Dependency edges: theses sharing scenario_refs
    scenario_nodes = [n for n in nodes if n.get('node_type') == 'scenario']
    for s in scenario_nodes:
        linked = s.get('linked_thesis_ids', [])
        if len(linked) > 1:
            for i, a_id in enumerate(linked):
                for b_id in linked[i + 1:]:
                    edges.append({
                        'edge_type': 'dependency',
                        'source': a_id,
                        'target': b_id,
                        'scenario': s['node_id'],
                    })
    # Invalidation edges
    for inv in invalidator_ledger.get('invalidators', []) if isinstance(invalidator_ledger.get('invalidators'), list) else []:
        if not isinstance(inv, dict) or inv.get('status') not in {'open', 'hit'}:
            continue
        target_id = inv.get('target_id')
        if target_id:
            edges.append({
                'edge_type': 'invalidation',
                'source': inv.get('invalidator_id'),
                'target': target_id,
                'status': inv.get('status'),
                'hit_count': inv.get('hit_count', 1),
            })
    return edges


def compute_hedge_coverage(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, str]:
    """Per-bucket hedge coverage status."""
    bucket_nodes = [n for n in nodes if n.get('node_type') == 'bucket']
    hedge_edges = {e['target'] for e in edges if e.get('edge_type') == 'hedge'}
    result: dict[str, str] = {}
    for b in bucket_nodes:
        bucket_id = b.get('bucket_id', '')
        thesis_refs = b.get('current_thesis_refs', [])
        if not thesis_refs:
            result[bucket_id] = 'not_applicable'
        elif all(ref in hedge_edges for ref in thesis_refs):
            result[bucket_id] = 'covered'
        elif any(ref in hedge_edges for ref in thesis_refs):
            result[bucket_id] = 'partial'
        else:
            result[bucket_id] = 'uncovered'
    return result


def graph_hash(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    raw = json.dumps({'nodes': nodes, 'edges': edges}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def compile_graph(
    watch_intent: dict[str, Any],
    thesis_registry: dict[str, Any],
    portfolio: dict[str, Any],
    scenario_cards: dict[str, Any],
    invalidator_ledger: dict[str, Any],
    bucket_config: dict[str, Any],
) -> dict[str, Any]:
    buckets = load_buckets(bucket_config)
    roles_map = intent_roles(watch_intent)
    nodes = build_nodes(thesis_registry, portfolio, scenario_cards, roles_map, buckets)
    edges = build_edges(nodes, invalidator_ledger)
    hedge_coverage = compute_hedge_coverage(nodes, edges)
    return {
        'generated_at': now_iso(),
        'policy_version': POLICY_VERSION,
        'graph_hash': graph_hash(nodes, edges),
        'node_count': len(nodes),
        'edge_count': len(edges),
        'nodes': nodes,
        'edges': edges,
        'hedge_coverage': hedge_coverage,
        'bucket_utilization': {
            n['bucket_id']: n.get('utilization', 0)
            for n in nodes if n.get('node_type') == 'bucket'
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch-intent', default=str(WATCH_INTENT))
    parser.add_argument('--thesis-registry', default=str(THESIS_REGISTRY))
    parser.add_argument('--portfolio', default=str(PORTFOLIO))
    parser.add_argument('--scenario-cards', default=str(SCENARIO_CARDS))
    parser.add_argument('--invalidator-ledger', default=str(INVALIDATOR_LEDGER))
    parser.add_argument('--bucket-config', default=str(BUCKET_CONFIG))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = compile_graph(
        load(Path(args.watch_intent), {}) or {},
        load(Path(args.thesis_registry), {}) or {},
        load(Path(args.portfolio), {}) or {},
        load(Path(args.scenario_cards), {}) or {},
        load(Path(args.invalidator_ledger), {}) or {},
        load(Path(args.bucket_config), {}) or {},
    )
    write(Path(args.out), payload)
    print(json.dumps({
        'status': 'pass',
        'graph_hash': payload['graph_hash'],
        'node_count': payload['node_count'],
        'edge_count': payload['edge_count'],
        'out': str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
