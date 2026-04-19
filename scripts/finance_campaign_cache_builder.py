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
VERB_GROUPS = {
    'why': ['campaign_projection', 'recent_claims', 'source_health', 'promotion_reason', 'event_timeline'],
    'challenge': ['countercase_memo', 'invalidators', 'contradictions', 'denied_hypotheses', 'freshness_risks'],
    'compare': ['capital_graph_slice', 'displacement_case', 'bucket_competition', 'portfolio_attachment'],
    'scenario': ['scenario_exposure', 'hedge_coverage', 'crowding_risk', 'linked_campaigns'],
    'sources': ['source_atoms', 'claim_lineage', 'rights_and_redaction', 'freshness_by_lane'],
    'trace': ['handle_to_claim_to_atom_to_source_lineage'],
    'expand': ['prepared_campaign_cache', 'report_bundle_summary'],
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(part or '') for part in parts)
    return f'{prefix}:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def grounding_summary(campaign: dict[str, Any]) -> dict[str, Any]:
    return {
        'atoms': len(as_list(campaign.get('linked_atoms'))),
        'claims': len(as_list(campaign.get('linked_claims'))),
        'context_gaps': len(as_list(campaign.get('linked_context_gaps'))),
        'source_diversity': int(campaign.get('source_diversity') or 0),
        'cross_lane_confirmation': int(campaign.get('cross_lane_confirmation') or 0),
        'source_health_degraded_count': int((campaign.get('source_health_summary') or {}).get('degraded_count') or 0) if isinstance(campaign.get('source_health_summary'), dict) else 0,
    }


def answer_status_for(verb: str, card: dict[str, Any]) -> str:
    if verb == 'compare' and not as_list(card.get('linked_displacement_cases')):
        return 'insufficient_data'
    if verb == 'scenario' and not as_list(card.get('linked_scenarios')):
        return 'insufficient_data'
    if verb in {'sources', 'trace'}:
        refs = card.get('linked_refs') if isinstance(card.get('linked_refs'), dict) else card.get('lineage_refs') if isinstance(card.get('lineage_refs'), dict) else {}
        if not any(as_list(refs.get(key)) for key in ['atoms', 'claims', 'context_gaps', 'opportunity', 'invalidator', 'thesis', 'scenario']):
            return 'insufficient_data'
    return 'ready'


def finalize_card(verb: str, card: dict[str, Any], campaign: dict[str, Any]) -> dict[str, Any]:
    out = dict(card)
    out['required_evidence_groups'] = VERB_GROUPS.get(verb, [])
    out['grounding_summary'] = grounding_summary(campaign)
    out['answer_status'] = answer_status_for(verb, out)
    out['refresh_policy'] = 'refresh_on_report_or_campaign_stage_change'
    out['review_only'] = True
    out['no_execution'] = True
    if out['answer_status'] == 'insufficient_data':
        out['insufficient_data_reason'] = 'Required evidence slice is incomplete; answer should state missing fields instead of inferring.'
    return out


def build_cards(campaign: dict[str, Any]) -> dict[str, dict[str, Any]]:
    title = campaign.get('human_title')
    cid = campaign.get('campaign_id')
    brief = campaign.get('operator_brief') if isinstance(campaign.get('operator_brief'), dict) else {}
    cards = {
        'why': {
            'evidence_slice_id': stable_id('slice', cid, 'why'),
            'title': title,
            'conclusion': brief.get('implication') or campaign.get('directional_implication'),
            'fact_slice': [campaign.get('why_now_delta'), campaign.get('source_freshness'), campaign.get('affected_objects')],
            'interpretation_slice': [campaign.get('capital_relevance'), campaign.get('stage_reason'), brief.get('known_unknown')],
            'to_verify': as_list(brief.get('verify_first')) or as_list(campaign.get('confirmations_needed'))[:4],
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
            'prebrief': {
                'conclusion': brief.get('implication') or campaign.get('directional_implication'),
                'facts': [campaign.get('why_now_delta'), campaign.get('source_freshness'), campaign.get('source_health_summary')],
                'interpretation': [campaign.get('capital_relevance'), campaign.get('stage_reason')],
                'unknowns': as_list(campaign.get('known_unknowns'))[:5],
                'next_checks': as_list(brief.get('verify_first')) or as_list(campaign.get('confirmations_needed'))[:3],
            },
            'campaign': campaign,
        },
    }
    return {verb: finalize_card(verb, card, campaign) for verb, card in cards.items()}


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
