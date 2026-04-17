#!/usr/bin/env python3
"""Route finance follow-up requests to verb-specific campaign/bundle context."""
from __future__ import annotations

import argparse
import hashlib
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
VERB_GROUPS = {
    'why': ['campaign_projection', 'recent_claims', 'source_health', 'promotion_reason', 'event_timeline'],
    'challenge': ['countercase_memo', 'invalidators', 'contradictions', 'denied_hypotheses', 'freshness_risks'],
    'compare': ['capital_graph_slice', 'displacement_case', 'bucket_competition', 'portfolio_attachment'],
    'scenario': ['scenario_exposure', 'hedge_coverage', 'crowding_risk', 'linked_campaigns'],
    'sources': ['source_atoms', 'claim_lineage', 'rights_and_redaction', 'freshness_by_lane'],
    'trace': ['handle_to_claim_to_atom_to_source_lineage'],
    'expand': ['prepared_campaign_cache', 'report_bundle_summary'],
}
VERB_ALIASES = {
    'why': 'why',
    '为什么': 'why',
    '为何': 'why',
    'challenge': 'challenge',
    '质疑': 'challenge',
    '反证': 'challenge',
    'compare': 'compare',
    '比较': 'compare',
    '对比': 'compare',
    'scenario': 'scenario',
    '情景': 'scenario',
    '场景': 'scenario',
    'sources': 'sources',
    'source': 'sources',
    '来源': 'sources',
    'trace': 'trace',
    '追溯': 'trace',
    'expand': 'expand',
    '详细': 'expand',
    '详细报告': 'expand',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(part or '') for part in parts)
    return f'{prefix}:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def parse_query(query: str) -> dict[str, Any]:
    cleaned = query.strip()
    parts = cleaned.split()
    first = parts[0].lower() if parts else ''
    verb = VERB_ALIASES.get(first, first)
    handles = parts[1:]
    if verb not in VALID_VERBS and ('详细' in cleaned or 'expand' in cleaned.lower()):
        verb = 'expand'
        handles = [re.sub(r'(的)?详细报告|详细|expand', '', cleaned, flags=re.I).strip()] if cleaned else []
    return {
        'verb': verb,
        'primary_handle': handles[0] if handles else '',
        'secondary_handle': handles[1] if len(handles) > 1 else '',
    }


