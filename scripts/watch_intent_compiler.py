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


CYCLICAL_SYMBOLS = {'USO', 'XLE', 'XLF', 'XLB', 'XLI', 'XLP', 'XLU', 'XLY', 'LUMN', 'RGTI'}


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


def bucket_hint_for(symbol: str, roles: list[str]) -> str:
    """Deterministic capital bucket hint from roles."""
    role_set = set(roles)
    if 'hedge' in role_set or 'macro_proxy' in role_set:
        return 'macro_hedges'
    if 'held_core' in role_set:
        return 'cyclical_beta' if symbol in CYCLICAL_SYMBOLS else 'core_compounders'
    if 'event_sensitive' in role_set:
        return 'event_driven'
    return 'speculative_optionality'


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
        computed_roles = roles_for(symbol, row, set(portfolio_symbols), set(option_symbols))
        intents.append({
            'intent_id': stable_id('watch-intent', symbol),
            'symbol': symbol,
            'roles': computed_roles,
            'capital_bucket_hint': bucket_hint_for(symbol, computed_roles),
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

