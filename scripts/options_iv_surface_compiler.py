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
OUT = STATE / 'options-iv-surface.json'
CONTRACT = 'options-iv-surface-v1-shadow'
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


def compile_surface(proxy: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    now = now or now_utc()
    generated_at = parse_ts(proxy.get('generated_at'))
    events = [event for event in proxy.get('top_events', []) if isinstance(event, dict) and event.get('symbol')]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        grouped.setdefault(str(event['symbol']).upper(), []).append(event)
    rows = [summarize_symbol(symbol, symbol_events, generated_at=generated_at, now=now) for symbol, symbol_events in sorted(grouped.items())]
    rows.sort(key=lambda row: (row['provider_confidence'], row.get('unusual_contract_count') or 0, row.get('max_volume_oi_ratio') or 0), reverse=True)
    stale_count = sum(1 for row in rows if row['chain_staleness'] in {'aging', 'stale', 'unknown'})
    missing_iv_count = sum(1 for row in rows if row['iv_observation_count'] == 0)
    return {
        'generated_at': now.isoformat().replace('+00:00', 'Z'),
        'status': 'pass' if rows else 'empty' if proxy else 'degraded',
        'contract': CONTRACT,
        'source': str(OPTIONS_PROXY),
        'source_generated_at': proxy.get('generated_at'),
        'source_status': proxy.get('status'),
        'symbol_count': len(rows),
        'symbols': rows,
        'summary': {
            'symbol_count': len(rows),
            'missing_iv_count': missing_iv_count,
            'stale_or_unknown_chain_count': stale_count,
            'proxy_only_count': sum(1 for row in rows if row['proxy_only']),
            'min_provider_confidence': min((row['provider_confidence'] for row in rows), default=None),
            'max_provider_confidence': max((row['provider_confidence'] for row in rows), default=None),
        },
        'shadow_only': True,
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compile shadow options IV surface from existing proxy data.')
    parser.add_argument('--proxy', default=str(OPTIONS_PROXY))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_state_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    proxy = load_json_safe(Path(args.proxy), {}) or {}
    report = compile_surface(proxy)
    atomic_write_json(out, report)
    print(json.dumps({'status': report['status'], 'symbol_count': report['symbol_count'], 'out': str(out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