def campaign_by_id(campaign_board: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    campaigns = [c for c in campaign_board.get('campaigns', []) if isinstance(c, dict) and c.get('campaign_id')]
    for idx, campaign in enumerate(campaigns, start=1):
        aliases = [
            campaign.get('campaign_id'),
            campaign.get('thread_key'),
            f'C{idx}',
        ]
        for alias in aliases:
            if alias:
                out[str(alias)] = campaign
    return out


def bundle_card_by_handle(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(c.get('handle')): c
        for c in bundle.get('object_cards', []) if isinstance(c, dict) and c.get('handle')
    }


def campaign_aliases(bundle: dict[str, Any]) -> dict[str, str]:
    aliases = bundle.get('campaign_alias_map') if isinstance(bundle.get('campaign_alias_map'), dict) else {}
    return {str(k): str(v) for k, v in aliases.items() if k and v}


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def required_slice_keys(verb: str) -> list[str]:
    return {
        'why': ['why_now_delta', 'source_freshness', 'capital_relevance', 'confirmations_needed'],
        'challenge': ['why_not_now', 'kill_switches', 'source_freshness'],
        'compare': ['capital_relevance', 'linked_thesis', 'linked_displacement_cases'],
        'scenario': ['linked_scenarios', 'capital_relevance'],
        'sources': ['source_freshness', 'linked_thesis', 'linked_scenarios', 'linked_opportunities', 'linked_invalidators'],
        'trace': ['linked_atoms', 'linked_claims', 'linked_context_gaps', 'source_health_summary'],
        'expand': ['campaign'],
    }.get(verb, [])


def context_gap_guidance(campaign: dict[str, Any] | None, missing_fields: list[str]) -> list[dict[str, Any]]:
    if not campaign or not missing_fields:
        return []
    known_unknowns = [gap for gap in campaign.get('known_unknowns', []) if isinstance(gap, dict)]
    guidance: list[dict[str, Any]] = []
    for field in missing_fields:
        related_gap = known_unknowns[0] if known_unknowns else {}
        guidance.append({
            'missing_field': field,
            'gap_id': related_gap.get('gap_id'),
            'missing_lane': related_gap.get('missing_lane') or field,
            'why_load_bearing': related_gap.get('why_load_bearing') or f'{field} is required for this follow-up verb.',
            'closure_condition': related_gap.get('closure_condition') or f'Provide {field} evidence before answering strongly.',
            'gap_status': related_gap.get('gap_status') or 'open',
        })
    return guidance


def evidence_coverage(campaign: dict[str, Any] | None, verb: str, missing_fields: list[str]) -> dict[str, Any]:
    required = required_slice_keys(verb)
    present = []
    if campaign:
        present = [key for key in required if key not in missing_fields and key != 'campaign']
    return {
        'required_keys': required,
        'required_evidence_groups': VERB_GROUPS.get(verb, []),
        'present_keys': present,
        'missing_fields': missing_fields,
        'coverage_status': 'insufficient' if missing_fields else 'complete',
    }


def missing_fields_for_campaign(campaign: dict[str, Any] | None, verb: str) -> list[str]:
    if not campaign:
        return []
    missing = []
    for key in required_slice_keys(verb):
        if key == 'campaign':
            continue
        if is_missing(campaign.get(key)):
            missing.append(key)
    return missing


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
    aliases = campaign_aliases(bundle)
    cache = campaign_cache.get('cache', {}) if isinstance(campaign_cache.get('cache'), dict) else {}
    resolved_primary = aliases.get(primary, primary)
    resolved_secondary = aliases.get(secondary, secondary)
    selected_campaign = campaigns.get(resolved_primary)
    selected_card = cards.get(primary)
    if primary and not selected_campaign and not selected_card:
        errors.append(f'unknown_primary_handle:{primary}')
    cache_slice = None
    if selected_campaign:
        cache_slice = cache.get(str(selected_campaign.get('campaign_id')), {}).get(verb)
    if selected_campaign and cache_slice is None:
        warnings.append(f'cache_miss:{verb}:{resolved_primary}')

    evidence_slice = required_slice_keys(verb)
    missing_fields = missing_fields_for_campaign(selected_campaign, verb)
    insufficient_data = bool(missing_fields and verb in {'compare', 'scenario', 'sources', 'trace'})
    coverage = evidence_coverage(selected_campaign, verb, missing_fields)
    gaps = context_gap_guidance(selected_campaign, missing_fields)
    evidence_slice_id = stable_id('slice', bundle.get('bundle_id'), campaign_board.get('contract'), verb, resolved_primary, resolved_secondary, ','.join(evidence_slice))

    return {
        'generated_at': now_iso(),
        'status': 'pass' if not errors else 'fail',
        'query': query,
        'verb': verb,
        'primary_handle': primary,
        'secondary_handle': secondary,
        'resolved_primary_handle': resolved_primary,
        'resolved_secondary_handle': resolved_secondary,
        'evidence_slice_id': evidence_slice_id if not errors else None,
        'errors': errors,
        'warnings': warnings,
        'selected_campaign': selected_campaign,
        'selected_object_card': selected_card,
        'cache_slice': cache_slice,
        'required_evidence_groups': VERB_GROUPS.get(verb, []),
        'evidence_slice_keys': evidence_slice,
        'evidence_slice_coverage': coverage,
        'missing_fields': missing_fields,
        'context_gap_guidance': gaps,
        'insufficient_data': insufficient_data,
        'recommended_answer_status': 'insufficient_data' if insufficient_data else 'answered',
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
