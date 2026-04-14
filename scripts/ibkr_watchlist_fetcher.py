#!/usr/bin/env python3
"""Fetch IBKR Client Portal watchlists into a cacheable local state file."""
from __future__ import annotations

import argparse
import json
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
OUT = STATE / 'ibkr-watchlists.json'
BASE_URL = 'https://localhost:5000/v1/api'
DEFAULT_SCOPE = 'USER_WATCHLIST'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_out_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def unavailable(reason: str, previous: dict[str, Any] | None = None, *, detail: str | None = None) -> dict[str, Any]:
    previous = previous if isinstance(previous, dict) else {}
    cached = previous.get('watchlists') if isinstance(previous.get('watchlists'), list) else []
    symbols = previous.get('symbols') if isinstance(previous.get('symbols'), list) else []
    payload = {
        'generated_at': now_iso(),
        'source': 'IBKR Client Portal Web API',
        'data_status': 'unavailable',
        'scope': DEFAULT_SCOPE,
        'blocking_reasons': [reason],
        'watchlists': cached,
        'symbols': symbols,
        'used_cached_watchlists': bool(cached or symbols),
    }
    if detail:
        payload['error_detail'] = detail[:500]
    if previous.get('generated_at'):
        payload['last_good_generated_at'] = previous.get('generated_at')
    return payload


def http_json(path: str, *, timeout: int = 8, base_url: str = BASE_URL) -> tuple[Any, str | None]:
    url = base_url.rstrip('/') + path
    req = urllib.request.Request(url, headers={'Accept': 'application/json'})
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            text = response.read().decode('utf-8', errors='replace')
    except Exception as exc:
        return None, str(exc)
    if not text.strip():
        return None, 'empty_response'
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, f'json_decode_failed:{exc}'


def auth_ok(base_url: str = BASE_URL) -> tuple[bool, str | None]:
    payload, error = http_json('/iserver/auth/status', base_url=base_url)
    if error:
        return False, error
    if isinstance(payload, dict) and payload.get('authenticated') is True:
        return True, None
    return False, 'not_authenticated'


def candidate_watchlist_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ['data', 'watchlists', 'user_watchlists', 'USER_WATCHLIST']:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = candidate_watchlist_items(value)
            if nested:
                return nested
    nested = []
    for value in payload.values():
        if isinstance(value, list):
            nested.extend(item for item in value if isinstance(item, dict))
    return nested


def watchlist_id(item: dict[str, Any]) -> str | None:
    for key in ['id', 'watchlist_id', 'watchlistId', 'name']:
        value = item.get(key)
        if isinstance(value, (str, int)) and str(value):
            return str(value)
    return None


def clean_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper().replace('/', '-')
    if not symbol or len(symbol) > 12:
        return None
    blocked = {'USD', 'STK', 'OPT', 'SMART'}
    if symbol in blocked:
        return None
    if not any(ch.isalpha() for ch in symbol):
        return None
    return symbol


def extract_symbols(payload: Any) -> list[str]:
    symbols: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key in ['symbol', 'ticker', 'localSymbol', 'underlying', 'contractDesc']:
                sym = clean_symbol(value.get(key))
                if sym:
                    symbols.add(sym)
            for key, child in value.items():
                if key in {'name', 'description'}:
                    continue
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    return sorted(symbols)


def fetch_watchlists(*, scope: str = DEFAULT_SCOPE, base_url: str = BASE_URL) -> dict[str, Any]:
    ok, auth_error = auth_ok(base_url=base_url)
    if not ok:
        return unavailable('client_portal_not_authenticated', detail=auth_error)
    encoded_scope = urllib.parse.quote(scope)
    summary, error = http_json(f'/iserver/watchlists?SC={encoded_scope}', base_url=base_url)
    if error:
        return unavailable('watchlists_summary_fetch_failed', detail=error)
    items = candidate_watchlist_items(summary)
    watchlists: list[dict[str, Any]] = []
    all_symbols: set[str] = set()
    errors: list[str] = []
    for item in items:
        wid = watchlist_id(item)
        if not wid:
            continue
        detail, detail_error = http_json(f'/iserver/watchlist?id={urllib.parse.quote(wid)}', base_url=base_url)
        if detail_error:
            errors.append(f'{wid}:{detail_error}')
            detail = item
        symbols = extract_symbols(detail)
        all_symbols.update(symbols)
        watchlists.append({
            'id': wid,
            'name': item.get('name') or item.get('displayName') or wid,
            'symbol_count': len(symbols),
            'symbols': symbols,
        })
    if not watchlists and not all_symbols:
        return unavailable('watchlists_empty_or_unparseable')
    return {
        'generated_at': now_iso(),
        'source': 'IBKR Client Portal Web API',
        'data_status': 'fresh',
        'scope': scope,
        'watchlists': watchlists,
        'symbols': sorted(all_symbols),
        'fetch_errors': errors,
        'used_cached_watchlists': False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Fetch IBKR Client Portal watchlists.')
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--base-url', default=BASE_URL)
    parser.add_argument('--scope', default=DEFAULT_SCOPE)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_out_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    previous = load_json_safe(out, {}) or {}
    payload = fetch_watchlists(scope=args.scope, base_url=args.base_url)
    if payload.get('data_status') == 'unavailable':
        payload = unavailable(
            payload.get('blocking_reasons', ['watchlist_fetch_failed'])[0],
            previous,
            detail=payload.get('error_detail'),
        )
    atomic_write_json(out, payload)
    print(json.dumps({
        'status': 'pass' if payload.get('data_status') in {'fresh', 'unavailable'} else 'fail',
        'data_status': payload.get('data_status'),
        'symbol_count': len(payload.get('symbols', [])),
        'used_cached_watchlists': payload.get('used_cached_watchlists'),
        'blocking_reasons': payload.get('blocking_reasons', []),
        'out': str(out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
