from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from finance_parent_market_ingest_cutover import build_steps


def test_parent_market_ingest_cutover_steps_include_parent_packet_and_wake() -> None:
    steps = build_steps()
    names = [name for name, _cmd, _required in steps]
    assert names[:3] == ['finance_context_pack', 'query_pack_planner', 'finance_source_health']
    assert 'parent_live_finance_adapter' in names
    assert 'parent_source_health' in names
    assert 'parent_packet_compiler' in names
    assert 'parent_wake_policy' in names


def test_parent_market_ingest_cutover_dry_run_stops_before_parent_mutation() -> None:
    names = [name for name, _cmd, _required in build_steps(dry_run=True)]
    assert names == ['finance_context_pack', 'query_pack_planner', 'finance_source_health']
