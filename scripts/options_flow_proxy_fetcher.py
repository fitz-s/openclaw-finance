#!/usr/bin/env python3
"""Fetch conservative options flow / IV-OI proxy from Nasdaq with yfinance fallback."""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
try:
    import yfinance as yf
except ImportError:
    yf = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
WATCHLIST = FINANCE / 'state' / 'watchlist-resolved.json'
FALLBACK_WATCHLIST = FINANCE / 'watchlists' / 'core.json'
DEFAULT_OUT = STATE / 'options-flow-proxy.json'
TZ_CHI = ZoneInfo('America/Chicago')
TZ_ET = ZoneInfo('America/New_York')
DEFAULT_SYMBOL_LIMIT = 20
DEFAULT_EXPIRY_LIMIT = 2
NASDAQ_OPTIONS_URL = 'https://api.nasdaq.com/api/quote/{symbol}/option-chain?assetclass=stocks'


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


def watchlist_symbols(path: Path = WATCHLIST, limit: int = DEFAULT_SYMBOL_LIMIT) -> list[str]:
    payload = load_json_safe(path, {}) or {}
    if not payload and path == WATCHLIST:
        payload = load_json_safe(FALLBACK_WATCHLIST, {}) or {}
    symbols = []
    for item in payload.get('tickers', []) if isinstance(payload, dict) else []:
        if isinstance(item, dict) and item.get('symbol'):
            symbols.append(str(item['symbol']).replace('/', '-'))
    return [symbol for symbol in symbols if '-' not in symbol][:limit]


def rows_from_table(table: Any) -> list[dict[str, Any]]:
    if table is None:
        return []
    if isinstance(table, list):
        return [row for row in table if isinstance(row, dict)]
    if hasattr(table, 'to_dict'):
        try:
            return table.to_dict('records')
        except Exception:
            return []
    return []


