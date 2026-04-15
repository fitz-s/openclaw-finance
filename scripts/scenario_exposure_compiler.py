#!/usr/bin/env python3
"""Compile scenario-exposure matrix from scenario cards + capital graph."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, POLICY_VERSION, load, now_iso, write


SCENARIO_CARDS = FINANCE / 'state' / 'scenario-cards.json'
THESIS_REGISTRY = FINANCE / 'state' / 'thesis-registry.json'
CAPITAL_GRAPH = FINANCE / 'state' / 'capital-graph.json'
PORTFOLIO = FINANCE / 'state' / 'portfolio-resolved.json'
OUT = FINANCE / 'state' / 'scenario-exposure-matrix.json'


def thesis_bucket_map(capital_graph: dict[str, Any]) -> dict[str, str]:
    """Map thesis_id -> bucket_id from capital graph nodes."""
    return {
        n['node_id']: n.get('bucket_ref', 'unknown')
        for n in capital_graph.get('nodes', [])
        if isinstance(n, dict) and n.get('node_type') == 'thesis'
    }


def compute_crowding(linked_thesis_ids: list[str], thesis_buckets: dict[str, str]) -> dict[str, int]:
    """Count how many linked theses fall in each bucket."""
    counts: dict[str, int] = {}
    for tid in linked_thesis_ids:
        bucket = thesis_buckets.get(tid, 'unknown')
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def compute_sensitivity(scenario: dict[str, Any], thesis_buckets: dict[str, str], hedge_coverage: dict[str, str]) -> dict[str, Any]:
    """Compute per-bucket sensitivity for one scenario."""
    linked = scenario.get('linked_thesis_ids', []) if isinstance(scenario.get('linked_thesis_ids'), list) else []
    crowding = compute_crowding(linked, thesis_buckets)
    sensitivity: dict[str, Any] = {}
    for bucket_id, count in crowding.items():
        sensitivity[bucket_id] = {
            'thesis_count': count,
            'crowding_risk': 'high' if count >= 3 else 'moderate' if count >= 2 else 'low',
            'hedge_coverage': hedge_coverage.get(bucket_id, 'unknown'),
        }
    return sensitivity


def compile_matrix(
    scenario_cards: dict[str, Any],
    thesis_registry: dict[str, Any],
    capital_graph: dict[str, Any],
    portfolio: dict[str, Any],
) -> dict[str, Any]:
    thesis_buckets = thesis_bucket_map(capital_graph)
    hedge_coverage = capital_graph.get('hedge_coverage') if isinstance(capital_graph.get('hedge_coverage'), dict) else {}
    rows: list[dict[str, Any]] = []
    for scenario in scenario_cards.get('scenarios', []) if isinstance(scenario_cards.get('scenarios'), list) else []:
        if not isinstance(scenario, dict) or not scenario.get('scenario_id'):
            continue
        if scenario.get('status') in {'retired'}:
            continue
        linked = scenario.get('linked_thesis_ids', []) if isinstance(scenario.get('linked_thesis_ids'), list) else []
        sensitivity = compute_sensitivity(scenario, thesis_buckets, hedge_coverage)
        crowding = compute_crowding(linked, thesis_buckets)
        max_crowding = max(crowding.values()) if crowding else 0
        rows.append({
            'scenario_id': scenario['scenario_id'],
            'title': scenario.get('title'),
            'scenario_type': scenario.get('scenario_type'),
            'status': scenario.get('status'),
            'linked_thesis_count': len(linked),
            'bucket_sensitivity': sensitivity,
            'max_crowding': max_crowding,
            'crowding_risk': 'high' if max_crowding >= 3 else 'moderate' if max_crowding >= 2 else 'low',
        })
    return {
        'generated_at': now_iso(),
        'policy_version': POLICY_VERSION,
        'capital_graph_hash': capital_graph.get('graph_hash'),
        'scenario_count': len(rows),
        'matrix': rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario-cards', default=str(SCENARIO_CARDS))
    parser.add_argument('--thesis-registry', default=str(THESIS_REGISTRY))
    parser.add_argument('--capital-graph', default=str(CAPITAL_GRAPH))
    parser.add_argument('--portfolio', default=str(PORTFOLIO))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = compile_matrix(
        load(Path(args.scenario_cards), {}) or {},
        load(Path(args.thesis_registry), {}) or {},
        load(Path(args.capital_graph), {}) or {},
        load(Path(args.portfolio), {}) or {},
    )
    write(Path(args.out), payload)
    print(json.dumps({
        'status': 'pass',
        'scenario_count': payload['scenario_count'],
        'out': str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
