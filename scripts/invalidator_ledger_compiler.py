#!/usr/bin/env python3
"""Compile persistent InvalidatorLedger from packet contradictions and judgment invalidators."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from thesis_spine_util import FINANCE, POLICY_VERSION, load, now_iso, parse_iso, stable_id, write

PACKET = FINANCE.parents[0] / 'services' / 'market-ingest' / 'state' / 'latest-context-packet.json'
JUDGMENT = FINANCE / 'state' / 'judgment-envelope.json'
OUT = FINANCE / 'state' / 'invalidator-ledger.json'


def source_time(packet: dict, judgment: dict) -> str:
    return (
        judgment.get('created_at')
        or judgment.get('judged_at')
        or packet.get('compiled_at')
        or packet.get('generated_at')
        or now_iso()
    )


def merge_row(row: dict, existing_by_id: dict[str, dict], seen_at: str) -> dict:
    previous = existing_by_id.get(row['invalidator_id']) or {}
    if not previous:
        return row
    previous_seen = parse_iso(previous.get('last_seen_at'))
    current_seen = parse_iso(seen_at)
    next_hit_count = int(previous.get('hit_count') or 1)
    next_last_seen = previous.get('last_seen_at') or row.get('last_seen_at')
    if current_seen and (previous_seen is None or current_seen > previous_seen):
        next_hit_count += 1
        next_last_seen = seen_at
    merged = {
        **row,
        'status': previous.get('status') or row.get('status'),
        'first_seen_at': previous.get('first_seen_at') or row.get('first_seen_at'),
        'last_seen_at': next_last_seen,
        'hit_count': next_hit_count,
        'resolution': previous.get('resolution', row.get('resolution')),
    }
    if previous.get('evidence_refs'):
        merged['evidence_refs'] = previous['evidence_refs']
    return merged


def compile_ledger(packet: dict, judgment: dict, existing: dict | None = None) -> dict:
    existing = existing or {}
    existing_by_id = {
        item.get('invalidator_id'): item
        for item in existing.get('invalidators', [])
        if isinstance(item, dict) and item.get('invalidator_id')
    }
    rows = []
    seen_at = source_time(packet, judgment)
    now = now_iso()
    for item in judgment.get('invalidators', []) if isinstance(judgment.get('invalidators'), list) else []:
        desc = str(item)
        rows.append(merge_row({
            'invalidator_id': stable_id('invalidator', judgment.get('judgment_id'), desc),
            'target_type': 'packet',
            'target_id': str(packet.get('packet_id') or judgment.get('packet_id') or 'unknown'),
            'status': 'open',
            'description': desc,
            'evidence_refs': judgment.get('evidence_refs', [])[:5] if isinstance(judgment.get('evidence_refs'), list) else [],
            'first_seen_at': seen_at,
            'last_seen_at': seen_at,
            'hit_count': 1,
            'resolution': None,
        }, existing_by_id, seen_at))
    for contradiction in packet.get('contradictions', []) if isinstance(packet.get('contradictions'), list) else []:
        if not isinstance(contradiction, dict):
            continue
        key = str(contradiction.get('contradiction_key') or stable_id('contradiction', contradiction))
        refs = list(contradiction.get('supports', []) or []) + list(contradiction.get('conflicts_with', []) or [])
        rows.append(merge_row({
            'invalidator_id': stable_id('invalidator', key),
            'target_type': 'packet',
            'target_id': str(packet.get('packet_id') or 'unknown'),
            'status': 'hit',
            'description': key,
            'evidence_refs': [str(ref) for ref in refs[:8]],
            'first_seen_at': seen_at,
            'last_seen_at': seen_at,
            'hit_count': 1,
            'resolution': None,
        }, existing_by_id, seen_at))
    return {'generated_at': now, 'policy_version': POLICY_VERSION, 'invalidators': rows}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', default=str(PACKET))
    parser.add_argument('--judgment', default=str(JUDGMENT))
    parser.add_argument('--existing', default=str(OUT))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = compile_ledger(
        load(Path(args.packet), {}) or {},
        load(Path(args.judgment), {}) or {},
        load(Path(args.existing), {}) or {},
    )
    write(Path(args.out), payload)
    print(json.dumps({'status': 'pass', 'invalidator_count': len(payload['invalidators']), 'out': str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
