#!/usr/bin/env python3
"""Pre-bake verb-specific cards for top finance campaigns."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
CAMPAIGN_BOARD = STATE / 'campaign-board.json'
OUT = STATE / 'campaign-cache.json'
VERBS = ('why', 'challenge', 'compare', 'scenario', 'sources', 'trace', 'expand')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(part or '') for part in parts)
    return f'{prefix}:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def build_cards(campaign: dict[str, Any]) -> dict[str, dict[str, Any]]:
    title = campaign.get('human_title')
    cid = campaign.get('campaign_id')
    return {
        'why': {
            'evidence_slice_id': stable_id('slice', cid, 'why'),
            'title': title,
            'fact_slice': [campaign.get('why_now_delta'), campaign.get('source_freshness')],
            'interpretation_slice': [campaign.get('capital_relevance'), campaign.get('stage_reason')],
            'to_verify': as_list(campaign.get('confirmations_needed'))[:4],
            'known_unknowns': as_list(campaign.get('known_unknowns'))[:3],
        },
        'challenge': {
            'evidence_slice_id': stable_id('slice', cid, 'challenge'),
            'title': title,
            'countercase_slice': as_list(campaign.get('kill_switches'))[:5],
            'why_not_now': campaign.get('why_not_now'),
            'source_freshness': campaign.get('source_freshness'),
            'known_unknowns': as_list(campaign.get('known_unknowns'))[:5],
            'source_health_summary': campaign.get('source_health_summary'),
        },
        'compare': {
            'evidence_slice_id': stable_id('slice', cid, 'compare'),
            'title': title,
            'capital_relevance': campaign.get('capital_relevance'),
            'linked_thesis': as_list(campaign.get('linked_thesis')),
            'linked_displacement_cases': as_list(campaign.get('linked_displacement_cases')),
            'missing_if_empty': 'displacement_case or capital_graph overlap may be insufficient for strong compare',
        },
        'scenario': {
            'evidence_slice_id': stable_id('slice', cid, 'scenario'),
            'title': title,
            'linked_scenarios': as_list(campaign.get('linked_scenarios')),
            'capital_relevance': campaign.get('capital_relevance'),
            'known_unknowns': as_list(campaign.get('known_unknowns'))[:3],
            'missing_if_empty': 'scenario exposure matrix slice required for stronger stress answer',
        },
        'sources': {
            'evidence_slice_id': stable_id('slice', cid, 'sources'),
            'title': title,
            'source_freshness': campaign.get('source_freshness'),
            'source_health_summary': campaign.get('source_health_summary'),
            'linked_refs': {
                'thesis': as_list(campaign.get('linked_thesis')),
                'scenario': as_list(campaign.get('linked_scenarios')),
                'opportunity': as_list(campaign.get('linked_opportunities')),
                'invalidator': as_list(campaign.get('linked_invalidators')),
                'atoms': as_list(campaign.get('linked_atoms')),
                'claims': as_list(campaign.get('linked_claims')),
                'context_gaps': as_list(campaign.get('linked_context_gaps')),
            },
        },
        'trace': {
            'evidence_slice_id': stable_id('slice', cid, 'trace'),
            'title': title,
            'lineage_refs': {
                'atoms': as_list(campaign.get('linked_atoms')),
                'claims': as_list(campaign.get('linked_claims')),
                'context_gaps': as_list(campaign.get('linked_context_gaps')),
                'thread_key': campaign.get('thread_key'),
            },
            'source_health_summary': campaign.get('source_health_summary'),
        },
        'expand': {
            'evidence_slice_id': stable_id('slice', cid, 'expand'),
            'campaign': campaign,
        },
    }


def build_cache(campaign_board: dict[str, Any], top_n: int = 5) -> dict[str, Any]:
    campaigns = [c for c in as_list(campaign_board.get('campaigns')) if isinstance(c, dict)]
    campaigns.sort(key=lambda c: (c.get('board_class') != 'live', -float(c.get('priority_score') or 0), c.get('human_title') or ''))
    cache = {}
    for campaign in campaigns[:top_n]:
        cid = str(campaign.get('campaign_id') or '')
        if cid:
            cache[cid] = build_cards(campaign)
    return {
        'generated_at': now_iso(),
        'status': 'pass',
        'contract': 'campaign-cache-v1',
        'cache': cache,
        'verbs': list(VERBS),
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--campaign-board', default=str(CAMPAIGN_BOARD))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = build_cache(load_json_safe(Path(args.campaign_board), {}) or {})
    atomic_write_json(Path(args.out), payload)
    print(json.dumps({'status': payload['status'], 'campaigns': len(payload['cache']), 'out': args.out}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
