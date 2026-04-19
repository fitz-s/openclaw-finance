#!/usr/bin/env python3
"""Track review-only source ROI and campaign outcomes.

This script writes advisory learning artifacts only. It does not mutate thresholds,
wake policy, delivery, or execution authority.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
SOURCE_HEALTH = Path('/Users/leofitz/.openclaw/workspace/services/market-ingest/state/source-health.json')
SOURCE_ATOMS = STATE / 'source-atoms' / 'latest.jsonl'
CLAIM_GRAPH = STATE / 'claim-graph.json'
CAMPAIGN_BOARD = STATE / 'campaign-board.json'
FOLLOWUP_ROUTE = STATE / 'followup-context-route.json'
SOURCE_ROI_HISTORY = STATE / 'source-roi-history.jsonl'
CAMPAIGN_OUTCOMES = STATE / 'campaign-outcomes.jsonl'
REPORT = STATE / 'source-roi-report.json'
POLICY_VERSION = 'source-roi-v1-review-only'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def health_map(source_health: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get('source_id')): row
        for row in source_health.get('sources', [])
        if isinstance(row, dict) and row.get('source_id')
    }


def atom_counts(atoms: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for atom in atoms:
        sid = str(atom.get('source_id') or 'source:unknown')
        counts[sid] = counts.get(sid, 0) + 1
    return counts


def claim_counts(claim_graph: dict[str, Any], atoms: list[dict[str, Any]]) -> dict[str, int]:
    atom_to_source = {str(atom.get('atom_id')): str(atom.get('source_id') or 'source:unknown') for atom in atoms}
    counts: dict[str, int] = {}
    for claim in claim_graph.get('claims', []) if isinstance(claim_graph.get('claims'), list) else []:
        sid = atom_to_source.get(str(claim.get('atom_id')), 'source:unknown')
        counts[sid] = counts.get(sid, 0) + 1
    return counts


def source_lane_sets(atoms: list[dict[str, Any]]) -> dict[str, list[str]]:
    lanes: dict[str, set[str]] = {}
    for atom in atoms:
        sid = str(atom.get('source_id') or 'source:unknown')
        lane = str(atom.get('source_lane') or atom.get('lane') or 'unknown')
        lanes.setdefault(sid, set()).add(lane)
    return {sid: sorted(values) for sid, values in lanes.items()}


def source_claim_refs(claim_graph: dict[str, Any], atoms: list[dict[str, Any]]) -> dict[str, list[str]]:
    atom_to_source = {str(atom.get('atom_id')): str(atom.get('source_id') or 'source:unknown') for atom in atoms}
    refs: dict[str, list[str]] = {}
    for claim in claim_graph.get('claims', []) if isinstance(claim_graph.get('claims'), list) else []:
        sid = atom_to_source.get(str(claim.get('atom_id')), 'source:unknown')
        if claim.get('claim_id'):
            refs.setdefault(sid, []).append(str(claim['claim_id']))
    return {sid: sorted(set(values)) for sid, values in refs.items()}


def campaign_source_counts(campaign_board: dict[str, Any], atoms: list[dict[str, Any]]) -> dict[str, int]:
    atom_to_source = {str(atom.get('atom_id')): str(atom.get('source_id') or 'source:unknown') for atom in atoms}
    counts: dict[str, int] = {}
    for campaign in campaign_board.get('campaigns', []) if isinstance(campaign_board.get('campaigns'), list) else []:
        for atom_id in campaign.get('linked_atoms', []) if isinstance(campaign.get('linked_atoms'), list) else []:
            sid = atom_to_source.get(str(atom_id))
            if sid:
                counts[sid] = counts.get(sid, 0) + 1
    return counts


def source_campaign_refs(campaign_board: dict[str, Any], atoms: list[dict[str, Any]]) -> dict[str, list[str]]:
    atom_to_source = {str(atom.get('atom_id')): str(atom.get('source_id') or 'source:unknown') for atom in atoms}
    refs: dict[str, list[str]] = {}
    for campaign in campaign_board.get('campaigns', []) if isinstance(campaign_board.get('campaigns'), list) else []:
        cid = str(campaign.get('campaign_id') or '')
        for atom_id in campaign.get('linked_atoms', []) if isinstance(campaign.get('linked_atoms'), list) else []:
            sid = atom_to_source.get(str(atom_id))
            if sid and cid:
                refs.setdefault(sid, []).append(cid)
    return {sid: sorted(set(values)) for sid, values in refs.items()}


def source_roi_rows(source_health: dict[str, Any], atoms: list[dict[str, Any]], claim_graph: dict[str, Any], campaign_board: dict[str, Any], generated_at: str | None = None) -> list[dict[str, Any]]:
    generated = generated_at or now_iso()
    health = health_map(source_health)
    a_counts = atom_counts(atoms)
    c_counts = claim_counts(claim_graph, atoms)
    camp_counts = campaign_source_counts(campaign_board, atoms)
    lanes = source_lane_sets(atoms)
    claim_refs = source_claim_refs(claim_graph, atoms)
    campaign_refs = source_campaign_refs(campaign_board, atoms)
    source_ids = sorted(set(health) | set(a_counts) | set(c_counts) | set(camp_counts) | set(lanes))
    rows = []
    for sid in source_ids:
        h = health.get(sid, {})
        freshness_status = h.get('freshness_status') or 'unknown'
        rights_status = h.get('rights_status') or 'unknown'
        freshness_penalty = 0.3 if freshness_status in {'stale', 'unknown'} else 0.0
        rights_penalty = 0.2 if rights_status in {'restricted', 'unknown'} else 0.0
        contribution = a_counts.get(sid, 0) + c_counts.get(sid, 0) * 2 + camp_counts.get(sid, 0) * 3
        score = max(0.0, round((contribution / 10) - freshness_penalty - rights_penalty, 3))
        campaign_value = round(camp_counts.get(sid, 0) * 0.5 + c_counts.get(sid, 0) * 0.2 + a_counts.get(sid, 0) * 0.1, 3)
        rows.append({
            'generated_at': generated,
            'source_id': sid,
            'source_lane_set': lanes.get(sid, []),
            'atom_count': a_counts.get(sid, 0),
            'claim_count': c_counts.get(sid, 0),
            'campaign_contribution_count': camp_counts.get(sid, 0),
            'claim_refs': claim_refs.get(sid, [])[:12],
            'campaign_refs': campaign_refs.get(sid, [])[:12],
            'freshness_status': freshness_status,
            'rights_status': rights_status,
            'marginal_value_score': score,
            'campaign_value_score': campaign_value,
            'false_positive_rate_proxy': None,
            'context_gap_closure_time_hours': None,
            'peacetime_to_live_conversion': False,
            'policy_version': POLICY_VERSION,
            'review_only': True,
            'no_threshold_mutation': True,
            'no_execution': True,
        })
    return rows


def campaign_outcome_rows(campaign_board: dict[str, Any], followup_route: dict[str, Any] | None = None, generated_at: str | None = None) -> list[dict[str, Any]]:
    generated = generated_at or now_iso()
    route = followup_route if isinstance(followup_route, dict) else {}
    primary = route.get('resolved_primary_handle') or route.get('primary_handle')
    rows = []
    for campaign in campaign_board.get('campaigns', []) if isinstance(campaign_board.get('campaigns'), list) else []:
        cid = str(campaign.get('campaign_id') or '')
        rows.append({
            'generated_at': generated,
            'campaign_id': cid,
            'human_title': campaign.get('human_title'),
            'board_class': campaign.get('board_class'),
            'stage': campaign.get('stage'),
            'stage_reason': campaign.get('stage_reason'),
            'source_diversity': campaign.get('source_diversity', 0),
            'cross_lane_confirmation': campaign.get('cross_lane_confirmation', 0),
            'known_unknown_count': len(campaign.get('known_unknowns', []) if isinstance(campaign.get('known_unknowns'), list) else []),
            'linked_claims': campaign.get('linked_claims', []) if isinstance(campaign.get('linked_claims'), list) else [],
            'linked_context_gaps': campaign.get('linked_context_gaps', []) if isinstance(campaign.get('linked_context_gaps'), list) else [],
            'peacetime_to_live_conversion': campaign.get('board_class') == 'live' and campaign.get('campaign_type') == 'peacetime_scout',
            'promotion_candidate': bool(campaign.get('promotion_candidate')),
            'followup_hit': primary == cid,
            'followup_verb': route.get('verb') if primary == cid else None,
            'evidence_slice_id': route.get('evidence_slice_id') if primary == cid else None,
            'review_only': True,
            'no_threshold_mutation': True,
            'no_execution': True,
        })
    return rows


def build_report(source_health: dict[str, Any], atoms: list[dict[str, Any]], claim_graph: dict[str, Any], campaign_board: dict[str, Any], followup_route: dict[str, Any] | None = None) -> dict[str, Any]:
    generated = now_iso()
    roi = source_roi_rows(source_health, atoms, claim_graph, campaign_board, generated_at=generated)
    outcomes = campaign_outcome_rows(campaign_board, followup_route, generated_at=generated)
    return {
        'generated_at': generated,
        'status': 'pass',
        'policy_version': POLICY_VERSION,
        'source_roi_rows': roi,
        'campaign_outcome_rows': outcomes,
        'summary': {
            'source_count': len(roi),
            'campaign_count': len(outcomes),
            'sources_with_campaign_contribution': sum(1 for row in roi if row['campaign_contribution_count'] > 0),
            'followup_hit_count': sum(1 for row in outcomes if row['followup_hit']),
        },
        'review_only': True,
        'no_threshold_mutation': True,
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-health', default=str(SOURCE_HEALTH))
    parser.add_argument('--atoms', default=str(SOURCE_ATOMS))
    parser.add_argument('--claim-graph', default=str(CLAIM_GRAPH))
    parser.add_argument('--campaign-board', default=str(CAMPAIGN_BOARD))
    parser.add_argument('--followup-route', default=str(FOLLOWUP_ROUTE))
    parser.add_argument('--source-roi-history', default=str(SOURCE_ROI_HISTORY))
    parser.add_argument('--campaign-outcomes', default=str(CAMPAIGN_OUTCOMES))
    parser.add_argument('--report', default=str(REPORT))
    parser.add_argument('--no-history', action='store_true')
    args = parser.parse_args(argv)
    for path in [Path(args.source_roi_history), Path(args.campaign_outcomes), Path(args.report)]:
        if not safe_state_path(path):
            print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_state_path']}, ensure_ascii=False))
            return 2
    report = build_report(
        load_json_safe(Path(args.source_health), {}) or {},
        load_jsonl(Path(args.atoms)),
        load_json_safe(Path(args.claim_graph), {}) or {},
        load_json_safe(Path(args.campaign_board), {}) or {},
        load_json_safe(Path(args.followup_route), {}) or {},
    )
    atomic_write_json(Path(args.report), report)
    if not args.no_history:
        append_jsonl(Path(args.source_roi_history), report['source_roi_rows'])
        append_jsonl(Path(args.campaign_outcomes), report['campaign_outcome_rows'])
    print(json.dumps({'status': report['status'], **report['summary'], 'report': args.report}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
