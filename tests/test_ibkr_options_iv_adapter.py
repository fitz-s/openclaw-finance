from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import ibkr_options_iv_adapter as adapter


def test_known_option_contracts_from_portfolio_are_explicit() -> None:
    portfolio = {
        'options': [{
            'underlying': 'TSLA',
            'expiry': '2026-01-17',
            'strike': 400,
            'put_or_call': 'call',
            'description': 'TSLA JAN2026 400 C',
        }]
    }
    rows = adapter.known_option_contracts(portfolio, ['TSLA'])
    assert len(rows) == 1
    assert rows[0].underlying == 'TSLA'
    assert rows[0].expiration == '20260117'
    assert rows[0].right == 'C'
    assert rows[0].strike == 400


def test_known_option_contracts_ignore_watchlist_without_contract_terms() -> None:
    assert adapter.known_option_contracts({'options': []}, ['TSLA']) == []
