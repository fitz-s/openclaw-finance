#!/usr/bin/env python3
"""Compile bounded inputs for the capital committee sidecar."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, POLICY_VERSION, load, now_iso, write


CAPITAL_AGENDA = FINANCE / 'state' / 'capital-agenda.json'
DISPLACEMENT_CASES = FINANCE / 'state' / 'displacement-cases.json'
INVALIDATOR_LEDGER = FINANCE / 'state' / 'invalidator-ledger.json'
CAPITAL_GRAPH = FINANCE / 'state' / 'capital-graph.json'
OUT = FINANCE / 'state' / 'capital-committee-packet.json'

MAX_AGENDA_ITEMS = 5
MAX_DISPLACEMENT_CASES = 5
MAX_INVALIDATOR_CLUSTERS = 3


def build_packet(
    capital_agenda: dict[str, Any],
    displacement_cases: dict[str, Any],
    invalidator_ledger: dict[str, Any],
    capital_graph: dict[str, Any],
) -> dict[str, Any]:
    agenda_items = capital_agenda.get('agenda_items', []) if isinstance(capital_agenda.get('agenda_items'), list) else []
    cases = displacement_cases.get('cases', []) if isinstance(displacement_cases.get('cases'), list) else []
    invalidators = [
        inv for inv in invalidator_ledger.get('invalidators', [])
        if isinstance(inv, dict) and inv.get('status') in {'open', 'hit'}
    ]
    invalidators.sort(key=lambda x: int(x.get('hit_count') or 0), reverse=True)
    return {
        'generated_at': now_iso(),
        'policy_version': POLICY_VERSION,
        'committee_scope': 'bounded_capital_review_only',
        'capital_graph_hash': capital_graph.get('graph_hash'),
        'selected_agenda_items': agenda_items[:MAX_AGENDA_ITEMS],
        'selected_displacement_cases': cases[:MAX_DISPLACEMENT_CASES],
        'selected_invalidator_clusters': invalidators[:MAX_INVALIDATOR_CLUSTERS],
        'hedge_coverage': capital_graph.get('hedge_coverage', {}),
        'bucket_utilization': capital_graph.get('bucket_utilization', {}),
        'forbidden_actions': [
            'no_user_delivery',
            'no_execution',
            'no_threshold_mutation',
            'no_live_authority_change',
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--capital-agenda', default=str(CAPITAL_AGENDA))
    parser.add_argument('--displacement-cases', default=str(DISPLACEMENT_CASES))
    parser.add_argument('--invalidator-ledger', default=str(INVALIDATOR_LEDGER))
    parser.add_argument('--capital-graph', default=str(CAPITAL_GRAPH))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = build_packet(
        load(Path(args.capital_agenda), {}) or {},
        load(Path(args.displacement_cases), {}) or {},
        load(Path(args.invalidator_ledger), {}) or {},
        load(Path(args.capital_graph), {}) or {},
    )
    write(Path(args.out), payload)
    print(json.dumps({
        'status': 'pass',
        'agenda_count': len(payload['selected_agenda_items']),
        'case_count': len(payload['selected_displacement_cases']),
        'out': str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
