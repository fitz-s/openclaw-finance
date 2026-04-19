from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import sys

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import finance_discord_report_job as job

CT = ZoneInfo('America/Chicago')


def _patch_common(monkeypatch, tmp_path: Path, delivered: bool) -> list[bool]:
    calls: list[bool] = []
    monkeypatch.setattr(job, 'REPORT_CALENDAR_GUARD', tmp_path / 'guard.json')
    monkeypatch.setattr(job, 'DELIVERY_OBSERVED_AUDIT', tmp_path / 'delivery-audit.json')
    monkeypatch.setattr(job, 'today_ct', lambda: datetime(2026, 4, 20, 8, 25, tzinfo=CT))
    monkeypatch.setattr(job, 'has_report_since_today', lambda hour, minute: False)
    monkeypatch.setattr(job, 'build_delivery_audit', lambda now=None: {'delivered_recent': [{'ts': '2026-04-20T08:10:00-05:00'}] if delivered else [], 'delivered_count': 1 if delivered else 0})
    monkeypatch.setattr(job, 'run_chain', lambda *, fast_core=False: calls.append(fast_core) or 'WATCHDOG REPORT\n')
    return calls


def test_morning_watchdog_no_reply_when_observed_delivery_exists(monkeypatch, capsys, tmp_path: Path) -> None:
    calls = _patch_common(monkeypatch, tmp_path, delivered=True)
    assert job.main(['--mode', 'morning-watchdog']) == 0
    assert capsys.readouterr().out.strip() == 'NO_REPLY'
    assert calls == []


def test_morning_watchdog_runs_when_no_observed_delivery(monkeypatch, capsys, tmp_path: Path) -> None:
    calls = _patch_common(monkeypatch, tmp_path, delivered=False)
    assert job.main(['--mode', 'morning-watchdog']) == 0
    assert capsys.readouterr().out == 'WATCHDOG REPORT\n'
    assert calls == [False]
