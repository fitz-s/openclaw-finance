#!/usr/bin/env python3
"""Build persistent OpportunityQueue from scanner unknown-discovery candidates."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, POLICY_VERSION, clean_symbol, load, now_iso, source_refs, stable_id, symbol_set, write

SCAN_STATE = FINANCE / 'state' / 'intraday-open-scan-state.json'
WATCHLIST = FINANCE / 'state' / 'watchlist-resolved.json'
OUT = FINANCE / 'state' / 'opportunity-queue.json'


def candidate_symbols(item: dict[str, Any]) -> set[str]:
    raw = item.get('tickers')
    if not isinstance(raw, list):
        return set()
    symbols = {clean_symbol(sym) for sym in raw}
    symbols.discard(None)
    return set(symbols)


def score(item: dict[str, Any]) -> float:
    return round(float(item.get('novelty') or 0) * 1.4 + float(item.get('importance') or 0) + float(item.get('urgency') or 0), 2)


def build_queue(scan_state: dict[str, Any], watchlist: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    existing = existing or {}
    existing_by_id = {
        item.get('candidate_id'): item
        for item in existing.get('candidates', [])
        if isinstance(item, dict) and item.get('candidate_id')
    }
    known = symbol_set(watchlist)
    candidates = []
    for item in scan_state.get('accumulated', []) if isinstance(scan_state.get('accumulated'), list) else []:
        if not isinstance(item, dict):
            continue
        scope = str(item.get('discovery_scope') or item.get('candidate_type') or item.get('exploration_lane') or '')
        syms = candidate_symbols(item)
        if scope not in {'non_watchlist', 'unknown_discovery', 'discovery', 'non_watchlist_discovery'} and not (syms - known):
            continue
        if syms & known:
            continue
        theme = str(item.get('theme') or item.get('summary') or 'unknown discovery')
        candidate_id = stable_id('opportunity', theme, ','.join(sorted(syms)))
        previous = existing_by_id.get(candidate_id) or {}
        status = previous.get('status') if previous.get('status') in {'candidate', 'promoted', 'suppressed', 'retired'} else 'candidate'
        seen_at = item.get('ts') or scan_state.get('last_scan_time')
        candidates.append({
            'candidate_id': candidate_id,
            'status': status,
            'instrument': sorted(syms)[0] if syms else None,
            'theme': theme,
            'source_refs': [str(src) for src in item.get('sources', [])[:4]] if isinstance(item.get('sources'), list) else source_refs(SCAN_STATE),
            'promotion_reason': previous.get('promotion_reason') or item.get('non_watchlist_reason') or 'scanner_unknown_discovery',
            'suppression_reason': previous.get('suppression_reason'),
            'linked_thesis_id': previous.get('linked_thesis_id'),
            'first_seen_at': previous.get('first_seen_at') or seen_at,
            'last_seen_at': seen_at or previous.get('last_seen_at'),
            'score': score(item),
            'displacement_case_ref': previous.get('displacement_case_ref'),
        })
    candidates.sort(key=lambda item: item['score'], reverse=True)
    return {'generated_at': now_iso(), 'policy_version': POLICY_VERSION, 'candidates': candidates[:20]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--scan-state', default=str(SCAN_STATE))
    parser.add_argument('--watchlist', default=str(WATCHLIST))
    parser.add_argument('--existing', default=str(OUT))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = build_queue(
        load(Path(args.scan_state), {}) or {},
        load(Path(args.watchlist), {}) or {},
        load(Path(args.existing), {}) or {},
    )
    write(Path(args.out), payload)
    print(json.dumps({'status': 'pass', 'candidate_count': len(payload['candidates']), 'out': str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
