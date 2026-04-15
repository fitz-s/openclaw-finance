#!/usr/bin/env python3
"""Compile durable ThesisCard registry from WatchIntent objects."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from thesis_spine_util import FINANCE, POLICY_VERSION, load, merge_unique, now_iso, stable_id, write

WATCH_INTENT = FINANCE / 'state' / 'watch-intent.json'
THESIS_REGISTRY = FINANCE / 'state' / 'thesis-registry.json'
ACTIVE_SET = FINANCE / 'state' / 'active-thesis-set.json'


DEFAULT_INVALIDATORS = ['source outage', 'official correction', 'packet staleness']
DEFAULT_CONFIRMATIONS = ['wake-eligible evidence', 'price/flow continuation']
LIFECYCLE_STATUSES = {'candidate', 'active', 'watch', 'suppressed', 'retired'}


def compile_registry(watch_intent: dict, existing: dict | None = None) -> tuple[dict, dict]:
    existing = existing or {}
    existing_by_id = {
        item.get('thesis_id'): item
        for item in existing.get('theses', [])
        if isinstance(item, dict) and item.get('thesis_id')
    }
    existing_by_instrument = {
        item.get('instrument'): item
        for item in existing.get('theses', [])
        if isinstance(item, dict) and item.get('instrument')
    }
    theses = []
    for intent in watch_intent.get('intents', []) if isinstance(watch_intent.get('intents'), list) else []:
        symbol = intent.get('symbol')
        thesis_id = stable_id('thesis', symbol)
        roles = intent.get('roles', [])
        existing_card = existing_by_id.get(thesis_id) or existing_by_instrument.get(symbol) or {}
        default_status = 'active' if 'held_core' in roles else 'watch'
        previous_status = existing_card.get('status') if existing_card.get('status') in LIFECYCLE_STATUSES else None
        status = previous_status or default_status
        if status not in {'suppressed', 'retired'} and default_status == 'active':
            status = 'active'
        theses.append({
            'thesis_id': thesis_id,
            'instrument': symbol,
            'linked_position': symbol if 'held_core' in roles else None,
            'linked_watch_intent': intent.get('intent_id'),
            'status': status,
            'maturity': existing_card.get('maturity') or 'seed',
            'bull_case': existing_card.get('bull_case') if isinstance(existing_card.get('bull_case'), list) else [],
            'bear_case': existing_card.get('bear_case') if isinstance(existing_card.get('bear_case'), list) else [],
            'invalidators': merge_unique(
                existing_card.get('invalidators') if isinstance(existing_card.get('invalidators'), list) else [],
                DEFAULT_INVALIDATORS,
            ),
            'required_confirmations': merge_unique(
                existing_card.get('required_confirmations') if isinstance(existing_card.get('required_confirmations'), list) else [],
                DEFAULT_CONFIRMATIONS,
            ),
            'evidence_refs': existing_card.get('evidence_refs') if isinstance(existing_card.get('evidence_refs'), list) else [],
            'scenario_refs': existing_card.get('scenario_refs') if isinstance(existing_card.get('scenario_refs'), list) else [],
            'last_meaningful_change_at': existing_card.get('last_meaningful_change_at') or watch_intent.get('generated_at'),
            'promotion_reason': existing_card.get('promotion_reason') or 'compiled_from_watch_intent',
            'retirement_reason': existing_card.get('retirement_reason'),
        })
    registry = {'generated_at': now_iso(), 'policy_version': POLICY_VERSION, 'theses': theses}
    active = {
        'generated_at': registry['generated_at'],
        'policy_version': POLICY_VERSION,
        'active_thesis_ids': [item['thesis_id'] for item in theses if item['status'] in {'active', 'watch'}],
    }
    return registry, active


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--watch-intent', default=str(WATCH_INTENT))
    parser.add_argument('--existing', default=str(THESIS_REGISTRY))
    parser.add_argument('--out', default=str(THESIS_REGISTRY))
    parser.add_argument('--active-out', default=str(ACTIVE_SET))
    args = parser.parse_args(argv)
    registry, active = compile_registry(load(Path(args.watch_intent), {}) or {}, load(Path(args.existing), {}) or {})
    write(Path(args.out), registry)
    write(Path(args.active_out), active)
    print(json.dumps({'status': 'pass', 'thesis_count': len(registry['theses']), 'out': str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
