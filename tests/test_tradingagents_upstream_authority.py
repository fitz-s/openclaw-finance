from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))

from audit_tradingagents_upstream_authority import build_report


def test_tradingagents_upstream_has_no_broker_or_order_api_surface() -> None:
    report = build_report(write=False)
    assert report['status'] == 'pass'
    assert report['dangerous_findings'] == []
    assert report['policy']['dangerous_broker_or_order_api_allowed'] is False
    assert report['policy']['runtime_import_allowed_in_p1'] is False
    assert report['no_execution'] is True


def test_tradingagents_upstream_review_language_is_detected_for_future_quarantine() -> None:
    report = build_report(write=False)
    codes = {finding['code'] for finding in report['review_language_findings']}
    assert 'final_transaction_proposal' in codes
    assert 'buy_hold_sell_rating' in codes
    assert report['policy']['review_language_allowed_only_in_quarantined_raw_or_machine_fields'] is True
