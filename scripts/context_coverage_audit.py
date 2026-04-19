#!/usr/bin/env python3
"""Audit source/context coverage for review-only learning."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe
from source_roi_tracker import load_jsonl


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'context-coverage-audit.json'
SOURCE_HEALTH = Path('/Users/leofitz/.openclaw/workspace/services/market-ingest/state/source-health.json')
CLAIM_GRAPH = STATE / 'claim-graph.json'
CONTEXT_GAPS = STATE / 'context-gaps.json'
CAMPAIGN_BOARD = STATE / 'campaign-board.json'
FOLLOWUP_ROUTE = STATE / 'followup-context-route.json'
POLICY_VERSION = 'context-coverage-v1-review-only'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def build_report(source_health: dict[str, Any], claim_graph: dict[str, Any], context_gaps: dict[str, Any], campaign_board: dict[str, Any], followup_route: dict[str, Any]) -> dict[str, Any]:
    sources = as_list(source_health.get('sources'))
    claims = as_list(claim_graph.get('claims'))
    gaps = as_list(context_gaps.get('gaps'))
    campaigns = as_list(campaign_board.get('campaigns'))
    freshness_breaches = [s for s in sources if isinstance(s, dict) and s.get('freshness_status') in {'stale', 'unknown'}]
    gap_rate = round(len(gaps) / max(len(claims), 1), 3)
    source_coverage_score = round(max(0.0, 1.0 - (len(freshness_breaches) / max(len(sources), 1))) * 100, 2)
    campaign_gap_count = sum(len(c.get('known_unknowns', []) if isinstance(c, dict) and isinstance(c.get('known_unknowns'), list) else []) for c in campaigns)
    grounding_failure = bool(followup_route.get('insufficient_data')) or bool(followup_route.get('errors'))
    return {
        'generated_at': now_iso(),
        'status': 'review',
        'policy_version': POLICY_VERSION,
        'source_coverage_score': source_coverage_score,
        'freshness_sla_breach_rate': round(len(freshness_breaches) / max(len(sources), 1), 3),
        'campaign_context_gap_rate': gap_rate,
        'campaign_known_unknown_count': campaign_gap_count,
        'followup_grounding_failure': grounding_failure,
        'counts': {
            'sources': len(sources),
            'freshness_breaches': len(freshness_breaches),
            'claims': len(claims),
            'context_gaps': len(gaps),
            'campaigns': len(campaigns),
        },
        'review_only': True,
        'no_threshold_mutation': True,
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-health', default=str(SOURCE_HEALTH))
    parser.add_argument('--claim-graph', default=str(CLAIM_GRAPH))
    parser.add_argument('--context-gaps', default=str(CONTEXT_GAPS))
    parser.add_argument('--campaign-board', default=str(CAMPAIGN_BOARD))
    parser.add_argument('--followup-route', default=str(FOLLOWUP_ROUTE))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    report = build_report(
        load_json_safe(Path(args.source_health), {}) or {},
        load_json_safe(Path(args.claim_graph), {}) or {},
        load_json_safe(Path(args.context_gaps), {}) or {},
        load_json_safe(Path(args.campaign_board), {}) or {},
        load_json_safe(Path(args.followup_route), {}) or {},
    )
    atomic_write_json(Path(args.out), report)
    print(json.dumps({'status': report['status'], 'source_coverage_score': report['source_coverage_score'], 'out': args.out}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
