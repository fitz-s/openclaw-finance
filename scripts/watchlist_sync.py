#!/usr/bin/env python3
"""Compatibility entrypoint for finance watchlist sync.

The authoritative runtime watchlist is `state/watchlist-resolved.json`.
`watchlists/core.json` is a local pinned fallback only and is not mutated here.
"""
from __future__ import annotations

import json
from pathlib import Path

from atomic_io import atomic_write_json, load_json_safe
from ibkr_watchlist_fetcher import OUT as IBKR_OUT, fetch_watchlists, unavailable
from watchlist_resolver import (
    HELD,
    IBKR_WATCHLISTS,
    LOCAL_CORE,
    OUT as RESOLVED_OUT,
    PORTFOLIO,
    build_resolved,
)


def parse_iso_datetime(value: str | None):
    from datetime import datetime
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None


def portfolio_invalidated_by_failed_refresh(portfolio: dict, held_tickers: dict) -> bool:
    """Compatibility helper retained for stale-state tests."""
    if not isinstance(portfolio, dict) or not isinstance(held_tickers, dict):
        return False
    if held_tickers.get('data_status') != 'ibkr_unavailable':
        return False
    failed_at = parse_iso_datetime(held_tickers.get('updated_at'))
    fetched_at = parse_iso_datetime(portfolio.get('fetched_at'))
    if failed_at is None:
        return False
    if fetched_at is None:
        return True
    return failed_at >= fetched_at


def main() -> int:
    previous_ibkr = load_json_safe(IBKR_OUT, {}) or {}
    ibkr_payload = fetch_watchlists()
    if ibkr_payload.get('data_status') == 'unavailable':
        ibkr_payload = unavailable(
            ibkr_payload.get('blocking_reasons', ['watchlist_fetch_failed'])[0],
            previous_ibkr,
            detail=ibkr_payload.get('error_detail'),
        )
    atomic_write_json(IBKR_OUT, ibkr_payload)

    resolved = build_resolved(
        local=load_json_safe(LOCAL_CORE, {}) or {},
        ibkr=load_json_safe(IBKR_WATCHLISTS, {}) or {},
        portfolio=load_json_safe(PORTFOLIO, {}) or {},
        held=load_json_safe(HELD, {}) or {},
    )
    atomic_write_json(RESOLVED_OUT, resolved)
    print(json.dumps({
        'status': 'pass',
        'watchlist_data_status': resolved.get('data_status'),
        'symbol_count': resolved.get('symbol_count'),
        'ibkr_watchlist_fresh': resolved.get('ibkr_watchlist_fresh'),
        'portfolio_fresh': resolved.get('portfolio_fresh'),
        'resolved_path': str(RESOLVED_OUT),
        'ibkr_path': str(IBKR_OUT),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
