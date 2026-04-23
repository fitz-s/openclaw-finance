from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import finance_discord_report_job as job


def test_refresh_tradingagents_sidecar_runs_for_immediate_alert(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(job, 'run_optional', lambda args: calls.append(args))
    job.refresh_tradingagents_sidecar('immediate-alert')
    assert calls == [
        [str(job.PYTHON), 'scripts/thesis_research_packet.py'],
        [str(job.PYTHON), 'scripts/tradingagents_sidecar_job.py', '--mode', 'report-sync'],
    ]


def test_refresh_tradingagents_sidecar_skips_watchdog(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(job, 'run_optional', lambda args: calls.append(args))
    job.refresh_tradingagents_sidecar('morning-watchdog')
    assert calls == []
