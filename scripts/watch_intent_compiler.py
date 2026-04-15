#!/usr/bin/env python3
"""Compile durable WatchIntent objects from resolved watchlist and portfolio."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from thesis_spine_util import FINANCE, POLICY_VERSION, clean_symbol, load, now_iso, source_refs, stable_id, write

WATCHLIST = FINANCE / 'state' / 'watchlist-resolved.json'
PORTFOLIO = FINANCE / 'state' / 'portfolio-resolved.json'
OUT = FINANCE / 'state' / 'watch-intent.json'


def roles_for(symbol: str, row: dict[str, Any], portfolio_symbols: set[str], option_symbols: set[str]) -> list[str]:
    roles = set()
    sources = set(row.get('sources', [])) if isinstance(row.get('sources'), list) else set()
    if symbol in portfolio_symbols or symbol in option_symbols:
        roles.add('held_core')
    if symbol in {'SPY', 'QQQ', 'BTC-USD', 'USO', 'XLE', 'IAU', 'VOO'}:
        roles.add('macro_proxy' if symbol != 'IAU' else 'hedge')
    if 'ibkr_client_portal_watchlist' in sources or 'local_pinned_core' in sources:
        roles.add('event_sensitive')
    if not roles:
        roles.add('curiosity')
    return sorted(roles)


def compile_intents(watchlist: dict[str, Any], portfolio: dict[str, Any]) -> dict[str, Any]:
    portfolio_symbols = {clean_symbol(item.get('symbol')) for item in portfolio.get('stocks', []) if isinstance(item, dict)}
    option_symbols = {clean_symbol(item.get('underlying') or item.get('symbol')) for item in portfolio.get('options', []) if isinstance(item, dict)}
    portfolio_symbols.discard(None)
    option_symbols.discard(None)
    intents = []
    for row in watchlist.get('tickers', []) if isinstance(watchlist.get('tickers'), list) else []:
        if not isinstance(row, dict):
            continue
        symbol = clean_symbol(row.get('symbol'))
        if not symbol:
            continue
        intents.append({
            'intent_id': stable_id('watch-intent', symbol),
            'symbol': symbol,
            'roles': roles_for(symbol, row, set(portfolio_symbols), set(option_symbols)),
            'source_refs': source_refs(WATCHLIST, PORTFOLIO),
            'notes': row.get('notes', []) if isinstance(row.get('notes'), list) else ([row.get('notes')] if row.get('notes') else []),
        })
    return {
        'generated_at': now_iso(),
        'policy_version': POLICY_VERSION,
        'intents': sorted(intents, key=lambda item: item['symbol']),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--watchlist', default=str(WATCHLIST))
    parser.add_argument('--portfolio', default=str(PORTFOLIO))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    payload = compile_intents(load(Path(args.watchlist), {}) or {}, load(Path(args.portfolio), {}) or {})
    write(Path(args.out), payload)
    print(json.dumps({'status': 'pass', 'intent_count': len(payload['intents']), 'out': str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

