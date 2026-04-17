#!/usr/bin/env python3
"""Compile durable undercurrent cards from existing finance state.

This is an operator projection only. It does not change thresholds, judgments,
or execution authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
INVALIDATORS = STATE / 'invalidator-ledger.json'
OPPORTUNITIES = STATE / 'opportunity-queue.json'
CAPITAL_GRAPH = STATE / 'capital-graph.json'
SOURCE_HEALTH = STATE / 'source-health.json'
SOURCE_ATOMS = STATE / 'source-atoms' / 'latest.jsonl'
CLAIM_GRAPH = STATE / 'claim-graph.json'
CONTEXT_GAPS = STATE / 'context-gaps.json'
OUT = STATE / 'undercurrents.json'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(p or '') for p in parts)
    return f'{prefix}:{hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]}'


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
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


def short_text(value: Any, limit: int = 96) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + '…'


def humanize_signal(value: Any) -> str:
    text = str(value or '').strip()
    if text.startswith('direction_conflict:theme:'):
        key = text.split(':')[-1]
        labels = {
            'unknown_discovery': '未知发现方向冲突',
            'broad_market': '大盘方向冲突',
            'sector': '板块方向冲突',
            'commodity': '商品方向冲突',
            'commodity_pressure_proxy': '商品压力冲突',
            'sector_rotation_proxy': '板块轮动冲突',
            'options_unusual_activity_proxy': '期权异动冲突',
        }
        return labels.get(key, key.replace('_', ' ') + ' 冲突')
    if text == 'source outage':
        return '数据源中断'
    if text == 'official correction':
        return '官方修正反证'
    if text == 'packet staleness':
        return 'Packet 新鲜度反证'
    return text.replace('_', ' ')


def source_freshness_from_refs(refs: list[Any]) -> dict[str, Any]:
    source_refs = [str(ref) for ref in refs if ref]
    if not source_refs:
        status = 'unknown'
    elif any(ref.startswith('state:') for ref in source_refs) and any(ref.startswith('http') for ref in source_refs):
        status = 'mixed'
    elif all(ref.startswith('state:') for ref in source_refs):
        status = 'mixed'
    else:
        status = 'fresh'
    return {'status': status, 'source_refs': source_refs[:8]}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def normalized_persistence(card: dict[str, Any]) -> float:
    return clamp(float(card.get('persistence_score') or 0) / 20)


def normalized_acceleration(card: dict[str, Any]) -> float:
    return clamp(float(card.get('acceleration_score') or card.get('velocity') or 0) / 10)


def capital_relevance_score(card: dict[str, Any]) -> float:
    refs = card.get('linked_refs') if isinstance(card.get('linked_refs'), dict) else {}
    source_type = str(card.get('source_type') or '')
    if source_type in {'hedge_gap', 'crowding'} or as_list(refs.get('capital_graph')):
        return 0.8
    if as_list(refs.get('opportunity')) or as_list(refs.get('invalidator')):
        return 0.65
    if as_list(refs.get('thesis')) or as_list(refs.get('scenario')):
        return 0.55
    return 0.35


def freshness_penalty(card: dict[str, Any]) -> float:
    status = str((card.get('source_freshness') or {}).get('status') or 'unknown')
    health = card.get('source_health_summary') if isinstance(card.get('source_health_summary'), dict) else {}
    degraded = int(health.get('degraded_count') or 0)
    quota = int(health.get('quota_degraded_count') or 0)
    unavailable = int(health.get('unavailable_count') or 0)
    penalty = 0.0
    if status == 'mixed':
        penalty += 0.2
    elif status == 'stale':
        penalty += 0.5
    elif status == 'unknown':
        penalty += 0.3
    penalty += min(degraded, 5) * 0.08
    penalty += min(quota + unavailable, 5) * 0.06
    return clamp(penalty)


def score_and_gate(card: dict[str, Any]) -> dict[str, Any]:
    card = dict(card)
    cross_lane_score = clamp(float(card.get('cross_lane_confirmation') or 0) / 3)
    contradiction_score = clamp(float(card.get('contradiction_load') or 0) / 5)
    capital_score = capital_relevance_score(card)
    fresh_penalty = freshness_penalty(card)
    persistence = normalized_persistence(card)
    acceleration = normalized_acceleration(card)
    score = (
        0.28 * persistence
        + 0.18 * acceleration
        + 0.24 * cross_lane_score
        + 0.20 * capital_score
        - 0.15 * contradiction_score
        - 0.10 * fresh_penalty
    )
    blockers: list[str] = []
    if int(card.get('source_diversity') or 0) < 2:
        blockers.append('source_diversity_lt_2')
    if cross_lane_score < 0.45:
        blockers.append('cross_lane_confirmation_lt_0.45')
    if contradiction_score > 0.35:
        blockers.append('contradiction_load_gt_0.35')
    if capital_score < 0.50:
        blockers.append('capital_relevance_lt_0.50')
    if persistence < 0.55:
        blockers.append('persistence_score_lt_0.55')
    if fresh_penalty >= 0.50:
        blockers.append('freshness_penalty_high')
    card.update({
        'undercurrent_score': round(clamp(score), 4),
        'cross_lane_confirmation_score': round(cross_lane_score, 4),
        'contradiction_load_score': round(contradiction_score, 4),
        'capital_relevance_score': round(capital_score, 4),
        'freshness_penalty': round(fresh_penalty, 4),
        'promotion_candidate': not blockers,
        'promotion_blockers': blockers,
        'peacetime_update_eligible': True,
        'packet_update_visibility': 'board_mutation_only',
        'wake_impact': 'none',
    })
    return card


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def shadow_context(
    *,
    source_health: dict[str, Any] | None = None,
    atoms: list[dict[str, Any]] | None = None,
    claim_graph: dict[str, Any] | None = None,
    context_gaps: dict[str, Any] | None = None,
) -> dict[str, Any]:
    atoms = atoms or []
    claims = [
        claim for claim in as_list((claim_graph or {}).get('claims'))
        if isinstance(claim, dict) and claim.get('claim_id')
    ]
    gaps = [
        gap for gap in as_list((context_gaps or {}).get('gaps'))
        if isinstance(gap, dict) and gap.get('gap_id')
    ]
    health_rows = [
        row for row in as_list((source_health or {}).get('sources'))
        if isinstance(row, dict) and row.get('source_id')
    ]
    return {
        'atoms': atoms,
        'claims': claims,
        'gaps': gaps,
        'health_rows': health_rows,
        'atom_by_id': {str(atom.get('atom_id')): atom for atom in atoms if isinstance(atom, dict) and atom.get('atom_id')},
        'gaps_by_claim': {
            str(claim_id): [gap for gap in gaps if str(gap.get('claim_id')) == str(claim_id)]
            for claim_id in {gap.get('claim_id') for gap in gaps}
        },
        'health_by_source': {str(row.get('source_id')): row for row in health_rows},
        'shadow_inputs': {
            'source_health': bool(source_health),
            'source_atoms': bool(atoms),
            'claim_graph': bool(claim_graph),
            'context_gaps': bool(context_gaps),
        },
    }


def claim_matches_text(claim: dict[str, Any], text: str) -> bool:
    if not text:
        return False
    haystack = ' '.join(str(claim.get(key) or '') for key in ['subject', 'object', 'predicate', 'event_class']).lower()
    tokens = {token for token in text.lower().replace('|', ' ').replace('/', ' ').split() if len(token) >= 3}
    return bool(tokens and any(token in haystack for token in tokens))


def relevant_claims(card: dict[str, Any], ctx: dict[str, Any]) -> list[dict[str, Any]]:
    claims = ctx.get('claims', [])
    refs = card.get('linked_refs') if isinstance(card.get('linked_refs'), dict) else {}
    text_parts = [
        card.get('human_title'),
        card.get('promotion_reason'),
        ' '.join(str(item) for item in as_list(refs.get('opportunity'))),
        ' '.join(str(item) for item in as_list(refs.get('invalidator'))),
        ' '.join(str(item) for item in as_list(refs.get('thesis'))),
    ]
    text = ' '.join(str(part or '') for part in text_parts)
    matched = [claim for claim in claims if claim_matches_text(claim, text)]
    if not matched and claims and card.get('source_type') in {'invalidator_cluster', 'opportunity_accumulation'}:
        matched = claims[:5]
    return matched[:12]


def enrich_with_shadow_context(card: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    card = dict(card)
    refs = dict(card.get('linked_refs') if isinstance(card.get('linked_refs'), dict) else {})
    claims = relevant_claims(card, ctx)
    atom_ids = sorted({str(claim.get('atom_id')) for claim in claims if claim.get('atom_id')})
    atoms = [ctx.get('atom_by_id', {}).get(atom_id) for atom_id in atom_ids]
    atoms = [atom for atom in atoms if isinstance(atom, dict)]
    claim_ids = sorted({str(claim.get('claim_id')) for claim in claims if claim.get('claim_id')})
    gaps = []
    for claim_id in claim_ids:
        gaps.extend(ctx.get('gaps_by_claim', {}).get(claim_id, []))
    source_ids = sorted({str(atom.get('source_id')) for atom in atoms if atom.get('source_id')})
    source_lanes = sorted({str(atom.get('source_lane')) for atom in atoms if atom.get('source_lane')})
    source_health_rows = [ctx.get('health_by_source', {}).get(source_id) for source_id in source_ids]
    source_health_rows = [row for row in source_health_rows if isinstance(row, dict)]
    degraded_sources = [
        row for row in source_health_rows
        if row.get('freshness_status') in {'stale', 'unknown'}
        or row.get('rights_status') in {'restricted', 'unknown'}
        or row.get('quota_status') == 'degraded'
        or row.get('coverage_status') == 'unavailable'
    ]
    quota_degraded_sources = [row for row in source_health_rows if row.get('quota_status') == 'degraded']
    unavailable_sources = [row for row in source_health_rows if row.get('coverage_status') == 'unavailable']
    contradiction_load = sum(1 for claim in claims if as_list(claim.get('contradicts')))
    claim_persistence = len(claim_ids)
    known_unknowns = [
        {
            'gap_id': gap.get('gap_id'),
            'missing_lane': gap.get('missing_lane'),
            'why_load_bearing': short_text(gap.get('why_load_bearing'), 120),
            'cost_of_ignorance': gap.get('cost_of_ignorance'),
            'subject': gap.get('subject'),
        }
        for gap in gaps[:5]
        if isinstance(gap, dict)
    ]
    refs['atom'] = atom_ids[:8]
    refs['claim'] = claim_ids[:8]
    refs['context_gap'] = [str(gap.get('gap_id')) for gap in gaps[:8] if gap.get('gap_id')]
    card['linked_refs'] = refs
    card['acceleration_score'] = round(float(card.get('velocity') or 0) + max(0, len(claims) - 1) * 0.25, 2)
    card['cross_lane_confirmation'] = len(source_lanes)
    card['source_diversity'] = len(source_ids)
    card['contradiction_load'] = contradiction_load
    card['known_unknowns'] = known_unknowns
    card['source_health_refs'] = [str(row.get('source_id')) for row in source_health_rows[:8]]
    card['shadow_inputs'] = dict(ctx.get('shadow_inputs') or {})
    card['source_health_summary'] = {
        'degraded_count': len(degraded_sources),
        'degraded_sources': [str(row.get('source_id')) for row in degraded_sources[:5]],
        'quota_degraded_count': len(quota_degraded_sources),
        'unavailable_count': len(unavailable_sources),
        'degraded_reasons': sorted({str(reason) for row in degraded_sources for reason in as_list(row.get('breach_reasons'))})[:8],
    }
    card['claim_persistence_score'] = claim_persistence
    card['claim_ids'] = claim_ids[:8]
    if degraded_sources and card.get('source_freshness', {}).get('status') == 'fresh':
        card['source_freshness'] = {
            'status': 'mixed',
            'source_refs': card.get('source_freshness', {}).get('source_refs', [])[:8],
        }
    card['no_execution'] = True
    return score_and_gate(card)


def compile_invalidator_undercurrents(invalidator_ledger: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row for row in invalidator_ledger.get('invalidators', [])
        if isinstance(row, dict) and row.get('invalidator_id') and row.get('status') in {'open', 'hit'}
    ]
    rows.sort(key=lambda row: (int(row.get('hit_count') or 0), str(row.get('last_seen_at') or '')), reverse=True)
    out: list[dict[str, Any]] = []
    for row in rows[:12]:
        desc = str(row.get('description') or '')
        hits = int(row.get('hit_count') or 0)
        divergence = 'high' if hits >= 8 else 'medium' if hits >= 4 else 'low'
        title = f'{humanize_signal(desc)}（{hits}次）'
        out.append({
            'undercurrent_id': stable_id('undercurrent', 'invalidator', row.get('invalidator_id'), desc),
            'human_title': title,
            'source_type': 'invalidator_cluster',
            'persistence_score': round(float(hits), 2),
            'velocity': round(float(hits), 2),
            'divergence': divergence,
            'crowding': 'unknown',
            'hedge_gap': 'unknown',
            'promotion_reason': f'{title} 持续累积，需要判断是否影响 attention slot',
            'kill_conditions': ['后续两次扫描不再命中', '相关机会或 thesis 证据被官方修正', '来源新鲜度降为 stale'],
            'linked_refs': {
                'thesis': [row.get('target_id')] if row.get('target_type') == 'thesis' else [],
                'scenario': [],
                'opportunity': [],
                'invalidator': [row.get('invalidator_id')],
                'capital_graph': [],
            },
            'source_freshness': source_freshness_from_refs(row.get('evidence_refs', []) if isinstance(row.get('evidence_refs'), list) else []),
            'no_execution': True,
        })
    return out


def compile_opportunity_undercurrents(opportunity_queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row for row in opportunity_queue.get('candidates', [])
        if isinstance(row, dict) and row.get('candidate_id') and row.get('status') in {'candidate', 'promoted'}
    ]
    rows.sort(key=lambda row: float(row.get('score') or 0), reverse=True)
    out: list[dict[str, Any]] = []
    for row in rows[:8]:
        score = float(row.get('score') or 0)
        instrument = str(row.get('instrument') or 'Unknown')
        title = f'{instrument}｜{short_text(row.get("theme"), 70)}'
        out.append({
            'undercurrent_id': stable_id('undercurrent', 'opportunity', row.get('candidate_id'), instrument),
            'human_title': title,
            'source_type': 'opportunity_accumulation',
            'persistence_score': round(score, 2),
            'velocity': round(score / 3, 2),
            'divergence': 'medium' if score >= 8 else 'low',
            'crowding': 'unknown',
            'hedge_gap': 'unknown',
            'promotion_reason': f'{instrument} 候选分数 {score:g}，可能进入 peacetime campaign',
            'kill_conditions': ['价格/量能不确认', 'source freshness 降级', '候选分数连续下滑'],
            'linked_refs': {
                'thesis': [row.get('linked_thesis_id')] if row.get('linked_thesis_id') else [],
                'scenario': [],
                'opportunity': [row.get('candidate_id')],
                'invalidator': [],
                'capital_graph': [],
            },
            'source_freshness': source_freshness_from_refs(row.get('source_refs', []) if isinstance(row.get('source_refs'), list) else []),
            'no_execution': True,
        })
    return out


def compile_graph_undercurrents(capital_graph: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in capital_graph.get('nodes', []) if isinstance(capital_graph.get('nodes'), list) else []:
        if not isinstance(node, dict) or node.get('type') != 'bucket':
            continue
        bucket_id = str(node.get('id') or '')
        util = float(node.get('utilization_pct') or 0)
        hedge = str(node.get('hedge_coverage') or 'unknown')
        if util < 100 and hedge not in {'uncovered', 'partial'}:
            continue
        source_type = 'hedge_gap' if hedge in {'uncovered', 'partial'} else 'crowding'
        out.append({
            'undercurrent_id': stable_id('undercurrent', source_type, bucket_id),
            'human_title': f'{bucket_id.replace("_", " ")}｜utilization {util:g}% / hedge {hedge}',
            'source_type': source_type,
            'persistence_score': round(max(util / 10, 1), 2),
            'velocity': 1.0,
            'divergence': 'medium' if util >= 150 else 'low',
            'crowding': 'high' if util >= 150 else 'medium' if util >= 100 else 'low',
            'hedge_gap': hedge,
            'promotion_reason': '资本桶拥挤或 hedge coverage 缺口需要长期可见',
            'kill_conditions': ['bucket utilization 回到 100% 以下', 'hedge coverage 修复为 covered'],
            'linked_refs': {'thesis': [], 'scenario': [], 'opportunity': [], 'invalidator': [], 'capital_graph': [bucket_id]},
            'source_freshness': {'status': 'fresh' if capital_graph.get('graph_hash') else 'unknown', 'source_refs': ['state:capital-graph.json']},
            'no_execution': True,
        })
    return out


def compile_undercurrents(
    invalidator_ledger: dict[str, Any],
    opportunity_queue: dict[str, Any],
    capital_graph: dict[str, Any],
    *,
    source_health: dict[str, Any] | None = None,
    atoms: list[dict[str, Any]] | None = None,
    claim_graph: dict[str, Any] | None = None,
    context_gaps: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = shadow_context(
        source_health=source_health,
        atoms=atoms,
        claim_graph=claim_graph,
        context_gaps=context_gaps,
    )
    cards = []
    cards.extend(compile_invalidator_undercurrents(invalidator_ledger))
    cards.extend(compile_opportunity_undercurrents(opportunity_queue))
    cards.extend(compile_graph_undercurrents(capital_graph))
    cards = [enrich_with_shadow_context(card, ctx) for card in cards]
    cards.sort(key=lambda row: float(row.get('persistence_score') or 0), reverse=True)
    return {
        'generated_at': now_iso(),
        'status': 'pass',
        'contract': 'undercurrent-card-v1',
        'undercurrents': cards,
        'shadow_inputs': ctx['shadow_inputs'],
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compile finance undercurrent cards.')
    parser.add_argument('--invalidators', default=str(INVALIDATORS))
    parser.add_argument('--opportunities', default=str(OPPORTUNITIES))
    parser.add_argument('--capital-graph', default=str(CAPITAL_GRAPH))
    parser.add_argument('--source-health', default=str(SOURCE_HEALTH))
    parser.add_argument('--source-atoms', default=str(SOURCE_ATOMS))
    parser.add_argument('--claim-graph', default=str(CLAIM_GRAPH))
    parser.add_argument('--context-gaps', default=str(CONTEXT_GAPS))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)

    payload = compile_undercurrents(
        load_json_safe(Path(args.invalidators), {}) or {},
        load_json_safe(Path(args.opportunities), {}) or {},
        load_json_safe(Path(args.capital_graph), {}) or {},
        source_health=load_json_safe(Path(args.source_health), {}) or {},
        atoms=load_jsonl(Path(args.source_atoms)),
        claim_graph=load_json_safe(Path(args.claim_graph), {}) or {},
        context_gaps=load_json_safe(Path(args.context_gaps), {}) or {},
    )
    atomic_write_json(Path(args.out), payload)
    print(json.dumps({'status': payload['status'], 'count': len(payload['undercurrents']), 'out': args.out}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
