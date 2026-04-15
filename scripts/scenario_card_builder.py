#!/usr/bin/env python3
"""Build persistent ScenarioCard objects from opportunity and invalidator state."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, POLICY_VERSION, load, now_iso, stable_id, write


OPPORTUNITY_QUEUE = FINANCE / 'state' / 'opportunity-queue.json'
INVALIDATOR_LEDGER = FINANCE / 'state' / 'invalidator-ledger.json'
OUT = FINANCE / 'state' / 'scenario-cards.json'


def scenario_type(text: str) -> str:
    lower = text.lower()
    if any(token in lower for token in ['oil', 'crude', 'brent', 'hormuz', 'iran', '原油', '霍尔木兹']):
        return 'commodity_geopolitical'
    if any(token in lower for token in ['options', 'iv', 'oi', '期权']):
        return 'options_flow'
    if any(token in lower for token in ['rates', 'yield', 'cpi', 'fomc', '利率']):
        return 'rates_macro'
    return 'market_dislocation'


def build_scenarios(opportunity_queue: dict[str, Any], invalidator_ledger: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    existing_by_id = {
        item.get('scenario_id'): item
        for item in existing.get('scenarios', [])
        if isinstance(item, dict) and item.get('scenario_id')
    }
    now = now_iso()
    scenarios = []
    for item in opportunity_queue.get('candidates', []) if isinstance(opportunity_queue.get('candidates'), list) else []:
        if not isinstance(item, dict) or item.get('status') not in {'candidate', 'promoted'}:
            continue
        title = str(item.get('theme') or item.get('instrument') or 'market dislocation')
        scenario_id = stable_id('scenario', scenario_type(title), title)
        previous = existing_by_id.get(scenario_id) or {}
        scenarios.append({
            'scenario_id': scenario_id,
            'title': title,
            'status': previous.get('status') if previous.get('status') in {'candidate', 'active', 'dormant', 'retired'} else 'candidate',
            'scenario_type': previous.get('scenario_type') or scenario_type(title),
            'linked_thesis_ids': previous.get('linked_thesis_ids') if isinstance(previous.get('linked_thesis_ids'), list) else [],
            'evidence_refs': previous.get('evidence_refs') if isinstance(previous.get('evidence_refs'), list) else item.get('source_refs', [])[:5],
            'activation_zone': previous.get('activation_zone') if isinstance(previous.get('activation_zone'), dict) else {
                'source': 'opportunity_queue',
                'score': item.get('score'),
            },
            'invalidators': previous.get('invalidators') if isinstance(previous.get('invalidators'), list) else [],
            'last_meaningful_change_at': previous.get('last_meaningful_change_at') or item.get('last_seen_at') or now,
        })

    invalidators = [
        item for item in invalidator_ledger.get('invalidators', [])
        if isinstance(item, dict) and item.get('status') in {'open', 'hit'}
    ]
    if invalidators and not scenarios:
        title = 'open invalidator cluster'
        scenario_id = stable_id('scenario', 'invalidator_cluster', title)
        previous = existing_by_id.get(scenario_id) or {}
        scenarios.append({
            'scenario_id': scenario_id,
            'title': title,
            'status': previous.get('status') or 'candidate',
            'scenario_type': 'invalidator_cluster',
            'linked_thesis_ids': previous.get('linked_thesis_ids') if isinstance(previous.get('linked_thesis_ids'), list) else [],
            'evidence_refs': [],
            'activation_zone': {'source': 'invalidator_ledger', 'open_count': len(invalidators)},
            'invalidators': [item.get('invalidator_id') for item in invalidators[:5] if item.get('invalidator_id')],
            'last_meaningful_change_at': previous.get('last_meaningful_change_at') or now,
        })
    return {'generated_at': now, 'policy_version': POLICY_VERSION, 'scenarios': scenarios[:20]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--opportunity-queue', default=str(OPPORTUNITY_QUEUE))
    parser.add_argument('--invalidator-ledger', default=str(INVALIDATOR_LEDGER))
    parser.add_argument('--existing', default=str(OUT))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = build_scenarios(
        load(Path(args.opportunity_queue), {}) or {},
        load(Path(args.invalidator_ledger), {}) or {},
        load(Path(args.existing), {}) or {},
    )
    write(Path(args.out), payload)
    print(json.dumps({'status': 'pass', 'scenario_count': len(payload['scenarios']), 'out': str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
