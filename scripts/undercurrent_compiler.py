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
OUT = STATE / 'undercurrents.json'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(p or '') for p in parts)
    return f'{prefix}:{hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]}'


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
) -> dict[str, Any]:
    cards = []
    cards.extend(compile_invalidator_undercurrents(invalidator_ledger))
    cards.extend(compile_opportunity_undercurrents(opportunity_queue))
    cards.extend(compile_graph_undercurrents(capital_graph))
    cards.sort(key=lambda row: float(row.get('persistence_score') or 0), reverse=True)
    return {
        'generated_at': now_iso(),
        'status': 'pass',
        'contract': 'undercurrent-card-v1',
        'undercurrents': cards,
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compile finance undercurrent cards.')
    parser.add_argument('--invalidators', default=str(INVALIDATORS))
    parser.add_argument('--opportunities', default=str(OPPORTUNITIES))
    parser.add_argument('--capital-graph', default=str(CAPITAL_GRAPH))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)

    payload = compile_undercurrents(
        load_json_safe(Path(args.invalidators), {}) or {},
        load_json_safe(Path(args.opportunities), {}) or {},
        load_json_safe(Path(args.capital_graph), {}) or {},
    )
    atomic_write_json(Path(args.out), payload)
    print(json.dumps({'status': payload['status'], 'count': len(payload['undercurrents']), 'out': args.out}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
