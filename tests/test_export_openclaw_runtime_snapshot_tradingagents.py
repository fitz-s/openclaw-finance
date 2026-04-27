from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))

import export_openclaw_runtime_snapshot as snapshot


def test_refresh_tradingagents_audits_runs_expected_tools(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, cwd, capture_output, text, timeout):  # type: ignore[no-untyped-def]
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout='{"status":"pass"}', stderr='')

    monkeypatch.setattr(snapshot.subprocess, 'run', fake_run)
    snapshot.refresh_tradingagents_audits()

    assert calls == [
        ['python3', str(ROOT / 'tools' / 'check_tradingagents_upstream_lock.py')],
        ['python3', str(ROOT / 'tools' / 'audit_tradingagents_upstream_authority.py')],
    ]
