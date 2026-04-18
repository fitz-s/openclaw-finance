#!/usr/bin/env python3
"""Compile a shadow options IV/flow surface from existing proxy data.

This does not fetch option chains. It makes proxy limitations explicit so later
campaign/undercurrent/follow-up logic can penalize stale or missing IV context.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OPTIONS_PROXY = STATE / 'options-flow-proxy.json'
PROVIDER_SNAPSHOT = STATE / 'options-iv-provider-snapshot.json'
OUT = STATE / 'options-iv-surface.json'
CONTRACT = 'options-iv-surface-v1-shadow'
SURFACE_POLICY_VERSION = 'options-iv-surface-v2-shadow'
FRESH_SECONDS = 30 * 60
AGING_SECONDS = 2 * FRESH_SECONDS


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(timezone.utc)
    except Exception:
        return None


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def number(value: Any) -> float | None:
    try:
        if value is None or value != value:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def staleness(age: int | None) -> str:
    if age is None:
        return 'unknown'
    if age <= FRESH_SECONDS:
        return 'fresh'
    if age <= AGING_SECONDS:
        return 'aging'
    return 'stale'


def base_confidence(chain_staleness: str, *, proxy_only: bool, has_iv: bool) -> tuple[float, list[str]]:
    confidence = 0.75 if has_iv else 0.45
    penalties: list[str] = []
    if proxy_only:
        confidence -= 0.10
        penalties.append('proxy_only_options_chain')
    if not has_iv:
        confidence -= 0.15
        penalties.append('missing_iv_surface')
    if chain_staleness == 'aging':
        confidence -= 0.10
        penalties.append('aging_chain_snapshot')
    elif chain_staleness == 'stale':
        confidence -= 0.25
        penalties.append('stale_chain_snapshot')
    elif chain_staleness == 'unknown':
        confidence -= 0.20
        penalties.append('unknown_chain_snapshot_age')
    return round(max(0.05, min(confidence, 0.95)), 4), penalties


def provider_confidence(events: list[dict[str, Any]], chain_staleness: str) -> tuple[float, list[str]]:
    base_values = [number(event.get('provider_confidence_base')) for event in events]
    base = max([value for value in base_values if value is not None], default=0.65)
    penalties: list[str] = []
    if not any(event_iv(event) is not None for event in events):
        base -= 0.20
        penalties.append('missing_iv_surface')
    if chain_staleness == 'aging':
        base -= 0.10
        penalties.append('aging_provider_snapshot')
    elif chain_staleness == 'stale':
        base -= 0.25
        penalties.append('stale_provider_snapshot')
    elif chain_staleness == 'unknown':
        base -= 0.15
        penalties.append('unknown_provider_snapshot_age')
    for event in events:
        for penalty in event.get('confidence_penalties', []) if isinstance(event.get('confidence_penalties'), list) else []:
            if penalty not in penalties:
                penalties.append(str(penalty))
                base -= 0.05
    return round(max(0.05, min(base, 0.95)), 4), penalties


def event_iv(event: dict[str, Any]) -> float | None:
    iv = number(event.get('implied_volatility'))
    if iv is None or iv <= 0:
        return None
    return iv


def summarize_symbol(symbol: str, events: list[dict[str, Any]], *, generated_at: datetime | None, now: datetime) -> dict[str, Any]:
    age = int((now - generated_at).total_seconds()) if generated_at else None
    chain_staleness = staleness(age)
    ivs = [iv for event in events if (iv := event_iv(event)) is not None]
    call_ivs = [iv for event in events if event.get('call_put') == 'call' and (iv := event_iv(event)) is not None]
    put_ivs = [iv for event in events if event.get('call_put') == 'put' and (iv := event_iv(event)) is not None]
    ratios = [ratio for event in events if (ratio := number(event.get('volume_oi_ratio'))) is not None]
    unusual = [event for event in events if str(event.get('option_signal_type')) == 'options_unusual_activity_proxy']
    provider_set = sorted({str(event.get('provider') or 'unknown') for event in events})
    proxy_only = not ivs or any('nasdaq' in provider.lower() for provider in provider_set)
    confidence, penalties = base_confidence(chain_staleness, proxy_only=proxy_only, has_iv=bool(ivs))
    return {
        'symbol': symbol,
        'event_count': len(events),
        'provider_set': provider_set,
        'chain_snapshot_age_seconds': age,
        'chain_staleness': chain_staleness,
        'proxy_only': proxy_only,
        'provider_confidence': confidence,
        'confidence_penalties': penalties,
        'iv_observation_count': len(ivs),
        'avg_implied_volatility': round(mean(ivs), 4) if ivs else None,
        'max_implied_volatility': round(max(ivs), 4) if ivs else None,
        'call_put_skew': round(mean(call_ivs) - mean(put_ivs), 4) if call_ivs and put_ivs else None,
        'max_volume_oi_ratio': round(max(ratios), 4) if ratios else None,
        'unusual_contract_count': len(unusual),
        'top_contracts': [
            {
                'expiry': event.get('expiry'),
                'call_put': event.get('call_put'),
                'strike': event.get('strike'),
                'volume': event.get('volume'),
                'open_interest': event.get('open_interest'),
                'volume_oi_ratio': event.get('volume_oi_ratio'),
                'implied_volatility': event.get('implied_volatility'),
                'option_signal_type': event.get('option_signal_type'),
                'score': event.get('score'),
            }
            for event in sorted(events, key=lambda item: (number(item.get('score')) or 0, number(item.get('notional_proxy')) or 0), reverse=True)[:5]
        ],
        'no_execution': True,
    }


def summarize_provider_symbol(symbol: str, events: list[dict[str, Any]], *, generated_at: datetime | None, now: datetime) -> dict[str, Any]:
    age = int((now - generated_at).total_seconds()) if generated_at else None
    chain_staleness = staleness(age)
    ivs = [iv for event in events if (iv := event_iv(event)) is not None]
    call_ivs = [iv for event in events if str(event.get('call_put')).lower() in {'call', 'c'} and (iv := event_iv(event)) is not None]
    put_ivs = [iv for event in events if str(event.get('call_put')).lower() in {'put', 'p'} and (iv := event_iv(event)) is not None]
    ratios = [ratio for event in events if (ratio := number(event.get('volume_oi_ratio'))) is not None]
    provider_set = sorted({str(event.get('provider') or 'unknown') for event in events})
    source_health_refs = sorted({str(event.get('source_id')) for event in events if event.get('source_id')})
    confidence, penalties = provider_confidence(events, chain_staleness)
    return {
        'symbol': symbol,
        'event_count': len(events),
        'provider_set': provider_set,
        'source_health_refs': source_health_refs,
        'rights_policy': 'derived_only',
        'derived_only': True,
        'raw_payload_retained': False,
        'point_in_time_replay_supported': any(event.get('point_in_time_replay_supported') is True for event in events),
        'chain_snapshot_age_seconds': age,
        'chain_staleness': chain_staleness,
        'proxy_only': False,
        'provider_confidence': confidence,
        'confidence_penalties': penalties,
        'iv_observation_count': len(ivs),
        'iv_rank': max((number(event.get('iv_rank')) for event in events if number(event.get('iv_rank')) is not None), default=None),
        'iv_percentile': max((number(event.get('iv_percentile')) for event in events if number(event.get('iv_percentile')) is not None), default=None),
        'term_structure': term_structure(events),
        'avg_implied_volatility': round(mean(ivs), 4) if ivs else None,
        'max_implied_volatility': round(max(ivs), 4) if ivs else None,
        'call_put_skew': round(mean(call_ivs) - mean(put_ivs), 4) if call_ivs and put_ivs else None,
        'max_volume_oi_ratio': round(max(ratios), 4) if ratios else None,
        'unusual_contract_count': sum(1 for event in events if (number(event.get('volume_oi_ratio')) or 0) >= 1 and (number(event.get('volume')) or 0) >= 100),
        'top_contracts': [
            {
                'expiration': event.get('expiration'),
                'expiry': event.get('expiration'),
                'call_put': event.get('call_put'),
                'strike': event.get('strike'),
                'volume': event.get('volume'),
                'open_interest': event.get('open_interest'),
                'volume_oi_ratio': event.get('volume_oi_ratio'),
                'implied_volatility': event.get('implied_volatility'),
                'provider': event.get('provider'),
            }
            for event in sorted(events, key=lambda item: (number(item.get('implied_volatility')) or 0, number(item.get('volume_oi_ratio')) or 0), reverse=True)[:5]
        ],
        'no_execution': True,
    }


def term_structure(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_expiry: dict[str, list[float]] = {}
    for event in events:
        expiry = str(event.get('expiration') or event.get('expiry') or '')
        iv = event_iv(event)
        if expiry and iv is not None:
            by_expiry.setdefault(expiry, []).append(iv)
    points = [
        {'expiration': expiry, 'avg_implied_volatility': round(mean(values), 4), 'observation_count': len(values)}
        for expiry, values in sorted(by_expiry.items())
    ]
    slope = None
    if len(points) >= 2:
        slope = round(points[-1]['avg_implied_volatility'] - points[0]['avg_implied_volatility'], 4)
    return {'points': points[:8], 'slope': slope}


def compile_surface(proxy: dict[str, Any], *, provider_snapshot: dict[str, Any] | None = None, now: datetime | None = None) -> dict[str, Any]:
    now = now or now_utc()
    provider_snapshot = provider_snapshot or {}
    provider_generated_at = parse_ts(provider_snapshot.get('generated_at'))
    provider_events = [
        event for event in provider_snapshot.get('observations', [])
        if isinstance(event, dict) and event.get('symbol')
    ]
    provider_grouped: dict[str, list[dict[str, Any]]] = {}
    for event in provider_events:
        provider_grouped.setdefault(str(event['symbol']).upper(), []).append(event)
    provider_rows = [
        summarize_provider_symbol(symbol, symbol_events, generated_at=provider_generated_at, now=now)
        for symbol, symbol_events in sorted(provider_grouped.items())
    ]

    generated_at = parse_ts(proxy.get('generated_at'))
    events = [event for event in proxy.get('top_events', []) if isinstance(event, dict) and event.get('symbol')]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        grouped.setdefault(str(event['symbol']).upper(), []).append(event)
    provider_symbols = {row['symbol'] for row in provider_rows}
    proxy_rows = [
        summarize_symbol(symbol, symbol_events, generated_at=generated_at, now=now)
        for symbol, symbol_events in sorted(grouped.items())
        if symbol not in provider_symbols
    ]
    for row in proxy_rows:
        row['confidence_penalties'] = sorted(set(row.get('confidence_penalties', []) + ['missing_primary_options_iv_source']))
        row['source_health_refs'] = ['source:nasdaq_options_flow_proxy', 'source:yfinance_options_proxy']
        row['rights_policy'] = 'derived_only'
        row['derived_only'] = True
        row['raw_payload_retained'] = False
        row['point_in_time_replay_supported'] = False
    rows = provider_rows + proxy_rows
    rows.sort(key=lambda row: (row['provider_confidence'], row.get('unusual_contract_count') or 0, row.get('max_volume_oi_ratio') or 0), reverse=True)
    stale_count = sum(1 for row in rows if row['chain_staleness'] in {'aging', 'stale', 'unknown'})
    missing_iv_count = sum(1 for row in rows if row['iv_observation_count'] == 0)
    provider_set = sorted({provider for row in rows for provider in row.get('provider_set', [])})
    primary_provider_set = sorted({provider for row in provider_rows for provider in row.get('provider_set', [])})
    primary_source_status = 'ok' if provider_rows else 'degraded' if provider_snapshot else 'missing'
    return {
        'generated_at': now.isoformat().replace('+00:00', 'Z'),
        'status': 'pass' if provider_rows else 'degraded' if proxy or provider_snapshot else 'empty',
        'contract': CONTRACT,
        'surface_policy_version': SURFACE_POLICY_VERSION,
        'source': f'{PROVIDER_SNAPSHOT} + {OPTIONS_PROXY}',
        'primary_source_status': primary_source_status,
        'primary_provider_set': primary_provider_set,
        'provider_set': provider_set,
        'source_health_refs': sorted({ref for row in rows for ref in row.get('source_health_refs', [])}),
        'rights_policy': 'derived_only' if rows else 'unknown',
        'point_in_time_replay_supported': any(row.get('point_in_time_replay_supported') is True for row in rows),
        'derived_only': True,
        'raw_payload_retained': False,
        'provider_snapshot_status': provider_snapshot.get('status') if provider_snapshot else None,
        'provider_snapshot_observation_count': provider_snapshot.get('observation_count') if provider_snapshot else 0,
        'source_generated_at': proxy.get('generated_at'),
        'source_status': proxy.get('status'),
        'symbol_count': len(rows),
        'symbols': rows,
        'summary': {
            'symbol_count': len(rows),
            'missing_iv_count': missing_iv_count,
            'stale_or_unknown_chain_count': stale_count,
            'proxy_only_count': sum(1 for row in rows if row['proxy_only']),
            'provider_backed_count': len(provider_rows),
            'primary_source_status': primary_source_status,
            'min_provider_confidence': min((row['provider_confidence'] for row in rows), default=None),
            'max_provider_confidence': max((row['provider_confidence'] for row in rows), default=None),
        },
        'shadow_only': True,
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compile shadow options IV surface from existing proxy data.')
    parser.add_argument('--proxy', default=str(OPTIONS_PROXY))
    parser.add_argument('--provider-snapshot', default=str(PROVIDER_SNAPSHOT))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_state_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    proxy = load_json_safe(Path(args.proxy), {}) or {}
    provider_snapshot = load_json_safe(Path(args.provider_snapshot), {}) or {}
    report = compile_surface(proxy, provider_snapshot=provider_snapshot)
    atomic_write_json(out, report)
    print(json.dumps({'status': report['status'], 'symbol_count': report['symbol_count'], 'out': str(out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
