#!/usr/bin/env python3
"""Compile bounded research inputs for Thesis Spine sidecar."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, POLICY_VERSION, load, now_iso, write


WAKE = FINANCE / 'state' / 'latest-wake-decision.json'
THESIS_REGISTRY = FINANCE / 'state' / 'thesis-registry.json'
OPPORTUNITY_QUEUE = FINANCE / 'state' / 'opportunity-queue.json'
INVALIDATOR_LEDGER = FINANCE / 'state' / 'invalidator-ledger.json'
OUT = FINANCE / 'state' / 'thesis-research-packet.json'


def by_id(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(item.get(key)): item for item in rows if isinstance(item, dict) and item.get(key)}


def build_packet(
    wake: dict[str, Any],
    thesis_registry: dict[str, Any],
    opportunity_queue: dict[str, Any],
    invalidator_ledger: dict[str, Any],
    *,
    opportunity_limit: int = 5,
) -> dict[str, Any]:
    theses = by_id(thesis_registry.get('theses', []), 'thesis_id')
    opportunities = [
        item for item in opportunity_queue.get('candidates', [])
        if isinstance(item, dict) and item.get('status') in {'candidate', 'promoted'}
    ]
    opportunities.sort(key=lambda item: float(item.get('score') or 0), reverse=True)
    invalidators = [
        item for item in invalidator_ledger.get('invalidators', [])
        if isinstance(item, dict) and item.get('status') in {'open', 'hit'}
    ]
    invalidators.sort(key=lambda item: (int(item.get('hit_count') or 0), str(item.get('last_seen_at') or '')), reverse=True)

    wake_thesis_refs = wake.get('thesis_refs', []) if wake.get('wake_class') == 'ISOLATED_JUDGMENT_WAKE' else []
    selected_theses = [theses[ref] for ref in wake_thesis_refs if ref in theses][:5]

    return {
        'generated_at': now_iso(),
        'policy_version': POLICY_VERSION,
        'sidecar_scope': 'bounded_research_artifacts_only',
        'wake_class': wake.get('wake_class'),
        'selected_theses': selected_theses,
        'selected_opportunities': opportunities[:opportunity_limit],
        'selected_invalidators': invalidators[:10],
        'capital_agenda_items': [],
        'displacement_cases': [],
        'forbidden_actions': [
            'no_user_delivery',
            'no_execution',
            'no_threshold_mutation',
            'no_live_authority_change',
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--wake', default=str(WAKE))
    parser.add_argument('--thesis-registry', default=str(THESIS_REGISTRY))
    parser.add_argument('--opportunity-queue', default=str(OPPORTUNITY_QUEUE))
    parser.add_argument('--invalidator-ledger', default=str(INVALIDATOR_LEDGER))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = build_packet(
        load(Path(args.wake), {}) or {},
        load(Path(args.thesis_registry), {}) or {},
        load(Path(args.opportunity_queue), {}) or {},
        load(Path(args.invalidator_ledger), {}) or {},
    )
    write(Path(args.out), payload)
    print(json.dumps({
        'status': 'pass',
        'selected_thesis_count': len(payload['selected_theses']),
        'selected_opportunity_count': len(payload['selected_opportunities']),
        'out': str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
