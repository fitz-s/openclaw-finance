from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import finance_discord_report_job as job


def test_holiday_weekday_returns_no_reply_without_chain(monkeypatch, capsys, tmp_path: Path) -> None:
    calls = []
    monkeypatch.setattr(job, 'REPORT_CALENDAR_GUARD', tmp_path / 'guard.json')
    monkeypatch.setattr(job, 'today_ct', lambda: job.datetime(2026, 11, 26, 8, 10, tzinfo=job.CT))
    monkeypatch.setattr(job, 'run_chain', lambda *, fast_core=False: calls.append(fast_core) or 'SHOULD NOT RUN\n')
    assert job.main(['--mode', 'marketday-review']) == 0
    assert capsys.readouterr().out.strip() == 'NO_REPLY'
    assert calls == []
    guard = json.loads((tmp_path / 'guard.json').read_text(encoding='utf-8'))
    assert guard['skip_reason'] == 'holiday_aperture'


def test_regular_trading_day_premarket_runs_chain(monkeypatch, capsys, tmp_path: Path) -> None:
    calls = []
    monkeypatch.setattr(job, 'REPORT_CALENDAR_GUARD', tmp_path / 'guard.json')
    monkeypatch.setattr(job, 'today_ct', lambda: job.datetime(2026, 4, 20, 8, 10, tzinfo=job.CT))
    monkeypatch.setattr(job, 'run_chain', lambda *, fast_core=False: calls.append(fast_core) or 'REPORT\n')
    assert job.main(['--mode', 'marketday-review']) == 0
    assert capsys.readouterr().out == 'REPORT\n'
    assert calls == [False]


def test_halfday_postclose_core_review_returns_no_reply(monkeypatch, capsys, tmp_path: Path) -> None:
    calls = []
    monkeypatch.setattr(job, 'REPORT_CALENDAR_GUARD', tmp_path / 'guard.json')
    monkeypatch.setattr(job, 'today_ct', lambda: job.datetime(2026, 11, 27, 13, 15, tzinfo=job.CT))
    monkeypatch.setattr(job, 'run_chain', lambda *, fast_core=False: calls.append(fast_core) or 'SHOULD NOT RUN\n')
    assert job.main(['--mode', 'marketday-core-review']) == 0
    assert capsys.readouterr().out.strip() == 'NO_REPLY'
    assert calls == []
    guard = json.loads((tmp_path / 'guard.json').read_text(encoding='utf-8'))
    assert guard['skip_reason'] == 'halfday_core_review_after_close'


def test_regular_rth_core_review_runs_fast_chain(monkeypatch, capsys, tmp_path: Path) -> None:
    calls = []
    monkeypatch.setattr(job, 'REPORT_CALENDAR_GUARD', tmp_path / 'guard.json')
    monkeypatch.setattr(job, 'today_ct', lambda: job.datetime(2026, 4, 20, 13, 15, tzinfo=job.CT))
    monkeypatch.setattr(job, 'run_chain', lambda *, fast_core=False: calls.append(fast_core) or 'CORE\n')
    assert job.main(['--mode', 'marketday-core-review']) == 0
    assert capsys.readouterr().out == 'CORE\n'
    assert calls == [True]
