#!/usr/bin/env python3
"""Merge committee role memos into annotated capital agenda items."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, POLICY_VERSION, load, now_iso, stable_id, write


CAPITAL_AGENDA = FINANCE / 'state' / 'capital-agenda.json'
MEMO_DIR = FINANCE / 'state' / 'committee-memos'
OUT = FINANCE / 'state' / 'capital-agenda-annotated.json'


def load_memos(memo_dir: Path) -> list[dict[str, Any]]:
    """Load all committee memos from the memo directory."""
    if not memo_dir.exists() or not memo_dir.is_dir():
        return []
    memos = []
    for f in sorted(memo_dir.glob('*.json')):
        try:
            memo = json.loads(f.read_text(encoding='utf-8'))
            if isinstance(memo, dict) and memo.get('memo_id'):
                memos.append(memo)
        except Exception:
            continue
    return memos


def memos_for_item(memos: list[dict[str, Any]], agenda_id: str) -> list[dict[str, Any]]:
    return [m for m in memos if m.get('agenda_item_ref') == agenda_id]


def compute_consensus(item_memos: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute consensus from role memos."""
    if not item_memos:
        return {'status': 'no_memos', 'consensus_score': 0, 'disagreements': []}
    recommendations = [m.get('assessment', {}).get('recommendation', 'review') for m in item_memos]
    confidences = [m.get('confidence', 'insufficient_data') for m in item_memos]
    confidence_scores = {'high': 3, 'medium': 2, 'low': 1, 'insufficient_data': 0}
    avg_confidence = sum(confidence_scores.get(c, 0) for c in confidences) / max(len(confidences), 1)
    # Flag disagreements
    unique_recs = set(recommendations)
    disagreements = []
    if len(unique_recs) > 1:
        for memo in item_memos:
            rec = memo.get('assessment', {}).get('recommendation', 'review')
            if rec != recommendations[0]:
                disagreements.append({
                    'role': memo.get('role'),
                    'recommendation': rec,
                    'vs_majority': recommendations[0],
                })
    risk_flags = []
    for memo in item_memos:
        risk_flags.extend(memo.get('risk_flags', []))
    return {
        'status': 'consensus' if len(unique_recs) == 1 else 'split',
        'consensus_recommendation': max(set(recommendations), key=recommendations.count),
        'consensus_score': round(avg_confidence, 2),
        'role_count': len(item_memos),
        'disagreements': disagreements,
        'aggregated_risk_flags': list(set(risk_flags))[:10],
        'required_questions': list(set(
            q for m in item_memos for q in m.get('required_questions', [])
        ))[:5],
    }


def merge(capital_agenda: dict[str, Any], memos: list[dict[str, Any]]) -> dict[str, Any]:
    annotated_items = []
    for item in capital_agenda.get('agenda_items', []) if isinstance(capital_agenda.get('agenda_items'), list) else []:
        if not isinstance(item, dict):
            continue
        agenda_id = item.get('agenda_id')
        item_memos = memos_for_item(memos, agenda_id) if agenda_id else []
        consensus = compute_consensus(item_memos)
        annotated = {**item, 'committee_consensus': consensus}
        annotated_items.append(annotated)
    return {
        'generated_at': now_iso(),
        'policy_version': POLICY_VERSION,
        'capital_graph_hash': capital_agenda.get('capital_graph_hash'),
        'total_memos': len(memos),
        'annotated_count': len(annotated_items),
        'agenda_items': annotated_items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--capital-agenda', default=str(CAPITAL_AGENDA))
    parser.add_argument('--memo-dir', default=str(MEMO_DIR))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    memos = load_memos(Path(args.memo_dir))
    payload = merge(load(Path(args.capital_agenda), {}) or {}, memos)
    write(Path(args.out), payload)
    print(json.dumps({
        'status': 'pass',
        'memo_count': payload['total_memos'],
        'annotated_count': payload['annotated_count'],
        'out': str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
