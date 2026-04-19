#!/usr/bin/env python3
"""Optional read-only IBKR TWS/Gateway options IV adapter.

This adapter intentionally reads only explicitly known option contracts, usually
from portfolio state. It never places orders, never claims brokerage authority,
and is disabled unless `IBKR_OPTIONS_IV_ENABLED=1`.
"""
from __future__ import annotations

import os
import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atomic_io import load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
PORTFOLIO_RESOLVED = STATE / 'portfolio-resolved.json'
PORTFOLIO_LEGACY = STATE / 'portfolio.json'
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 7497
DEFAULT_CLIENT_ID = 17042


@dataclass(frozen=True)
class KnownOptionContract:
    underlying: str
    expiration: str
    strike: float
    right: str
    raw_ref: str


def enabled() -> bool:
    return os.environ.get('IBKR_OPTIONS_IV_ENABLED') == '1'


def normalize_right(value: Any) -> str | None:
    text = str(value or '').strip().lower()
    if text in {'c', 'call'}:
        return 'C'
    if text in {'p', 'put'}:
        return 'P'
    return None


def normalize_expiry(value: Any) -> str | None:
    text = str(value or '').strip()
    if not text:
        return None
    return text.replace('-', '')[:8]


def load_portfolio(path: Path | None = None) -> dict[str, Any]:
    if path:
        return load_json_safe(path, {}) or {}
    data = load_json_safe(PORTFOLIO_RESOLVED, {}) or {}
    if data:
        return data
    return load_json_safe(PORTFOLIO_LEGACY, {}) or {}


def known_option_contracts(portfolio: dict[str, Any], symbols: list[str] | None = None) -> list[KnownOptionContract]:
    wanted = {symbol.upper() for symbol in symbols or []}
    out: list[KnownOptionContract] = []
    for row in portfolio.get('options', []) if isinstance(portfolio.get('options'), list) else []:
        if not isinstance(row, dict):
            continue
        underlying = str(row.get('underlying') or row.get('symbol') or '').upper()
        if wanted and underlying not in wanted:
            continue
        expiry = normalize_expiry(row.get('expiry') or row.get('expiration'))
        strike = row.get('strike')
        right = normalize_right(row.get('put_or_call') or row.get('right') or row.get('type'))
        try:
            strike_f = float(strike)
        except (TypeError, ValueError):
            continue
        if not underlying or not expiry or not right:
            continue
        out.append(KnownOptionContract(
            underlying=underlying,
            expiration=expiry,
            strike=strike_f,
            right=right,
            raw_ref=str(row.get('description') or row.get('conid') or row.get('contract_id') or f'{underlying}-{expiry}-{right}-{strike_f}'),
        ))
    return out


def dependency_available() -> bool:
    try:
        import ibapi  # noqa: F401
        return True
    except Exception:
        return False


def fetch_contract_greeks(
    contracts: list[KnownOptionContract],
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    client_id: int = DEFAULT_CLIENT_ID,
    timeout: float = 8.0,
) -> list[dict[str, Any]]:
    """Fetch model option computations through ibapi.

    This function is deliberately small and best-effort. Unit tests mock this
    boundary; live use requires a running TWS/Gateway read-only market-data
    session and market data subscriptions.
    """
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.wrapper import EWrapper

    class App(EWrapper, EClient):
        def __init__(self) -> None:
            EClient.__init__(self, self)
            self.results: dict[int, dict[str, Any]] = {}
            self.errors: queue.Queue[str] = queue.Queue()

        def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=''):  # noqa: N802
            self.errors.put(f'{reqId}:{errorCode}:{errorString}')

        def tickOptionComputation(self, reqId, tickType, tickAttrib, impliedVol, delta, optPrice, pvDividend, gamma, vega, theta, undPrice):  # noqa: N802
            if tickType == 13:  # Model Option Computation
                self.results[int(reqId)] = {
                    'implied_volatility': impliedVol if impliedVol is not None and impliedVol >= 0 else None,
                    'delta': delta if delta is not None and delta > -2 else None,
                    'gamma': gamma if gamma is not None and gamma > -2 else None,
                    'vega': vega if vega is not None and vega > -2 else None,
                    'theta': theta if theta is not None and theta > -2 else None,
                    'underlying_price': undPrice if undPrice is not None and undPrice >= 0 else None,
                }

    app = App()
    app.connect(host, port, client_id)
    thread = threading.Thread(target=app.run, daemon=True)
    thread.start()
    time.sleep(0.5)
    for idx, known in enumerate(contracts, start=1):
        contract = Contract()
        contract.symbol = known.underlying
        contract.secType = 'OPT'
        contract.exchange = 'SMART'
        contract.currency = 'USD'
        contract.lastTradeDateOrContractMonth = known.expiration
        contract.strike = known.strike
        contract.right = known.right
        contract.multiplier = '100'
        app.reqMktData(idx, contract, '', False, False, [])
    deadline = time.time() + timeout
    while time.time() < deadline and len(app.results) < len(contracts):
        time.sleep(0.1)
    for idx in range(1, len(contracts) + 1):
        app.cancelMktData(idx)
    app.disconnect()
    out: list[dict[str, Any]] = []
    for idx, known in enumerate(contracts, start=1):
        row = app.results.get(idx)
        if not row or row.get('implied_volatility') is None:
            continue
        out.append({
            **row,
            'underlying': known.underlying,
            'expiration': known.expiration,
            'strike': known.strike,
            'right': known.right,
            'raw_ref': known.raw_ref,
        })
    return out
