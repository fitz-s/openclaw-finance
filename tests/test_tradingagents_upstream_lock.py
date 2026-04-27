from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))

from check_tradingagents_upstream_lock import build_report


def test_tradingagents_upstream_lock_matches_submodule() -> None:
    report = build_report(write=False)
    assert report['status'] == 'pass'
    assert report['locked_tag'] == 'v0.2.3'
    assert report['locked_commit'] == '4641c03340c70e0e75e74234c998325164c72b36'
    assert report['observed_head'] == report['locked_commit']
    assert report['observed_tag'] == report['locked_tag']
    assert report['no_execution'] is True


def test_tradingagents_lock_forbids_runtime_import_in_p1() -> None:
    lock = json.loads((ROOT / 'ops' / 'tradingagents-upstream-lock.json').read_text(encoding='utf-8'))
    policy = lock['openclaw_policy']
    assert policy['phase'] == 'P1'
    assert policy['runtime_import_allowed'] is False
    assert policy['cli_integration_allowed'] is False
    assert policy['parent_cron_change_allowed'] is False
    assert policy['report_path_change_allowed'] is False
    assert policy['execution_allowed'] is False
    assert policy['no_execution'] is True
