from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from finance_scanner_job import build_steps


def _names(mode: str) -> list[str]:
    return [name for name, _cmd, _required, _timeout in build_steps(mode)]


def test_offhours_scan_inserts_router_and_market_hours_does_not() -> None:
    offhours = _names('offhours-scan')
    market = _names('market-hours-scan')

    assert offhours[0] == 'offhours_source_router'
    assert 'offhours_source_router' not in market
    assert market[:2] == ['finance_context_pack', 'query_pack_planner']


def test_scanner_mode_passes_to_query_planner_and_parent_cutover() -> None:
    steps = build_steps('offhours-scan')
    by_name = {name: cmd for name, cmd, _required, _timeout in steps}

    assert '--scanner-mode' in by_name['query_pack_planner']
    assert 'offhours-scan' in by_name['query_pack_planner']
    assert '--scanner-mode' in by_name['parent_market_ingest_cutover']
    assert 'offhours-scan' in by_name['parent_market_ingest_cutover']
