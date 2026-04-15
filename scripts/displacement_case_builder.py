#!/usr/bin/env python3
"""Build DisplacementCase objects for opportunity candidates with exposure overlap."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, POLICY_VERSION, load, now_iso, stable_id, write


OPPORTUNITY_QUEUE = FINANCE / 'state' / 'opportunity-queue.json'
CAPITAL_GRAPH = FINANCE / 'state' / 'capital-graph.json'
THESIS_REGISTRY = FINANCE / 'state' / 'thesis-registry.json'
SCENARIO_EXPOSURE = FINANCE / 'state' / 'scenario-exposure-matrix.json'
OUT = FINANCE / 'state' / 'displacement-cases.json'


def thesis_symbols(capital_graph: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Map symbol -> list of thesis nodes from the capital graph."""
    result: dict[str, list[dict[str, Any]]] = {}
    for n in capital_graph.get('nodes', []):
        if isinstance(n, dict) and n.get('node_type') == 'thesis' and n.get('symbol'):
            result.setdefault(n['symbol'], []).append(n)
    return result


def bucket_utilization(capital_graph: dict[str, Any]) -> dict[str, float]:
    """Map bucket_id -> utilization from capital graph."""
    return capital_graph.get('bucket_utilization') if isinstance(capital_graph.get('bucket_utilization'), dict) else {}


def hedge_coverage(capital_graph: dict[str, Any]) -> dict[str, str]:
    """Map bucket_id -> coverage status."""
    return capital_graph.get('hedge_coverage') if isinstance(capital_graph.get('hedge_coverage'), dict) else {}


def find_overlaps(
    candidate_symbol: str | None,
    candidate_theme: str | None,
    thesis_by_symbol: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Find existing theses that overlap with a candidate."""
    if not candidate_symbol:
        return []
    return thesis_by_symbol.get(candidate_symbol, [])


def assess_hedge_gap_impact(
    candidate_bucket: str,
    coverage: dict[str, str],
) -> str:
    """Assess whether adding to this bucket improves/worsens hedge coverage."""
    status = coverage.get(candidate_bucket, 'unknown')
    if status in {'uncovered', 'partial'}:
        return 'improves'
    if status == 'covered':
        return 'neutral'
    return 'neutral'


def build_cases(
    opportunity_queue: dict[str, Any],
    capital_graph: dict[str, Any],
    thesis_registry: dict[str, Any],
    scenario_exposure: dict[str, Any],
) -> dict[str, Any]:
    thesis_by_symbol = thesis_symbols(capital_graph)
    util = bucket_utilization(capital_graph)
    coverage = hedge_coverage(capital_graph)
    cases: list[dict[str, Any]] = []
    for candidate in opportunity_queue.get('candidates', []) if isinstance(opportunity_queue.get('candidates'), list) else []:
        if not isinstance(candidate, dict) or candidate.get('status') not in {'candidate', 'promoted'}:
            continue
        symbol = candidate.get('instrument')
        theme = candidate.get('theme')
        overlaps = find_overlaps(symbol, theme, thesis_by_symbol)
        # Check bucket crowding for the candidate's likely bucket
        candidate_bucket = 'speculative_optionality'  # default for unknown discovery
        bucket_util = util.get(candidate_bucket, 0)
        bucket_crowded = bucket_util >= 0.8
        if not overlaps and not bucket_crowded:
            # No overlap, no crowding — no displacement case needed
            continue
        for overlap in overlaps:
            cases.append({
                'case_id': stable_id('displacement', candidate.get('candidate_id'), overlap.get('node_id')),
                'candidate_thesis_ref': candidate.get('candidate_id'),
                'candidate_instrument': symbol,
                'candidate_theme': theme,
                'displaced_thesis_ref': overlap.get('node_id'),
                'displaced_instrument': overlap.get('symbol'),
                'bucket_ref': overlap.get('bucket_ref', candidate_bucket),
                'overlap_type': 'instrument_overlap',
                'exposure_delta': f"adds duplicate {symbol} exposure to {overlap.get('bucket_ref', 'unknown')} bucket",
                'hedge_gap_impact': assess_hedge_gap_impact(overlap.get('bucket_ref', candidate_bucket), coverage),
                'scenario_sensitivity_change': [],
                'justification': f"candidate {symbol} overlaps existing thesis {overlap.get('node_id')} in {overlap.get('bucket_ref', 'unknown')}",
                'no_execution': True,
            })
        if bucket_crowded and not overlaps:
            cases.append({
                'case_id': stable_id('displacement', candidate.get('candidate_id'), 'bucket_crowding', candidate_bucket),
                'candidate_thesis_ref': candidate.get('candidate_id'),
                'candidate_instrument': symbol,
                'candidate_theme': theme,
                'displaced_thesis_ref': None,
                'displaced_instrument': None,
                'bucket_ref': candidate_bucket,
                'overlap_type': 'bucket_crowding',
                'exposure_delta': f"{candidate_bucket} bucket at {bucket_util:.0%} utilization",
                'hedge_gap_impact': assess_hedge_gap_impact(candidate_bucket, coverage),
                'scenario_sensitivity_change': [],
                'justification': f"candidate would add to already-crowded {candidate_bucket} bucket ({bucket_util:.0%})",
                'no_execution': True,
            })
    return {
        'generated_at': now_iso(),
        'policy_version': POLICY_VERSION,
        'capital_graph_hash': capital_graph.get('graph_hash'),
        'case_count': len(cases),
        'cases': cases[:20],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--opportunity-queue', default=str(OPPORTUNITY_QUEUE))
    parser.add_argument('--capital-graph', default=str(CAPITAL_GRAPH))
    parser.add_argument('--thesis-registry', default=str(THESIS_REGISTRY))
    parser.add_argument('--scenario-exposure', default=str(SCENARIO_EXPOSURE))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = build_cases(
        load(Path(args.opportunity_queue), {}) or {},
        load(Path(args.capital_graph), {}) or {},
        load(Path(args.thesis_registry), {}) or {},
        load(Path(args.scenario_exposure), {}) or {},
    )
    write(Path(args.out), payload)
    print(json.dumps({
        'status': 'pass',
        'case_count': payload['case_count'],
        'out': str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
