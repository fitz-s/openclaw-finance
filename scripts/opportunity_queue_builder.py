#!/usr/bin/env python3
"""Build persistent OpportunityQueue from scanner unknown-discovery candidates."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, POLICY_VERSION, clean_symbol, load, now_iso, source_refs, stable_id, symbol_set, write

SCAN_STATE = FINANCE / 'state' / 'intraday-open-scan-state.json'
WATCHLIST = FINANCE / 'state' / 'watchlist-resolved.json'
OUT = FINANCE / 'state' / 'opportunity-queue.json'
FRESH_SOURCE_HOURS = 8
STALE_SOURCE_HOURS = 24


def candidate_symbols(item: dict[str, Any]) -> set[str]:
    raw = item.get('tickers')
    if not isinstance(raw, list):
        return set()
    symbols = {clean_symbol(sym) for sym in raw}
    symbols.discard(None)
    return set(symbols)


def score(item: dict[str, Any]) -> float:
    return round(float(item.get('novelty') or 0) * 1.4 + float(item.get('importance') or 0) + float(item.get('urgency') or 0), 2)


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception:
        return None


def source_ref_time(source_ref: Any, *, reference_year: int) -> datetime | None:
    text = str(source_ref or '')
    iso = re.search(r'20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?Z?', text)
    if iso:
        return parse_ts(iso.group(0))
    date = re.search(r'(20\d{2})-(\d{2})-(\d{2})', text)
    if date:
        return parse_ts(f'{date.group(1)}-{date.group(2)}-{date.group(3)}T00:00:00Z')
    month = re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})\b', text, re.I)
    if month:
        try:
            parsed = datetime.strptime(f'{month.group(1)} {month.group(2)} {reference_year}', '%b %d %Y')
            return parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def source_freshness(item: dict[str, Any], scan_state: dict[str, Any]) -> dict[str, Any]:
    now = parse_ts(scan_state.get('last_updated')) or datetime.now(timezone.utc)
    refs = item.get('sources') if isinstance(item.get('sources'), list) else []
    fresh = 0
    stale = 0
    unknown = 0
    external_stale = 0
    ages: list[float] = []
    for ref in refs:
        parsed = source_ref_time(ref, reference_year=now.year)
        if parsed is None:
            if str(ref).startswith('state:'):
                unknown += 1
            else:
                unknown += 1
            continue
        age_hours = max(0.0, (now - parsed).total_seconds() / 3600)
        ages.append(age_hours)
        if age_hours <= FRESH_SOURCE_HOURS:
            fresh += 1
        elif age_hours >= STALE_SOURCE_HOURS:
            stale += 1
            if not str(ref).startswith('state:'):
                external_stale += 1
        else:
            unknown += 1
    if fresh and stale:
        status = 'mixed'
    elif fresh:
        status = 'fresh'
    elif stale:
        status = 'stale'
    else:
        status = 'unknown'
    penalty = external_stale * 1.5
    if not fresh and stale:
        penalty += 2.5
    if status == 'unknown':
        penalty += 0.75
    return {
        'status': status,
        'fresh_source_count': fresh,
        'stale_source_count': stale,
        'unknown_source_count': unknown,
        'external_stale_source_count': external_stale,
        'max_source_age_hours': round(max(ages), 2) if ages else None,
        'source_quality_penalty': round(penalty, 2),
    }


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
        base_score = score(item)
        freshness = source_freshness(item, scan_state)
        adjusted_score = max(0.0, round(base_score - float(freshness['source_quality_penalty']), 2))
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
            'score': adjusted_score,
            'score_before_source_penalty': base_score,
            'source_freshness_status': freshness['status'],
            'source_fresh_count': freshness['fresh_source_count'],
            'source_stale_count': freshness['stale_source_count'],
            'source_unknown_count': freshness['unknown_source_count'],
            'external_stale_source_count': freshness['external_stale_source_count'],
            'max_source_age_hours': freshness['max_source_age_hours'],
            'source_quality_penalty': freshness['source_quality_penalty'],
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
