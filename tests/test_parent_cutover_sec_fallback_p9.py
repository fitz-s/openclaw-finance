from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from finance_parent_market_ingest_cutover import build_steps


def test_parent_cutover_includes_optional_sec_fallback_after_brave_activation() -> None:
    steps = build_steps(dry_run=True, scanner_mode='offhours-scan')
    names = [name for name, _cmd, _required in steps]
    assert 'brave_source_activation' in names
    assert 'sec_fallback_activation' in names
    assert names.index('sec_fallback_activation') > names.index('brave_source_activation')
    by_name = {name: required for name, _cmd, required in steps}
    assert by_name['sec_fallback_activation'] is False


def test_parent_cutover_default_keeps_legacy_step_order_without_sec_fallback() -> None:
    names = [name for name, _cmd, _required in build_steps(dry_run=True)]
    assert names == ['finance_context_pack', 'query_pack_planner', 'brave_source_activation', 'finance_source_health']
