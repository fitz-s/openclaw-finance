#!/usr/bin/env python3
"""Compile deterministic shadow ContextGap records from ClaimGraph."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe
from source_atom_compiler import canonical_hash, stable_id


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
CLAIM_GRAPH = STATE / 'claim-graph.json'
OUT = STATE / 'context-gaps.json'
CONTRACT = 'context-gap-v1-shadow'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def source_for_lane(lane: str) -> list[str]:
    return {
        'market_structure': ['source:yfinance', 'source:exchange_market_data'],
        'corporate_filing': ['source:sec_edgar', 'source:issuer_press_release'],
        'news_policy_narrative': ['source:reuters', 'source:bloomberg'],
        'internal_private': ['source:portfolio_flex'],
        'derived_context': ['source:capital_graph', 'source:scenario_exposure'],
    }.get(lane, ['source:unknown_web'])


def gaps_for_claim(claim: dict[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    claim_id = str(claim.get('claim_id') or '')
    event_class = str(claim.get('event_class') or 'unknown')
    lane = str(claim.get('source_lane') or 'unknown')
    certainty = str(claim.get('certainty') or 'unknown')
    if event_class == 'narrative' and lane != 'market_structure':
        gaps.append(make_gap(claim_id, 'market_structure', 'Narrative-only claim lacks price/volume confirmation.', claim, 'medium'))
    if claim.get('predicate') in {'mentions', 'conflicts'} and claim.get('subject') not in {'news_policy_narrative', 'market_structure'} and event_class != 'filing':
        gaps.append(make_gap(claim_id, 'corporate_filing', 'Issuer/security claim lacks official filing or issuer confirmation.', claim, 'medium'))
    if certainty in {'weak', 'unknown'}:
        gaps.append(make_gap(claim_id, 'derived_context', 'Claim confidence is weak; needs triangulation or contradiction check.', claim, 'low'))
    return gaps


def make_gap(claim_id: str, missing_lane: str, reason: str, claim: dict[str, Any], cost: str) -> dict[str, Any]:
    return {
        'gap_id': stable_id('gap', claim_id, missing_lane, reason),
        'campaign_id': None,
        'claim_id': claim_id,
        'missing_lane': missing_lane,
        'why_load_bearing': reason,
        'what_claims_remain_weak': [claim_id],
        'which_source_could_close_it': source_for_lane(missing_lane),
        'cost_of_ignorance': cost,
        'subject': claim.get('subject'),
        'no_execution': True,
    }


def compile_context_gaps(claim_graph: dict[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    claims = [claim for claim in claim_graph.get('claims', []) if isinstance(claim, dict)]
    dedup: dict[str, dict[str, Any]] = {}
    for claim in claims:
        for gap in gaps_for_claim(claim):
            dedup[gap['gap_id']] = gap
    gaps = sorted(dedup.values(), key=lambda item: item['gap_id'])
    return {
        'generated_at': generated_at or now_iso(),
        'status': 'pass',
        'contract': CONTRACT,
        'claim_graph_hash': claim_graph.get('graph_hash'),
        'gap_count': len(gaps),
        'gaps': gaps,
        'context_gap_hash': canonical_hash(gaps),
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
    parser.add_argument('--claim-graph', default=str(CLAIM_GRAPH))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_state_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    report = compile_context_gaps(load_json_safe(Path(args.claim_graph), {}) or {})
    atomic_write_json(out, report)
    print(json.dumps({'status': report['status'], 'gap_count': report['gap_count'], 'out': str(out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
