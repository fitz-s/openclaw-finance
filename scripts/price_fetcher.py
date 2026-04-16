#!/usr/bin/env python3
"""Deterministic price fetcher — no LLM, pure yfinance API.
Fetches provider quote snapshots for watchlist tickers and writes to state/prices.json.
The cron cadence is a polling cadence; yfinance is not a tick-real-time feed.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import yfinance as yf
except ImportError:
    yf = None

from atomic_io import atomic_write_json, load_json_safe

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
WATCHLIST = FINANCE / 'state' / 'watchlist-resolved.json'
FALLBACK_WATCHLIST = FINANCE / 'watchlists' / 'core.json'
PRICES_STATE = FINANCE / 'state' / 'prices.json'
TZ_CHI = ZoneInfo('America/Chicago')
TZ_ET = ZoneInfo('America/New_York')
QUOTE_GRANULARITY = 'provider_quote_snapshot'
CORE_MACRO_TICKERS = ['SPY', 'GLD', 'IAU', 'BTC-USD']
FRESHNESS_SEMANTICS = (
    'yfinance fast_info snapshot; not tick-real-time; provider data may be delayed, '
    'frozen, or unavailable depending on symbol/session/subscription'
)


def load_tickers() -> list[str]:
    wl = load_json_safe(WATCHLIST, {})
    if not wl:
        wl = load_json_safe(FALLBACK_WATCHLIST, {})
    tickers = []
    for item in wl.get('tickers', []):
        tickers.append(item['symbol'])
    for item in wl.get('indexes', []):
        tickers.append(item['symbol'])
    for item in wl.get('crypto', []):
        sym = item['symbol']
        # yfinance uses BTC-USD format
        tickers.append(sym.replace('/', '-'))
    # Core reports must always collect Gold / Bitcoin / SPX direction.
    # SPY is the SPX proxy; GLD/IAU are gold proxies; BTC-USD is Bitcoin.
    tickers.extend(CORE_MACRO_TICKERS)
    return sorted(set(tickers))


def fetch_quotes(tickers: list[str]) -> dict:
    """Fetch provider quote snapshots for all tickers.

    The previous implementation used a 1d/1d batch bar and labeled it as a
    current quote. Use yfinance fast_info instead so the schema reflects quote
    semantics, while still making clear this is not a streaming/tick feed.
    """
    return {t: _fetch_single(t) for t in tickers}


def _fast_info_value(info, *names, default=None):
    for name in names:
        try:
            if isinstance(info, dict):
                value = info.get(name)
            else:
                value = getattr(info, name, None)
        except Exception:
            value = None
        if value is not None:
            return value
    return default


def _finite_positive(value: float) -> bool:
    return value > 0 and value == value and value not in {float('inf'), float('-inf')}


def _fetch_single(ticker: str) -> dict:
    """Fallback: fetch a single ticker."""
    now = datetime.now(timezone.utc)
    if yf is None:
        return {'status': 'error', 'error': 'yfinance not installed'}
    try:
        tk = yf.Ticker(ticker)
        info = tk.fast_info
        price = float(_fast_info_value(info, 'last_price', 'lastPrice', default=0) or 0)
        prev = float(_fast_info_value(info, 'previous_close', 'regular_market_previous_close', default=0) or 0)
        if not _finite_positive(price) or not _finite_positive(prev):
            return {
                'status': 'error',
                'error': f'invalid provider quote snapshot: price={price} previous_close={prev}',
                'as_of': now.isoformat(),
                'quote_granularity': QUOTE_GRANULARITY,
                'freshness_semantics': FRESHNESS_SEMANTICS,
            }
        change = round(price - prev, 4) if prev else 0
        pct = round((change / prev) * 100, 4) if prev else 0
        return {
            'price': price,
            'close': price,
            'previous_close': prev,
            'open': float(_fast_info_value(info, 'open', default=0) or 0),
            'high': float(_fast_info_value(info, 'day_high', default=0) or 0),
            'low': float(_fast_info_value(info, 'day_low', default=0) or 0),
            'volume': int(_fast_info_value(info, 'last_volume', default=0) or 0),
            'change': change,
            'pct_change': pct,
            'change_pct': pct,
            'as_of': now.isoformat(),
            'quote_granularity': QUOTE_GRANULARITY,
            'freshness_semantics': FRESHNESS_SEMANTICS,
            'status': 'ok',
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


def main():
    now = datetime.now(timezone.utc)
    if yf is None:
        print("❌ yfinance not installed: pip3 install yfinance", file=sys.stderr)
        sys.exit(1)
    tickers = load_tickers()
    if not tickers:
        print("⚠️ No tickers in watchlist", file=sys.stderr)
        sys.exit(1)

    quotes = fetch_quotes(tickers)

    state = {
        'fetched_at': now.isoformat(),
        'fetched_at_chicago': now.astimezone(TZ_CHI).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'fetched_at_et': now.astimezone(TZ_ET).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'source': 'yfinance',
        'source_detail': 'yfinance.fast_info',
        'quote_granularity': QUOTE_GRANULARITY,
        'freshness_semantics': FRESHNESS_SEMANTICS,
        'ticker_count': len(tickers),
        'ok_count': sum(1 for q in quotes.values() if q.get('status') == 'ok'),
        'error_count': sum(1 for q in quotes.values() if q.get('status') == 'error'),
        'watchlist_source': str(WATCHLIST if WATCHLIST.exists() else FALLBACK_WATCHLIST),
        'quotes': quotes,
    }

    atomic_write_json(PRICES_STATE, state)

    ok = state['ok_count']
    err = state['error_count']
    print(f"✅ Fetched {ok}/{len(tickers)} tickers. Errors: {err}. Written to state/prices.json")
    if err:
        for t, q in quotes.items():
            if q.get('status') == 'error':
                print(f"  ❌ {t}: {q.get('error', 'unknown')}")


if __name__ == '__main__':
    main()
