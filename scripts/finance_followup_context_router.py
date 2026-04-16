#!/usr/bin/env python3
"""Route finance follow-up requests to verb-specific campaign/bundle context."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
READER_BUNDLE = STATE / 'report-reader' / 'latest.json'
CAMPAIGN_BOARD = STATE / 'campaign-board.json'
CAMPAIGN_CACHE = STATE / 'campaign-cache.json'
OUT = STATE / 'followup-context-route.json'
VALID_VERBS = {'why', 'challenge', 'compare', 'scenario', 'sources', 'trace', 'expand'}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_query(query: str) -> dict[str, Any]:
    parts = query.strip().split()
    verb = parts[0].lower() if parts else ''
    handles = parts[1:]
    return {
        'verb': verb,
        'primary_handle': handles[0] if handles else '',
        'secondary_handle': handles[1] if len(handles) > 1 else '',
    }


def campaign_by_id(campaign_board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(c.get('campaign_id')): c
        for c in campaign_board.get('campaigns', []) if isinstance(c, dict) and c.get('campaign_id')
    }


def bundle_card_by_handle(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(c.get('handle')): c
        for c in bundle.get('object_cards', []) if isinstance(c, dict) and c.get('handle')
    }


def route_context(
    *,
    query: str,
    bundle: dict[str, Any],
    campaign_board: dict[str, Any],
    campaign_cache: dict[str, Any],
) -> dict[str, Any]:
    parsed = parse_query(query)
    verb = parsed['verb']
    primary = parsed['primary_handle']
    secondary = parsed['secondary_handle']
    errors: list[str] = []
    warnings: list[str] = []
    if verb not in VALID_VERBS:
        errors.append(f'invalid_verb:{verb or "missing"}')
    if not primary:
        errors.append('missing_primary_handle')
    if verb == 'compare' and not secondary:
        errors.append('missing_secondary_handle')

    campaigns = campaign_by_id(campaign_board)
    cards = bundle_card_by_handle(bundle)
    cache = campaign_cache.get('cache', {}) if isinstance(campaign_cache.get('cache'), dict) else {}
    selected_campaign = campaigns.get(primary)
    selected_card = cards.get(primary)
    if primary and not selected_campaign and not selected_card:
        errors.append(f'unknown_primary_handle:{primary}')
    cache_slice = None
    if selected_campaign:
        cache_slice = cache.get(primary, {}).get('sources' if verb == 'trace' else verb)
    if selected_campaign and cache_slice is None:
        warnings.append(f'cache_miss:{verb}:{primary}')

    evidence_slice = {
        'why': ['why_now_delta', 'source_freshness', 'capital_relevance', 'confirmations_needed'],
        'challenge': ['why_not_now', 'kill_switches', 'source_freshness'],
        'compare': ['capital_relevance', 'linked_thesis', 'linked_displacement_cases'],
        'scenario': ['linked_scenarios', 'capital_relevance'],
        'sources': ['source_freshness', 'linked_thesis', 'linked_scenarios', 'linked_opportunities', 'linked_invalidators'],
        'trace': ['source_freshness', 'linked_thesis', 'linked_scenarios', 'linked_opportunities', 'linked_invalidators'],
        'expand': ['campaign'],
    }.get(verb, [])

    return {
        'generated_at': now_iso(),
        'status': 'pass' if not errors else 'fail',
        'query': query,
        'verb': verb,
        'primary_handle': primary,
        'secondary_handle': secondary,
        'errors': errors,
        'warnings': warnings,
        'selected_campaign': selected_campaign,
        'selected_object_card': selected_card,
        'cache_slice': cache_slice,
        'evidence_slice_keys': evidence_slice,
        'bundle_ref': bundle.get('bundle_id'),
        'campaign_board_ref': campaign_board.get('contract'),
        'insufficient_data_rule': 'Return insufficient_data with missing fields instead of generic inference when required slice is empty.',
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', required=True)
    parser.add_argument('--bundle', default=str(READER_BUNDLE))
    parser.add_argument('--campaign-board', default=str(CAMPAIGN_BOARD))
    parser.add_argument('--campaign-cache', default=str(CAMPAIGN_CACHE))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = route_context(
        query=args.query,
        bundle=load_json_safe(Path(args.bundle), {}) or {},
        campaign_board=load_json_safe(Path(args.campaign_board), {}) or {},
        campaign_cache=load_json_safe(Path(args.campaign_cache), {}) or {},
    )
    atomic_write_json(Path(args.out), payload)
    print(json.dumps({'status': payload['status'], 'errors': payload['errors'], 'out': args.out}, ensure_ascii=False))
    return 0 if payload['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
