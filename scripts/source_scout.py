#!/usr/bin/env python3
"""Compile review-only source scout candidates for finance intelligence lanes.

This is a source discovery backlog, not source activation. Candidate rows are
metadata-only and cannot wake, support JudgmentEnvelope, or change delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
DEFAULT_OUT = STATE / 'source-scout-candidates.json'
CONTRACT = 'source-scout-candidates-v1'
REQUIRED_LANES = [
    'market_structure',
    'corp_filing_ir',
    'real_economy_alt',
    'news_policy_narrative',
    'human_field_private',
    'internal_private',
]
OPTIONS_IV_METRICS = [
    'iv_rank',
    'iv_percentile',
    'iv_term_structure',
    'skew',
    'open_interest_change',
    'volume_open_interest_ratio',
    'unusual_contract_concentration',
    'chain_snapshot_age_seconds',
    'provider_confidence',
    'point_in_time_replay_supported',
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def safe_out_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def stable_id(lane: str, sublane: str, provider: str) -> str:
    raw = f'{lane}|{sublane}|{provider}'.lower()
    return 'source-scout:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def candidate(
    *,
    lane: str,
    sublane: str,
    provider: str,
    coverage: list[str],
    latency_class: str,
    cost_class: str,
    rights_policy: str,
    api_available: bool,
    historical_depth: str,
    point_in_time_support: bool | None,
    implementation_complexity: str,
    expected_value: str,
    required_metrics: list[str] | None = None,
    credential_ref: str | None = None,
    activation_mode: str = 'candidate_only',
    source_health_id: str | None = None,
    primary_eligible: bool = False,
    risks: list[str] | None = None,
    promotion_blockers: list[str] | None = None,
) -> dict[str, Any]:
    blockers = list(promotion_blockers or [])
    if rights_policy in {'unknown', 'none'}:
        blockers.append('rights_policy_not_approved')
    if point_in_time_support is not True:
        blockers.append('point_in_time_support_not_proven')
    if primary_eligible and blockers:
        blockers.append('primary_eligibility_blocked')
    return {
        'source_candidate_id': stable_id(lane, sublane, provider),
        'lane': lane,
        'sublane': sublane,
        'provider': provider,
        'coverage': coverage,
        'latency_class': latency_class,
        'cost_class': cost_class,
        'rights_policy': rights_policy,
        'api_available': api_available,
        'historical_depth': historical_depth,
        'point_in_time_support': point_in_time_support,
        'implementation_complexity': implementation_complexity,
        'expected_value': expected_value,
        'required_metrics': required_metrics or [],
        'credential_ref': credential_ref,
        'activation_mode': activation_mode,
        'source_health_id': source_health_id or f"source:{provider.lower().replace(' ', '_').replace('/', '_')}_{sublane}",
        'primary_eligible': primary_eligible and not blockers,
        'risks': risks or [],
        'promotion_blockers': sorted(set(blockers)),
        'status': 'shadow_candidate',
        'eligible_for_wake': False,
        'eligible_for_judgment_support': False,
        'no_execution': True,
    }


def build_candidates() -> list[dict[str, Any]]:
    return [
        candidate(
            lane='market_structure',
            sublane='options_iv',
            provider='ORATS',
            coverage=['US listed equity options', 'IV surface', 'skew', 'term structure'],
            latency_class='intraday',
            cost_class='premium',
            rights_policy='derived_only',
            api_available=True,
            historical_depth='multi-year',
            point_in_time_support=True,
            implementation_complexity='medium',
            expected_value='Improve IV rank/percentile/skew sensitivity for non-watchlist and watchlist campaigns.',
            required_metrics=OPTIONS_IV_METRICS,
            credential_ref='ORATS_API_KEY',
            activation_mode='credential_gated',
            source_health_id='source:orats_options_iv',
            primary_eligible=True,
            risks=['paid vendor', 'redistribution must remain derived-only'],
            promotion_blockers=['live_agreement_not_verified'],
        ),
        candidate(
            lane='market_structure',
            sublane='options_iv',
            provider='ThetaData',
            coverage=['US options history', 'greeks', 'IV', 'quotes/trades depending on subscription'],
            latency_class='intraday',
            cost_class='paid',
            rights_policy='derived_only',
            api_available=True,
            historical_depth='multi-year',
            point_in_time_support=True,
            implementation_complexity='medium',
            expected_value='Add point-in-time options history for IV anomaly replay and stale-chain detection.',
            required_metrics=OPTIONS_IV_METRICS,
            credential_ref='THETADATA_BASE_URL',
            activation_mode='local_terminal',
            source_health_id='source:thetadata_options_iv',
            primary_eligible=True,
            risks=['license terms must be checked', 'local storage volume risk'],
        ),
        candidate(
            lane='market_structure',
            sublane='options_iv',
            provider='Polygon Options',
            coverage=['options chain snapshots', 'trades/quotes by plan', 'underlying aggregates'],
            latency_class='intraday',
            cost_class='paid',
            rights_policy='derived_only',
            api_available=True,
            historical_depth='plan-dependent',
            point_in_time_support=None,
            implementation_complexity='medium',
            expected_value='Candidate fallback for broader options coverage when IV surface vendors are not available.',
            required_metrics=OPTIONS_IV_METRICS,
            credential_ref='POLYGON_API_KEY',
            activation_mode='credential_gated',
            source_health_id='source:polygon_options_iv',
            primary_eligible=False,
            risks=['plan-dependent greeks/IV coverage', 'rate limits'],
        ),
        candidate(
            lane='market_structure',
            sublane='options_iv',
            provider='Tradier Options',
            coverage=['option chains', 'courtesy ORATS greeks/IV when greeks=true', 'realtime options for brokerage accounts'],
            latency_class='intraday',
            cost_class='brokerage_or_paid',
            rights_policy='derived_only',
            api_available=True,
            historical_depth='limited',
            point_in_time_support=False,
            implementation_complexity='medium',
            expected_value='Constrained fallback for live chain greeks/IV when dedicated IV vendors are unavailable.',
            required_metrics=OPTIONS_IV_METRICS,
            credential_ref='TRADIER_ACCESS_TOKEN',
            activation_mode='credential_gated',
            source_health_id='source:tradier_options_iv',
            primary_eligible=False,
            risks=['greeks are courtesy data', 'hourly greeks cadence', 'brokerage/account entitlement constraints'],
            promotion_blockers=['courtesy_greeks_not_primary_iv_truth'],
        ),
        candidate(
            lane='market_structure',
            sublane='options_iv',
            provider='IBKR TWS/Gateway',
            coverage=['held option contracts', 'model option computation ticks', 'model IV', 'delta', 'gamma', 'vega', 'theta'],
            latency_class='intraday',
            cost_class='brokerage_session',
            rights_policy='derived_only',
            api_available=True,
            historical_depth='session_snapshot_only',
            point_in_time_support=False,
            implementation_complexity='medium',
            expected_value='Fallback/private source for held-contract Greeks and model IV when a read-only TWS/Gateway session is already active.',
            required_metrics=OPTIONS_IV_METRICS,
            credential_ref='IBKR_OPTIONS_IV_ENABLED',
            activation_mode='broker_session_local_gateway',
            source_health_id='source:ibkr_options_iv',
            primary_eligible=False,
            risks=['requires active broker session', 'market data subscriptions required', 'must not place orders or claim brokerage authority'],
            promotion_blockers=['broker_session_required', 'held_contracts_only', 'not_primary_iv_truth'],
        ),
        candidate(
            lane='market_structure',
            sublane='options_flow_proxy',
            provider='Nasdaq option-chain',
            coverage=['delayed option chain table', 'volume', 'open interest'],
            latency_class='delayed_intraday',
            cost_class='free',
            rights_policy='derived_only',
            api_available=True,
            historical_depth='snapshot_only',
            point_in_time_support=False,
            implementation_complexity='low',
            expected_value='Keep as conservative proxy, explicitly penalized when no primary options IV source exists.',
            required_metrics=['volume_open_interest_ratio', 'chain_snapshot_age_seconds', 'provider_confidence'],
            activation_mode='proxy_fallback',
            source_health_id='source:nasdaq_options_flow_proxy',
            primary_eligible=False,
            risks=['not a primary IV source', 'fragile endpoint', 'limited replay'],
        ),
        candidate(
            lane='market_structure',
            sublane='price_volume',
            provider='Polygon Aggregates',
            coverage=['US equities', 'ETF aggregates', 'intraday bars'],
            latency_class='intraday',
            cost_class='paid',
            rights_policy='derived_only',
            api_available=True,
            historical_depth='multi-year plan-dependent',
            point_in_time_support=True,
            implementation_complexity='medium',
            expected_value='Upgrade yfinance fallback into point-in-time market tape for campaign replay.',
            risks=['paid plan', 'rate limits', 'redistribution constraints'],
        ),
        candidate(
            lane='corp_filing_ir',
            sublane='sec_filings',
            provider='SEC submissions/companyfacts APIs',
            coverage=['10-K', '10-Q', '8-K', 'Form 4', 'company facts'],
            latency_class='event_driven',
            cost_class='free',
            rights_policy='raw_ok',
            api_available=True,
            historical_depth='multi-year',
            point_in_time_support=True,
            implementation_complexity='low',
            expected_value='Close issuer-confirmation gaps and prevent narrative-only promotion.',
            risks=['fair access and user-agent compliance required'],
        ),
        candidate(
            lane='corp_filing_ir',
            sublane='issuer_ir',
            provider='Issuer IR RSS / press release pages',
            coverage=['press releases', 'presentations', 'earnings dates'],
            latency_class='event_driven',
            cost_class='free',
            rights_policy='derived_only',
            api_available=False,
            historical_depth='issuer-dependent',
            point_in_time_support=None,
            implementation_complexity='high',
            expected_value='Adds primary issuer confirmation for campaign claims where SEC is too slow or incomplete.',
            risks=['site-specific scraping', 'robots/terms review required'],
        ),
        candidate(
            lane='real_economy_alt',
            sublane='jobs',
            provider='Company careers / job posting aggregations',
            coverage=['hiring velocity', 'role mix', 'geography'],
            latency_class='daily',
            cost_class='free_or_paid',
            rights_policy='derived_only',
            api_available=False,
            historical_depth='must_build',
            point_in_time_support=False,
            implementation_complexity='high',
            expected_value='Add peacetime demand/capex hints for company campaigns.',
            risks=['anti-scraping', 'entity matching noise'],
        ),
        candidate(
            lane='real_economy_alt',
            sublane='energy_supply',
            provider='EIA / public energy datasets',
            coverage=['oil inventories', 'production', 'imports/exports', 'regional energy data'],
            latency_class='daily_weekly',
            cost_class='free',
            rights_policy='raw_ok',
            api_available=True,
            historical_depth='multi-year',
            point_in_time_support=True,
            implementation_complexity='low',
            expected_value='Cross-check BNO/oil/Hormuz narratives with official supply data when available.',
            risks=['release lag', 'macro not single-name specific'],
        ),
        candidate(
            lane='news_policy_narrative',
            sublane='entity_event',
            provider='RavenPack / structured news analytics',
            coverage=['entity relevance', 'novelty', 'event classification', 'impact'],
            latency_class='near_realtime',
            cost_class='premium',
            rights_policy='derived_only',
            api_available=True,
            historical_depth='vendor-dependent',
            point_in_time_support=True,
            implementation_complexity='high',
            expected_value='Replace generic news summaries with entity/event/novelty intelligence.',
            risks=['premium vendor', 'strict redistribution controls'],
        ),
        candidate(
            lane='human_field_private',
            sublane='expert_transcript',
            provider='Licensed expert transcript import',
            coverage=['expert interviews', 'channel checks', 'private research notes'],
            latency_class='event_driven',
            cost_class='premium',
            rights_policy='none',
            api_available=False,
            historical_depth='import-dependent',
            point_in_time_support=True,
            implementation_complexity='medium',
            expected_value='Adds compliant private research lane without exposing raw content to reviewer packets.',
            risks=['MNPI exclusion required', 'raw redistribution forbidden'],
        ),
        candidate(
            lane='internal_private',
            sublane='thread_unknowns',
            provider='OpenClaw finance thread ledger',
            coverage=['operator follow-up unknowns', 'challenge questions', 'source requests'],
            latency_class='event_driven',
            cost_class='internal',
            rights_policy='none',
            api_available=False,
            historical_depth='local_runtime',
            point_in_time_support=True,
            implementation_complexity='medium',
            expected_value='Turns repeated user questions and unresolved unknowns into source scouting demand.',
            risks=['Discord conversation must not be committed', 'privacy boundary'],
        ),
    ]


def summarize(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    lanes = {lane: 0 for lane in REQUIRED_LANES}
    sublanes: dict[str, int] = {}
    for row in candidates:
        lanes[row['lane']] = lanes.get(row['lane'], 0) + 1
        sublanes[row['sublane']] = sublanes.get(row['sublane'], 0) + 1
    return {
        'candidate_count': len(candidates),
        'lanes': lanes,
        'sublanes': sublanes,
        'options_iv_candidate_count': sum(1 for row in candidates if row['sublane'] == 'options_iv'),
        'primary_options_iv_candidate_count': sum(1 for row in candidates if row.get('sublane') == 'options_iv' and row.get('primary_eligible')),
        'promotion_ready_count': sum(1 for row in candidates if not row['promotion_blockers']),
    }


def build_report() -> dict[str, Any]:
    candidates = build_candidates()
    return {
        'generated_at': now_iso(),
        'status': 'pass',
        'contract': CONTRACT,
        'summary': summarize(candidates),
        'candidates': candidates,
        'activation_boundary': 'shadow-only; candidates cannot wake, support judgment, mutate thresholds, or change Discord delivery',
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compile review-only source scout candidates.')
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_out_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    report = build_report()
    atomic_write_json(out, report)
    print(json.dumps({'status': report['status'], 'candidate_count': report['summary']['candidate_count'], 'out': str(out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
