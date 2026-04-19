from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from finance_parent_market_ingest_cutover import build_steps


def _cmd(name: str, mode: str) -> list[str]:
    steps = build_steps(dry_run=True, scanner_mode=mode)
    by_name = {step_name: cmd for step_name, cmd, _required in steps}
    return by_name[name]


def test_parent_cutover_includes_runtime_control_state_only_for_offhours() -> None:
    offhours = _cmd('finance_source_health', 'offhours-scan')
    market = _cmd('finance_source_health', 'market-hours-scan')

    assert '--include-runtime-control-state' in offhours
    assert '--include-runtime-control-state' not in market


def test_parent_cutover_runs_router_only_for_offhours() -> None:
    assert 'offhours_source_router' in [name for name, _cmd, _required in build_steps(dry_run=True, scanner_mode='offhours-scan')]
    assert 'offhours_source_router' not in [name for name, _cmd, _required in build_steps(dry_run=True, scanner_mode='market-hours-scan')]
