#!/usr/bin/env python3
"""Fetch deterministic broad-market sector/credit/rates/commodity proxies."""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

try:
    import yfinance as yf
except ImportError:
    yf = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_io import atomic_write_json


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
DEFAULT_OUT = STATE / 'broad-market-proxy.json'
TZ_CHI = ZoneInfo('America/Chicago')
TZ_ET = ZoneInfo('America/New_York')

UNIVERSE = {
    'sector': ['XLK', 'XLE', 'XLF', 'XLV', 'XLI', 'XLY', 'XLP', 'XLU', 'XLB', 'IWM'],
    'rates_credit': ['TLT', 'IEF', 'HYG', 'LQD'],
    'commodity': ['USO', 'GLD', 'IAU', 'DBC'],
    'benchmark': ['SPY', 'QQQ'],
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def safe_out_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def finite_positive(value: float) -> bool:
    return value > 0 and value == value and value not in {float('inf'), float('-inf')}


def info_value(info: Any, *names: str, default=None):
    for name in names:
        try:
            value = info.get(name) if isinstance(info, dict) else getattr(info, name, None)
        except Exception:
            value = None
        if value is not None:
            return value
    return default


def fetch_single(symbol: str) -> dict[str, Any]:
    now = now_utc().isoformat()
    if yf is None:
        return {'status': 'error', 'error': 'yfinance not installed', 'as_of': now}
    try:
        info = yf.Ticker(symbol).fast_info
        price = float(info_value(info, 'last_price', 'lastPrice', default=0) or 0)
        prev = float(info_value(info, 'previous_close', 'regular_market_previous_close', default=0) or 0)
        if not finite_positive(price) or not finite_positive(prev):
            return {'status': 'error', 'error': f'invalid broad-market snapshot: price={price} previous_close={prev}', 'as_of': now}
        change = round(price - prev, 4)
        pct = round((change / prev) * 100, 4)
        return {
            'status': 'ok',
            'price': price,
            'previous_close': prev,
            'change': change,
            'pct_change': pct,
            'volume': int(info_value(info, 'last_volume', default=0) or 0),
            'as_of': now,
        }
    except Exception as exc:
        return {'status': 'error', 'error': str(exc), 'as_of': now}


def flatten_universe(universe: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for values in universe.values():
        out.extend(values)
    return sorted(set(out))


def classify_symbol(symbol: str) -> str:
    for category, symbols in UNIVERSE.items():
        if symbol in symbols:
            return category
    return 'unknown'


def build_proxy(quotes: dict[str, dict[str, Any]], fetched_at: str) -> dict[str, Any]:
    spy = quotes.get('SPY', {})
    spy_pct = float(spy.get('pct_change') or 0) if spy.get('status') == 'ok' else 0.0
    rows = []
    for symbol, quote in quotes.items():
        if quote.get('status') != 'ok':
            continue
        pct = float(quote.get('pct_change') or 0)
        volume = float(quote.get('volume') or 0)
        rel = round(pct - spy_pct, 4)
        pressure = round(abs(rel) * math.log10(volume + 10), 4)
        category = classify_symbol(symbol)
        rows.append({
            'symbol': symbol,
            'category': category,
            'price': quote.get('price'),
            'pct_change': pct,
            'relative_to_spy_pct': rel,
            'volume': int(volume),
            'pressure_score': pressure,
            'direction': 'bullish' if rel > 0 else 'bearish' if rel < 0 else 'neutral',
            'as_of': quote.get('as_of') or fetched_at,
            'semantics': semantics_for(category, symbol, rel),
        })
    rows.sort(key=lambda item: abs(item['relative_to_spy_pct']) + item['pressure_score'] / 100, reverse=True)
    return {
        'top_dislocations': rows[:10],
        'by_category': {
            category: [row for row in rows if row['category'] == category][:5]
            for category in ['sector', 'rates_credit', 'commodity', 'benchmark']
        },
    }


def semantics_for(category: str, symbol: str, rel: float) -> str:
    if category == 'sector':
        return 'sector_rotation_proxy'
    if category == 'rates_credit':
        return 'credit_or_rates_pressure_proxy'
    if category == 'commodity':
        return 'commodity_pressure_proxy'
    return 'broad_market_benchmark'


def build_report(universe: dict[str, list[str]] | None = None) -> dict[str, Any]:
    universe = universe or UNIVERSE
    fetched = now_utc()
    quotes = {symbol: fetch_single(symbol) for symbol in flatten_universe(universe)}
    proxy = build_proxy(quotes, fetched.isoformat())
    return {
        'generated_at': fetched.isoformat(),
        'generated_at_chicago': fetched.astimezone(TZ_CHI).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'generated_at_et': fetched.astimezone(TZ_ET).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'status': 'pass' if any(q.get('status') == 'ok' for q in quotes.values()) else 'degraded',
        'source': 'yfinance',
        'freshness_semantics': 'provider quote snapshot; broad-market proxy, not fund-flow truth',
        'universe': universe,
        'quotes': quotes,
        **proxy,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_out_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    report = build_report()
    atomic_write_json(out, report)
    print(json.dumps({'status': report['status'], 'top_count': len(report['top_dislocations']), 'out': str(out)}, ensure_ascii=False))
    return 0 if report['status'] in {'pass', 'degraded'} else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
