#!/usr/bin/env python3
"""Resolve finance watchlist universe from IBKR watchlists, Flex holdings, and local pins."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
LOCAL_CORE = FINANCE / 'watchlists' / 'core.json'
IBKR_WATCHLISTS = STATE / 'ibkr-watchlists.json'
PORTFOLIO = STATE / 'portfolio-resolved.json'
HELD = STATE / 'held-tickers-resolved.json'
OUT = STATE / 'watchlist-resolved.json'
IBKR_MAX_AGE_DAYS = 30
PORTFOLIO_MAX_AGE_HOURS = 36


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def age_hours(value: Any, now: datetime) -> float | None:
    dt = parse_dt(value)
    if dt is None:
        return None
    return round((now - dt).total_seconds() / 3600, 2)


def clean_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper().replace('/', '-')
    if not symbol or len(symbol) > 12:
        return None
    if not any(ch.isalpha() for ch in symbol):
        return None
    return symbol


def add_symbol(symbols: dict[str, dict[str, Any]], symbol: Any, source: str, *, market: str = 'US', notes: str = '') -> None:
    sym = clean_symbol(symbol)
    if not sym:
        return
    row = symbols.setdefault(sym, {'symbol': sym, 'market': market, 'sources': [], 'notes': []})
    if source not in row['sources']:
        row['sources'].append(source)
    if notes and notes not in row['notes']:
        row['notes'].append(notes)


def add_local(symbols: dict[str, dict[str, Any]], local: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    indexes = local.get('indexes') if isinstance(local.get('indexes'), list) else []
    crypto = local.get('crypto') if isinstance(local.get('crypto'), list) else []
    for item in local.get('tickers', []) if isinstance(local.get('tickers'), list) else []:
        if isinstance(item, dict):
            add_symbol(symbols, item.get('symbol'), 'local_pinned_core', market=item.get('market') or 'US', notes=item.get('notes') or '')
    return indexes, crypto


def add_ibkr(symbols: dict[str, dict[str, Any]], ibkr: dict[str, Any], now: datetime) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    age = age_hours(ibkr.get('generated_at'), now)
    fresh = ibkr.get('data_status') == 'fresh' and age is not None and age <= IBKR_MAX_AGE_DAYS * 24
    if not fresh:
        reasons.extend(str(item) for item in ibkr.get('blocking_reasons', []) if item)
        if age is None:
            reasons.append('ibkr_watchlist_missing_generated_at')
        elif age > IBKR_MAX_AGE_DAYS * 24:
            reasons.append('ibkr_watchlist_stale')
    source_name = 'ibkr_client_portal_watchlist' if fresh else 'ibkr_client_portal_watchlist_cache'
    for symbol in ibkr.get('symbols', []) if isinstance(ibkr.get('symbols'), list) else []:
        add_symbol(symbols, symbol, source_name)
    return fresh, sorted(set(reasons))


def add_portfolio(symbols: dict[str, dict[str, Any]], portfolio: dict[str, Any], held: dict[str, Any], now: datetime) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    index_aliases = {'SPY', 'QQQ', 'VOO', 'IWM', 'DIA'}
    age = age_hours(portfolio.get('resolved_at') or portfolio.get('fetched_at'), now)
    fresh = portfolio.get('data_status') == 'fresh' and age is not None and age <= PORTFOLIO_MAX_AGE_HOURS
    if not fresh:
        if portfolio.get('stale_reason'):
            reasons.append(str(portfolio.get('stale_reason')))
        else:
            reasons.append('portfolio_unavailable_or_stale')
        return False, sorted(set(reasons))
    for stock in portfolio.get('stocks', []) if isinstance(portfolio.get('stocks'), list) else []:
        sym = stock.get('symbol') if isinstance(stock, dict) else None
        if sym and sym not in {'SPY', 'QQQ', 'VOO'}:
            add_symbol(symbols, sym, 'flex_holding_stock')
    for option in portfolio.get('options', []) if isinstance(portfolio.get('options'), list) else []:
        if isinstance(option, dict):
            add_symbol(symbols, option.get('underlying') or option.get('symbol'), 'flex_holding_option_underlying')
    for sym in held.get('tickers', {}) if isinstance(held.get('tickers'), dict) else []:
        if sym in index_aliases:
            continue
        add_symbol(symbols, sym, 'resolved_held_tickers')
    return True, []


def build_resolved(
    *,
    local: dict[str, Any],
    ibkr: dict[str, Any],
    portfolio: dict[str, Any],
    held: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    symbols: dict[str, dict[str, Any]] = {}
    indexes, crypto = add_local(symbols, local)
    ibkr_fresh, ibkr_reasons = add_ibkr(symbols, ibkr, now)
    portfolio_fresh, portfolio_reasons = add_portfolio(symbols, portfolio, held, now)
    tickers = sorted(symbols.values(), key=lambda item: item['symbol'])
    status = 'fresh' if ibkr_fresh or portfolio_fresh else 'degraded'
    return {
        'generated_at': now.isoformat(),
        'source': 'watchlist_resolver.py',
        'data_status': status,
        'ibkr_watchlist_fresh': ibkr_fresh,
        'portfolio_fresh': portfolio_fresh,
        'blocking_reasons': sorted(set(ibkr_reasons + portfolio_reasons)),
        'tickers': tickers,
        'indexes': indexes,
        'crypto': crypto,
        'symbol_count': len(tickers) + len(indexes) + len(crypto),
        'source_refs': {
            'local_core': str(LOCAL_CORE),
            'ibkr_watchlists': str(IBKR_WATCHLISTS),
            'portfolio': str(PORTFOLIO),
            'held_tickers': str(HELD),
        },
    }


def safe_out_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Resolve finance watchlist universe.')
    parser.add_argument('--local-core', default=str(LOCAL_CORE))
    parser.add_argument('--ibkr-watchlists', default=str(IBKR_WATCHLISTS))
    parser.add_argument('--portfolio', default=str(PORTFOLIO))
    parser.add_argument('--held', default=str(HELD))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_out_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    payload = build_resolved(
        local=load_json_safe(Path(args.local_core), {}) or {},
        ibkr=load_json_safe(Path(args.ibkr_watchlists), {}) or {},
        portfolio=load_json_safe(Path(args.portfolio), {}) or {},
        held=load_json_safe(Path(args.held), {}) or {},
    )
    atomic_write_json(out, payload)
    print(json.dumps({
        'status': 'pass',
        'data_status': payload['data_status'],
        'symbol_count': payload['symbol_count'],
        'ibkr_watchlist_fresh': payload['ibkr_watchlist_fresh'],
        'portfolio_fresh': payload['portfolio_fresh'],
        'blocking_reasons': payload['blocking_reasons'],
        'out': str(out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
