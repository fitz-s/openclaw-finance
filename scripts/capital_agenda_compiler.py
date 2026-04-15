#!/usr/bin/env python3
"""Compile ranked CapitalAgenda from capital graph + displacement cases + thesis state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, POLICY_VERSION, load, now_iso, stable_id, write


CAPITAL_GRAPH = FINANCE / 'state' / 'capital-graph.json'
DISPLACEMENT_CASES = FINANCE / 'state' / 'displacement-cases.json'
SCENARIO_EXPOSURE = FINANCE / 'state' / 'scenario-exposure-matrix.json'
THESIS_REGISTRY = FINANCE / 'state' / 'thesis-registry.json'
INVALIDATOR_LEDGER = FINANCE / 'state' / 'invalidator-ledger.json'
OPPORTUNITY_QUEUE = FINANCE / 'state' / 'opportunity-queue.json'
OUT = FINANCE / 'state' / 'capital-agenda.json'

MAX_AGENDA_ITEMS = 8
MAX_DELIVERED = 5
MAX_PER_TYPE = 3  # ensure agenda type diversity


def displacement_items(
    displacement_cases: dict[str, Any],
    opportunity_queue: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate new_opportunity agenda items from displacement cases."""
    items: list[dict[str, Any]] = []
    candidates_by_id = {
        c.get('candidate_id'): c
        for c in opportunity_queue.get('candidates', [])
        if isinstance(c, dict) and c.get('candidate_id')
    }
    for case in displacement_cases.get('cases', []) if isinstance(displacement_cases.get('cases'), list) else []:
        if not isinstance(case, dict):
            continue
        candidate_ref = case.get('candidate_thesis_ref')
        candidate = candidates_by_id.get(candidate_ref, {})
        displaced_ref = case.get('displaced_thesis_ref')
        score = float(candidate.get('score') or 0) * 1.5  # displacement amplifier
        items.append({
            'agenda_id': stable_id('agenda', 'new_opportunity', candidate_ref, displaced_ref),
            'agenda_type': 'new_opportunity',
            'priority_score': round(score, 2),
            'linked_thesis_ids': [displaced_ref] if displaced_ref else [],
            'linked_positions': [],
            'linked_scenarios': [],
            'displacement_case_refs': [case.get('case_id')],
            'opportunity_cost_refs': [displaced_ref] if displaced_ref else [],
            'required_questions': [f"does {case.get('candidate_instrument')} justify displacing {case.get('displaced_instrument', 'existing')} exposure?"],
            'attention_justification': case.get('justification', ''),
            'no_execution': True,
        })
    return items


