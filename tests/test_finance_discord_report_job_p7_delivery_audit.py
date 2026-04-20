from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import sys

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import finance_discord_report_job as job

CT = ZoneInfo('America/Chicago')


def _patch_common(monkeypatch, tmp_path: Path, *, delivered: bool, registry_activity: bool) -> list[bool]:
    calls: list[bool] = []
    monkeypatch.setattr(job, 'REPORT_CALENDAR_GUARD', tmp_path / 'guard.json')
    monkeypatch.setattr(job, 'DELIVERY_OBSERVED_AUDIT', tmp_path / 'delivery-audit.json')
    monkeypatch.setattr(job, 'today_ct', lambda: datetime(2026, 4, 20, 8, 25, tzinfo=CT))
    monkeypatch.setattr(job, 'build_delivery_audit', lambda now=None: {
        'delivered_recent': [{'ts': '2026-04-20T08:10:00-05:00'}] if delivered else [],
        'delivered_count': 1 if delivered else 0,
    })
    monkeypatch.setattr(job, 'followup_registry_activity_since_today', lambda hour, minute, now=None: {
        'boundary': 'followup_thread_registry',
        'authoritative_delivery_proof': False,
        'observed_since_cutoff': registry_activity,
        'cutoff': '2026-04-20T07:30:00-05:00',
        'matching_thread_count': 1 if registry_activity else 0,
        'latest_updated_at': '2026-04-20T08:15:00-05:00' if registry_activity else None,
        'warning': job.FOLLOWUP_REGISTRY_WARNING if registry_activity else None,
    })
    monkeypatch.setattr(job, 'run_chain', lambda *, fast_core=False: calls.append(fast_core) or 'WATCHDOG REPORT\n')
    return calls


def test_morning_watchdog_no_reply_when_observed_delivery_exists(monkeypatch, capsys, tmp_path: Path) -> None:
    calls = _patch_common(monkeypatch, tmp_path, delivered=True, registry_activity=False)
    assert job.main(['--mode', 'morning-watchdog']) == 0
    assert capsys.readouterr().out.strip() == 'NO_REPLY'
    assert calls == []
    audit = json.loads((tmp_path / 'delivery-audit.json').read_text(encoding='utf-8'))
    assert audit['watchdog_duplicate_suppression_boundary'] == 'observed_parent_delivery_only'
    assert audit['followup_registry_activity']['authoritative_delivery_proof'] is False


def test_morning_watchdog_runs_when_no_observed_delivery(monkeypatch, capsys, tmp_path: Path) -> None:
    calls = _patch_common(monkeypatch, tmp_path, delivered=False, registry_activity=False)
    assert job.main(['--mode', 'morning-watchdog']) == 0
    assert capsys.readouterr().out == 'WATCHDOG REPORT\n'
    assert calls == [True]
    audit = json.loads((tmp_path / 'delivery-audit.json').read_text(encoding='utf-8'))
    assert audit['followup_registry_activity']['observed_since_cutoff'] is False
    assert audit.get('warnings') is None


def test_morning_watchdog_runs_when_only_followup_registry_activity_exists(monkeypatch, capsys, tmp_path: Path) -> None:
    calls = _patch_common(monkeypatch, tmp_path, delivered=False, registry_activity=True)
    assert job.main(['--mode', 'morning-watchdog']) == 0
    assert capsys.readouterr().out == 'WATCHDOG REPORT\n'
    assert calls == [True]
    audit = json.loads((tmp_path / 'delivery-audit.json').read_text(encoding='utf-8'))
    assert audit['followup_registry_activity']['observed_since_cutoff'] is True
    assert audit['warnings'] == [job.FOLLOWUP_REGISTRY_WARNING]