def number(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value != value:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def classify(row: dict[str, Any], *, symbol: str, expiry: str, call_put: str) -> dict[str, Any]:
    volume = number(row.get('volume'))
    oi = number(row.get('openInterest'))
    iv = number(row.get('impliedVolatility'))
    last_price = number(row.get('lastPrice') or row.get('last_price'))
    strike = number(row.get('strike'))
    ratio = round(volume / oi, 4) if oi > 0 else None
    notional = round(volume * last_price * 100, 2) if last_price > 0 and volume > 0 else 0.0
    score = round(math.log10(volume + 10) * (ratio or 0.25) * (1 + min(iv, 3)), 4)
    signal_type = 'options_unusual_activity_proxy' if volume >= 500 and (ratio or 0) >= 1 else 'options_chain_context'
    return {
        'symbol': symbol,
        'provider': row.get('provider') or 'unknown',
        'expiry': expiry,
        'call_put': call_put,
        'contract_symbol': row.get('contractSymbol'),
        'strike': strike,
        'volume': int(volume),
        'open_interest': int(oi),
        'volume_oi_ratio': ratio,
        'implied_volatility': round(iv, 4) if iv else None,
        'last_price': last_price,
        'notional_proxy': notional,
        'score': score,
        'option_signal_type': signal_type,
        'direction': 'bullish' if call_put == 'call' else 'bearish' if call_put == 'put' else 'ambiguous',
    }


def to_number_string(value: Any) -> float:
    text = str(value or '').replace(',', '').strip()
    if text in {'', '--', 'N/A', 'None'}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def normalize_expiry(value: str | None, current_year: int) -> str | None:
    if not value:
        return None
    value = value.strip()
    try:
        dt = datetime.strptime(f'{value} {current_year}', '%b %d %Y')
        return dt.strftime('%Y-%m-%d')
    except Exception:
        try:
            dt = datetime.strptime(value, '%B %d, %Y')
            return dt.strftime('%Y-%m-%d')
        except Exception:
            return None


def fetch_symbol_nasdaq(symbol: str, timeout: int = 20) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://www.nasdaq.com',
        'Referer': 'https://www.nasdaq.com/',
    }
    try:
        response = requests.get(NASDAQ_OPTIONS_URL.format(symbol=symbol), headers=headers, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return [], [f'nasdaq_fetch_failed:{exc}']
    rows = (((payload or {}).get('data') or {}).get('table') or {}).get('rows') or []
    current_group = None
    events: list[dict[str, Any]] = []
    year = now_utc().year
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get('expirygroup'):
            current_group = normalize_expiry(str(row.get('expirygroup')), year)
            continue
        expiry = normalize_expiry(str(row.get('expiryDate') or ''), year) or current_group
        strike = to_number_string(row.get('strike'))
        if strike <= 0 or not expiry:
            continue
        base = {
            'strike': strike,
            'provider': 'nasdaq option-chain',
        }
        call = classify({
            **base,
            'contractSymbol': row.get('drillDownURL'),
            'volume': to_number_string(row.get('c_Volume')),
            'openInterest': to_number_string(row.get('c_Openinterest')),
            'lastPrice': to_number_string(row.get('c_Last')),
            'impliedVolatility': None,
        }, symbol=symbol, expiry=expiry, call_put='call')
        put = classify({
            **base,
            'contractSymbol': row.get('drillDownURL'),
            'volume': to_number_string(row.get('p_Volume')),
            'openInterest': to_number_string(row.get('p_Openinterest')),
            'lastPrice': to_number_string(row.get('p_Last')),
            'impliedVolatility': None,
        }, symbol=symbol, expiry=expiry, call_put='put')
        if call['volume'] > 0 or call['open_interest'] > 0:
            events.append(call)
        if put['volume'] > 0 or put['open_interest'] > 0:
            events.append(put)
    events.sort(key=lambda item: (item['score'], item['notional_proxy']), reverse=True)
    return events[:8], errors


def fetch_symbol(symbol: str, expiry_limit: int = DEFAULT_EXPIRY_LIMIT) -> tuple[list[dict[str, Any]], list[str]]:
    events, errors = fetch_symbol_nasdaq(symbol)
    if events:
        return events, errors
    errors: list[str] = []
    events: list[dict[str, Any]] = []
    if yf is None:
        return [], (errors + ['yfinance not installed'])
    try:
        ticker = yf.Ticker(symbol)
        expiries = list(getattr(ticker, 'options', []) or [])[:expiry_limit]
    except Exception as exc:
        return [], (errors + [f'options_list_failed:{exc}'])
    for expiry in expiries:
        try:
            chain = ticker.option_chain(expiry)
        except Exception as exc:
            errors.append(f'{expiry}:option_chain_failed:{exc}')
            continue
        for call_put, table in [('call', getattr(chain, 'calls', None)), ('put', getattr(chain, 'puts', None))]:
            for row in rows_from_table(table):
                event = classify(row, symbol=symbol, expiry=expiry, call_put=call_put)
                if event['volume'] <= 0 and event['open_interest'] <= 0:
                    continue
                events.append(event)
    events.sort(key=lambda item: (item['score'], item['notional_proxy']), reverse=True)
    return events[:8], errors


def build_report(symbols: list[str] | None = None, expiry_limit: int = DEFAULT_EXPIRY_LIMIT) -> dict[str, Any]:
    fetched = now_utc()
    symbols = symbols or watchlist_symbols()
    all_events: list[dict[str, Any]] = []
    errors: dict[str, list[str]] = {}
    for symbol in symbols:
        events, symbol_errors = fetch_symbol(symbol, expiry_limit=expiry_limit)
        all_events.extend(events)
        if symbol_errors:
            errors[symbol] = symbol_errors
    all_events.sort(key=lambda item: (item['score'], item['notional_proxy']), reverse=True)
    return {
        'generated_at': fetched.isoformat(),
        'generated_at_chicago': fetched.astimezone(TZ_CHI).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'generated_at_et': fetched.astimezone(TZ_ET).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'status': 'pass' if all_events else 'degraded',
        'source': 'nasdaq option-chain / yfinance fallback',
        'freshness_semantics': 'provider option-chain snapshot; delayed/incomplete; proxy only',
        'symbols': symbols,
        'watchlist_source': str(WATCHLIST if WATCHLIST.exists() else FALLBACK_WATCHLIST),
        'event_count': len(all_events),
        'top_events': all_events[:12],
        'fetch_errors': errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbols', default=None, help='comma-separated symbols; defaults to watchlist tickers')
    parser.add_argument('--expiry-limit', type=int, default=DEFAULT_EXPIRY_LIMIT)
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_out_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    symbols = [item.strip().upper() for item in args.symbols.split(',') if item.strip()] if args.symbols else None
    report = build_report(symbols=symbols, expiry_limit=args.expiry_limit)
    atomic_write_json(out, report)
    print(json.dumps({'status': report['status'], 'event_count': report['event_count'], 'error_symbols': len(report['fetch_errors']), 'out': str(out)}, ensure_ascii=False))
    return 0 if report['status'] in {'pass', 'degraded'} else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
