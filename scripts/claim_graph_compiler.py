#!/usr/bin/env python3
"""Compile a deterministic shadow ClaimGraph from EvidenceAtom rows."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json
from source_atom_compiler import SOURCE_ATOMS_LATEST, canonical_hash, stable_id, short_text


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OUT = STATE / 'claim-graph.json'
CONTRACT = 'claim-graph-v1-shadow'

BULLISH = {'rally', 'up', 'beats', 'growth', 'raises', 'buyback', '增持', '上涨', '利好'}
BEARISH = {'down', 'falls', 'misses', 'delay', 'lawsuit', 'risk', 'conflict', '下跌', '风险', '利空', '尚未'}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def infer_direction(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in BEARISH):
        return 'bearish'
    if any(token in lowered for token in BULLISH):
        return 'bullish'
    return 'ambiguous'


def event_class_for(atom: dict[str, Any]) -> str:
    lane = str(atom.get('source_lane') or '')
    sublane = str(atom.get('source_sublane') or '')
    snippet = str(atom.get('safe_excerpt') or atom.get('raw_snippet') or '').lower()
    if sublane in {'market_structure.options_iv', 'market_structure.options_flow_proxy'}:
        return 'flow'
    if lane == 'market_structure':
        return 'price'
    if lane in {'corporate_filing', 'corp_filing_ir'} or '8-k' in snippet or 'filing' in snippet:
        return 'filing'
    if lane == 'internal_private':
        return 'portfolio'
    if 'flow' in snippet or 'option' in snippet:
        return 'flow'
    if 'source' in snippet and 'status' in snippet:
        return 'source_health'
    return 'narrative'


def predicate_for(atom: dict[str, Any], event_class: str) -> str:
    if event_class == 'price':
        return 'moves'
    if event_class == 'filing':
        return 'files'
    if event_class == 'flow':
        return 'shows_flow'
    if event_class == 'portfolio':
        return 'updates_private_context'
    if 'conflict' in str(atom.get('raw_snippet') or '').lower() or '冲突' in str(atom.get('raw_snippet') or ''):
        return 'conflicts'
    return 'mentions'


def claim_from_atom(atom: dict[str, Any]) -> dict[str, Any]:
    symbols = atom.get('symbol_candidates') if isinstance(atom.get('symbol_candidates'), list) else []
    subject = str(symbols[0]) if symbols else str(atom.get('source_lane') or atom.get('source_id') or 'unknown')
    event_class = event_class_for(atom)
    snippet = short_text(atom.get('safe_excerpt') or atom.get('raw_snippet'), 180)
    direction = infer_direction(snippet)
    claim = {
        'claim_id': stable_id('claim', atom.get('atom_id'), subject, snippet),
        'atom_id': atom.get('atom_id'),
        'source_id': atom.get('source_id'),
        'source_lane': atom.get('source_lane'),
        'source_sublane': atom.get('source_sublane'),
        'subject': subject,
        'predicate': predicate_for(atom, event_class),
        'object': snippet,
        'magnitude': None,
        'unit': None,
        'direction': direction,
        'horizon': 'intraday' if atom.get('source_lane') == 'market_structure' else 'multi_day' if event_class in {'filing', 'narrative'} else 'unknown',
        'certainty': 'confirmed' if atom.get('source_id') == 'source:sec_edgar' else 'weak' if atom.get('compliance_class') == 'unknown' else 'probable',
        'supports': [],
        'contradicts': [],
        'event_class': event_class,
        'why_it_matters_tags': [tag for tag in [event_class, atom.get('candidate_type')] if tag],
        'capital_relevance_tags': [str(symbol) for symbol in symbols[:3]],
        'source_reliability_score': atom.get('reliability_score'),
        'source_uniqueness_score': atom.get('uniqueness_score'),
        'evidence_rights': {
            'compliance_class': atom.get('compliance_class'),
            'redistribution_policy': atom.get('redistribution_policy'),
            'export_policy': atom.get('export_policy'),
            'raw_snippet_redaction_required': atom.get('raw_snippet_redaction_required'),
        },
        'lineage': {
            'atom_id': atom.get('atom_id'),
            'point_in_time_hash': atom.get('point_in_time_hash'),
            'raw_snippet_ref': atom.get('raw_snippet_ref'),
        },
        'no_execution': True,
    }
    return claim


def add_claim_edges(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_subject: dict[str, list[dict[str, Any]]] = {}
    for claim in claims:
        by_subject.setdefault(str(claim.get('subject')), []).append(claim)
    by_id = {claim['claim_id']: claim for claim in claims}
    for subject_claims in by_subject.values():
        bullish = [c for c in subject_claims if c.get('direction') == 'bullish']
        bearish = [c for c in subject_claims if c.get('direction') == 'bearish']
        for claim in bullish:
            claim['contradicts'] = sorted({c['claim_id'] for c in bearish})
        for claim in bearish:
            claim['contradicts'] = sorted({c['claim_id'] for c in bullish})
        for claim in subject_claims:
            claim['supports'] = sorted({c['claim_id'] for c in subject_claims if c is not claim and c.get('direction') == claim.get('direction') and c.get('direction') != 'ambiguous'})
    return sorted(by_id.values(), key=lambda item: item['claim_id'])


def compile_claim_graph(atoms: list[dict[str, Any]], *, generated_at: str | None = None) -> dict[str, Any]:
    claims = add_claim_edges([claim_from_atom(atom) for atom in atoms if isinstance(atom, dict) and atom.get('atom_id')])
    graph = {
        'generated_at': generated_at or now_iso(),
        'status': 'pass',
        'contract': CONTRACT,
        'atom_count': len(atoms),
        'claim_count': len(claims),
        'claims': claims,
        'graph_hash': canonical_hash(claims),
        'shadow_only': True,
        'no_execution': True,
    }
    return graph


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
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_state_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    report = compile_claim_graph(load_jsonl(Path(args.atoms)))
    atomic_write_json(out, report)
    print(json.dumps({'status': report['status'], 'claim_count': report['claim_count'], 'out': str(out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
