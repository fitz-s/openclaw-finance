#!/usr/bin/env python3
"""Build shadow source memory and lane watermark artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from atomic_io import atomic_write_json
from claim_graph_compiler import OUT as CLAIM_GRAPH, load_jsonl
from source_atom_compiler import SOURCE_ATOMS_LATEST, canonical_hash

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
SOURCE_MEMORY_INDEX = STATE / 'source-memory-index.json'
LANE_WATERMARKS = STATE / 'lane-watermarks.json'
CONTRACT = 'source-memory-index-v1-shadow'
WATERMARK_CONTRACT = 'lane-watermarks-v1-shadow'
NORMALIZATION_PROFILE_VERSION = 'source-memory-v1'
DEFAULT_ALLOWED_LATENESS_SECONDS = {
    'market_structure': 5 * 60,
    'news_policy_narrative': 30 * 60,
    'corp_filing_ir': 24 * 60 * 60,
    'real_economy_alt': 7 * 24 * 60 * 60,
    'human_field_private': 30 * 24 * 60 * 60,
    'internal_private': 30 * 24 * 60 * 60,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def short_hash(*parts: Any) -> str:
    raw = '|'.join(str(part or '') for part in parts)
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]


def domain_from_value(value: Any) -> str | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        if '://' in text:
            host = urlparse(text).netloc
        elif '.' in text and '/' not in text:
            host = text
        else:
            host = ''
    except Exception:
        return None
    host = host.lower().removeprefix('www.')
    return host or None


def atom_domain(atom: dict[str, Any]) -> str | None:
    for key in ('raw_uri', 'url'):
        domain = domain_from_value(atom.get(key))
        if domain:
            return domain
    refs = atom.get('source_refs') if isinstance(atom.get('source_refs'), list) else []
    for ref in refs:
        domain = domain_from_value(ref)
        if domain:
            return domain
    source_id = str(atom.get('source_id') or '').replace('source:', '')
    return source_id or None


def event_date(value: datetime | None) -> str:
    if value is None:
        return 'unknown-date'
    return value.date().isoformat()


def claim_identity(claim: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(claim.get('subject') or 'unknown'),
        str(claim.get('predicate') or 'unknown'),
        str(claim.get('horizon') or 'unknown'),
        str(claim.get('direction') or 'unknown'),
    )


def claim_novelty_score(new_claim: dict[str, Any], existing_claims: list[dict[str, Any]]) -> float:
    subject = str(new_claim.get('subject') or '')
    predicate = str(new_claim.get('predicate') or '')
    horizon = str(new_claim.get('horizon') or '')
    overlaps = [
        claim for claim in existing_claims
        if str(claim.get('subject') or '') == subject
        and str(claim.get('predicate') or '') == predicate
        and str(claim.get('horizon') or '') == horizon
    ]
    if not overlaps:
        return 1.0
    direction = str(new_claim.get('direction') or '')
    same_direction = sum(1 for claim in overlaps if str(claim.get('direction') or '') == direction)
    return max(0.0, round(1.0 - 0.25 * same_direction, 4))


def claims_from_graph(graph: dict[str, Any]) -> list[dict[str, Any]]:
    claims = graph.get('claims') if isinstance(graph, dict) else []
    return [claim for claim in claims if isinstance(claim, dict)] if isinstance(claims, list) else []


def atom_map(atoms: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(atom.get('atom_id')): atom for atom in atoms if isinstance(atom, dict) and atom.get('atom_id')}


def latest_ts(values: list[Any]) -> str | None:
    parsed = [ts for ts in (parse_ts(value) for value in values) if ts is not None]
    return iso(max(parsed)) if parsed else None


def memory_key_for(claim: dict[str, Any], atom: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    lane = str(claim.get('source_lane') or (atom or {}).get('source_lane') or 'unknown')
    entity = str(claim.get('subject') or 'unknown')
    predicate = str(claim.get('predicate') or 'unknown')
    horizon = str(claim.get('horizon') or 'unknown')
    domain = atom_domain(atom or {}) or str(claim.get('source_id') or 'unknown').replace('source:', '')
    event_dt = parse_ts((atom or {}).get('event_time')) or parse_ts((atom or {}).get('published_at')) or parse_ts((atom or {}).get('ingested_at'))
    date_key = event_date(event_dt)
    key = f'{lane}:{entity}:{date_key}:{domain}:{predicate}:{horizon}'
    return key, {
        'memory_key': 'source-memory:' + short_hash(key),
        'lane': lane,
        'entity_key': entity,
        'event_date': date_key,
        'domain': domain,
        'predicate': predicate,
        'horizon': horizon,
        'claim_ids': [],
        'atom_ids': [],
        'source_ids': [],
        'directions': [],
        'latest_event_time': None,
        'latest_ingested_at': None,
    }


def build_source_memory_index(
    atoms: list[dict[str, Any]],
    claim_graph: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or now_iso()
    by_atom = atom_map(atoms)
    entries_by_key: dict[str, dict[str, Any]] = {}
    novelty_by_claim: dict[str, float] = {}
    prior_claims: list[dict[str, Any]] = []
    for claim in claims_from_graph(claim_graph):
        claim_id = str(claim.get('claim_id') or '')
        atom = by_atom.get(str(claim.get('atom_id') or ''))
        key, seed = memory_key_for(claim, atom)
        entry = entries_by_key.setdefault(key, seed)
        if claim_id:
            entry['claim_ids'].append(claim_id)
        if atom and atom.get('atom_id'):
            entry['atom_ids'].append(str(atom['atom_id']))
        source_id = str(claim.get('source_id') or (atom or {}).get('source_id') or '')
        if source_id:
            entry['source_ids'].append(source_id)
        direction = str(claim.get('direction') or 'unknown')
        entry['directions'].append(direction)
        event_time = (atom or {}).get('event_time') or (atom or {}).get('published_at')
        ingested_at = (atom or {}).get('ingested_at')
        entry['latest_event_time'] = latest_ts([entry.get('latest_event_time'), event_time])
        entry['latest_ingested_at'] = latest_ts([entry.get('latest_ingested_at'), ingested_at])
        novelty_by_claim[claim_id] = claim_novelty_score(claim, prior_claims)
        prior_claims.append(claim)

    entries = []
    for entry in entries_by_key.values():
        entry['claim_ids'] = sorted(set(entry['claim_ids']))
        entry['atom_ids'] = sorted(set(entry['atom_ids']))
        entry['source_ids'] = sorted(set(entry['source_ids']))
        entry['directions'] = sorted(set(entry['directions']))
        entry['seen_count'] = len(entry['claim_ids'])
        entry['saturation_score'] = min(1.0, round(max(0, entry['seen_count'] - 1) * 0.25, 4))
        entry['normalization_profile_version'] = NORMALIZATION_PROFILE_VERSION
        entry['restricted_payload_present'] = False
        entry['retention_class'] = 'metadata_only'
        entries.append(entry)
    entries.sort(key=lambda item: item['memory_key'])

    return {
        'generated_at': generated,
        'status': 'pass',
        'contract': CONTRACT,
        'normalization_profile_version': NORMALIZATION_PROFILE_VERSION,
        'memory_count': len(entries),
        'claim_count': len(claims_from_graph(claim_graph)),
        'entries': entries,
        'claim_novelty': novelty_by_claim,
        'input_digest': canonical_hash({'atoms': atoms, 'claim_graph_hash': claim_graph.get('graph_hash')}),
        'output_digest': canonical_hash(entries),
        'restricted_payload_present': False,
        'shadow_only': True,
        'no_execution': True,
    }


def allowed_lateness_seconds(lane: str) -> int:
    return DEFAULT_ALLOWED_LATENESS_SECONDS.get(lane, 24 * 60 * 60)


def build_lane_watermarks(
    atoms: list[dict[str, Any]],
    claim_graph: dict[str, Any],
    source_memory: dict[str, Any] | None = None,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated = generated_at or now_iso()
    source_memory = source_memory or build_source_memory_index(atoms, claim_graph, generated_at=generated)
    novelty = source_memory.get('claim_novelty') if isinstance(source_memory.get('claim_novelty'), dict) else {}
    by_atom = atom_map(atoms)
    watermarks: dict[str, dict[str, Any]] = {}
    for claim in claims_from_graph(claim_graph):
        atom = by_atom.get(str(claim.get('atom_id') or ''))
        key, seed = memory_key_for(claim, atom)
        lane = seed['lane']
        watermark_key = f"{lane}:{seed['entity_key']}:{seed['domain']}"
        row = watermarks.setdefault(watermark_key, {
            'watermark_key': watermark_key,
            'lane': lane,
            'entity_key': seed['entity_key'],
            'domain': seed['domain'],
            'max_event_time': None,
            'watermark_time': None,
            'allowed_lateness_seconds': allowed_lateness_seconds(lane),
            'freshness_sla_seconds': allowed_lateness_seconds(lane),
            'last_effective_fetch_at': None,
            'last_novel_claim_at': None,
            'claim_ids': [],
            'atom_ids': [],
            'paused_until': None,
            'backoff_state': None,
            'merge_policy': 'lane_independent',
        })
        claim_id = str(claim.get('claim_id') or '')
        atom_id = str((atom or {}).get('atom_id') or '')
        event_dt = parse_ts((atom or {}).get('event_time')) or parse_ts((atom or {}).get('published_at'))
        ingested_dt = parse_ts((atom or {}).get('ingested_at'))
        row['max_event_time'] = latest_ts([row.get('max_event_time'), iso(event_dt)])
        row['last_effective_fetch_at'] = latest_ts([row.get('last_effective_fetch_at'), iso(ingested_dt)])
        if float(novelty.get(claim_id, 0.0) or 0.0) > 0.0:
            row['last_novel_claim_at'] = latest_ts([row.get('last_novel_claim_at'), iso(event_dt)])
        if claim_id:
            row['claim_ids'].append(claim_id)
        if atom_id:
            row['atom_ids'].append(atom_id)
        max_event = parse_ts(row.get('max_event_time'))
        if max_event:
            row['watermark_time'] = iso(max_event - timedelta(seconds=row['allowed_lateness_seconds']))
    rows = []
    for row in watermarks.values():
        row['claim_ids'] = sorted(set(row['claim_ids']))
        row['atom_ids'] = sorted(set(row['atom_ids']))
        rows.append(row)
    rows.sort(key=lambda item: item['watermark_key'])
    return {
        'generated_at': generated,
        'status': 'pass',
        'contract': WATERMARK_CONTRACT,
        'watermark_count': len(rows),
        'watermarks': rows,
        'normalization_profile_version': NORMALIZATION_PROFILE_VERSION,
        'shadow_only': True,
        'no_execution': True,
    }


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--atoms', default=str(SOURCE_ATOMS_LATEST))
    parser.add_argument('--claim-graph', default=str(CLAIM_GRAPH))
    parser.add_argument('--out', default=str(SOURCE_MEMORY_INDEX))
    parser.add_argument('--watermarks-out', default=str(LANE_WATERMARKS))
    args = parser.parse_args(argv)
    out = Path(args.out)
    watermarks_out = Path(args.watermarks_out)
    if not safe_state_path(out) or not safe_state_path(watermarks_out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_state_path']}, ensure_ascii=False))
        return 2
    atoms = load_jsonl(Path(args.atoms))
    graph = load_json(Path(args.claim_graph), {}) or {}
    memory = build_source_memory_index(atoms, graph)
    watermarks = build_lane_watermarks(atoms, graph, memory, generated_at=memory['generated_at'])
    atomic_write_json(out, memory)
    atomic_write_json(watermarks_out, watermarks)
    print(json.dumps({'status': 'pass', 'memory_count': memory['memory_count'], 'watermark_count': watermarks['watermark_count'], 'out': str(out), 'watermarks_out': str(watermarks_out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