def invalidator_items(invalidator_ledger: dict[str, Any], thesis_registry: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate invalidator_escalation items from high-hit invalidators."""
    items: list[dict[str, Any]] = []
    theses_by_id = {
        t.get('thesis_id'): t
        for t in thesis_registry.get('theses', [])
        if isinstance(t, dict) and t.get('thesis_id')
    }
    for inv in invalidator_ledger.get('invalidators', []) if isinstance(invalidator_ledger.get('invalidators'), list) else []:
        if not isinstance(inv, dict) or inv.get('status') not in {'open', 'hit'}:
            continue
        hit_count = int(inv.get('hit_count') or 0)
        if hit_count < 3:
            continue
        target_id = inv.get('target_id')
        thesis = theses_by_id.get(target_id, {})
        score = hit_count * 2.0
        items.append({
            'agenda_id': stable_id('agenda', 'invalidator_escalation', inv.get('invalidator_id')),
            'agenda_type': 'invalidator_escalation',
            'priority_score': round(score, 2),
            'linked_thesis_ids': [target_id] if target_id else [],
            'linked_positions': [thesis.get('linked_position')] if thesis.get('linked_position') else [],
            'linked_scenarios': [],
            'displacement_case_refs': [],
            'opportunity_cost_refs': [],
            'required_questions': [f"is thesis {target_id} still valid after {hit_count} invalidator hits?"],
            'attention_justification': f"invalidator {inv.get('description', 'unknown')} has hit {hit_count} times",
            'no_execution': True,
        })
    return items


def hedge_gap_items(capital_graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate hedge_gap_alert items for uncovered buckets."""
    items: list[dict[str, Any]] = []
    coverage = capital_graph.get('hedge_coverage') if isinstance(capital_graph.get('hedge_coverage'), dict) else {}
    for bucket_id, status in coverage.items():
        if status not in {'uncovered', 'partial'}:
            continue
        util = capital_graph.get('bucket_utilization', {}).get(bucket_id, 0)
        if util <= 0:
            continue  # empty bucket, no gap to alert
        score = 3.0 if status == 'uncovered' else 1.5
        items.append({
            'agenda_id': stable_id('agenda', 'hedge_gap_alert', bucket_id),
            'agenda_type': 'hedge_gap_alert',
            'priority_score': round(score, 2),
            'linked_thesis_ids': [],
            'linked_positions': [],
            'linked_scenarios': [],
            'displacement_case_refs': [],
            'opportunity_cost_refs': [],
            'required_questions': [f"what hedge options exist for {bucket_id} ({status})?"],
            'attention_justification': f"{bucket_id} bucket has {status} hedge coverage",
            'no_execution': True,
        })
    return items


def crowding_items(capital_graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate exposure_crowding_warning for over-utilized buckets."""
    items: list[dict[str, Any]] = []
    util = capital_graph.get('bucket_utilization') if isinstance(capital_graph.get('bucket_utilization'), dict) else {}
    for bucket_id, utilization in util.items():
        if float(utilization) < 0.8:
            continue
        score = float(utilization) * 2.0
        bucket_node = None
        for n in capital_graph.get('nodes', []):
            if isinstance(n, dict) and n.get('node_type') == 'bucket' and n.get('bucket_id') == bucket_id:
                bucket_node = n
                break
        thesis_refs = bucket_node.get('current_thesis_refs', []) if bucket_node else []
        items.append({
            'agenda_id': stable_id('agenda', 'exposure_crowding', bucket_id),
            'agenda_type': 'exposure_crowding_warning',
            'priority_score': round(score, 2),
            'linked_thesis_ids': thesis_refs[:5],
            'linked_positions': [],
            'linked_scenarios': [],
            'displacement_case_refs': [],
            'opportunity_cost_refs': [],
            'required_questions': [f"should any thesis in {bucket_id} be retired to reduce crowding?"],
            'attention_justification': f"{bucket_id} at {utilization:.0%} utilization",
            'no_execution': True,
        })
    return items


def thesis_review_items(thesis_registry: dict[str, Any], invalidator_ledger: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate existing_thesis_review items for active theses with open invalidators."""
    items: list[dict[str, Any]] = []
    open_invalidator_targets = set()
    for inv in invalidator_ledger.get('invalidators', []) if isinstance(invalidator_ledger.get('invalidators'), list) else []:
        if isinstance(inv, dict) and inv.get('status') in {'open', 'hit'}:
            open_invalidator_targets.add(inv.get('target_id'))
    for thesis in thesis_registry.get('theses', []) if isinstance(thesis_registry.get('theses'), list) else []:
        if not isinstance(thesis, dict) or thesis.get('status') not in {'active', 'watch'}:
            continue
        if thesis.get('thesis_id') not in open_invalidator_targets:
            continue
        items.append({
            'agenda_id': stable_id('agenda', 'thesis_review', thesis.get('thesis_id')),
            'agenda_type': 'existing_thesis_review',
            'priority_score': 2.0 if thesis.get('status') == 'active' else 1.0,
            'linked_thesis_ids': [thesis.get('thesis_id')],
            'linked_positions': [thesis.get('linked_position')] if thesis.get('linked_position') else [],
            'linked_scenarios': thesis.get('scenario_refs', [])[:3],
            'displacement_case_refs': [],
            'opportunity_cost_refs': [],
            'required_questions': [f"review thesis {thesis.get('instrument')} against open invalidators"],
            'attention_justification': f"active thesis {thesis.get('instrument')} has open invalidators",
            'no_execution': True,
        })
    return items


def compile_agenda(
    capital_graph: dict[str, Any],
    displacement_cases: dict[str, Any],
    scenario_exposure: dict[str, Any],
    thesis_registry: dict[str, Any],
    invalidator_ledger: dict[str, Any],
    opportunity_queue: dict[str, Any],
) -> dict[str, Any]:
    all_items: list[dict[str, Any]] = []
    all_items.extend(displacement_items(displacement_cases, opportunity_queue))
    all_items.extend(invalidator_items(invalidator_ledger, thesis_registry))
    all_items.extend(hedge_gap_items(capital_graph))
    all_items.extend(crowding_items(capital_graph))
    all_items.extend(thesis_review_items(thesis_registry, invalidator_ledger))
    # Deduplicate by agenda_id
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in all_items:
        aid = item.get('agenda_id')
        if aid and aid not in seen:
            seen.add(aid)
            unique.append(item)
    # Rank by priority_score descending
    unique.sort(key=lambda item: float(item.get('priority_score') or 0), reverse=True)
    # Enforce type diversity: max MAX_PER_TYPE items per agenda_type
    type_counts: dict[str, int] = {}
    diverse: list[dict[str, Any]] = []
    for item in unique:
        atype = item.get('agenda_type', 'unknown')
        if type_counts.get(atype, 0) < MAX_PER_TYPE:
            diverse.append(item)
            type_counts[atype] = type_counts.get(atype, 0) + 1
    return {
        'generated_at': now_iso(),
        'policy_version': POLICY_VERSION,
        'capital_graph_hash': capital_graph.get('graph_hash'),
        'total_generated': len(unique),
        'max_delivered': MAX_DELIVERED,
        'agenda_items': diverse[:MAX_AGENDA_ITEMS],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--capital-graph', default=str(CAPITAL_GRAPH))
    parser.add_argument('--displacement-cases', default=str(DISPLACEMENT_CASES))
    parser.add_argument('--scenario-exposure', default=str(SCENARIO_EXPOSURE))
    parser.add_argument('--thesis-registry', default=str(THESIS_REGISTRY))
    parser.add_argument('--invalidator-ledger', default=str(INVALIDATOR_LEDGER))
    parser.add_argument('--opportunity-queue', default=str(OPPORTUNITY_QUEUE))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = compile_agenda(
        load(Path(args.capital_graph), {}) or {},
        load(Path(args.displacement_cases), {}) or {},
        load(Path(args.scenario_exposure), {}) or {},
        load(Path(args.thesis_registry), {}) or {},
        load(Path(args.invalidator_ledger), {}) or {},
        load(Path(args.opportunity_queue), {}) or {},
    )
    write(Path(args.out), payload)
    print(json.dumps({
        'status': 'pass',
        'agenda_count': len(payload['agenda_items']),
        'total_generated': payload['total_generated'],
        'out': str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
