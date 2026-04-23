from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import finance_discord_report_job as job


def test_marketday_core_review_mode_uses_fast_chain(monkeypatch, capsys) -> None:
    calls = []
    monkeypatch.setattr(job, 'today_ct', lambda: job.datetime(2026, 4, 20, 13, 15, tzinfo=job.CT))
    monkeypatch.setattr(job, 'run_chain', lambda *, mode, fast_core=False: calls.append((mode, fast_core)) or 'CORE REPORT\n')
    code = job.main(['--mode', 'marketday-core-review'])
    assert code == 0
    assert calls == [('marketday-core-review', True)]
    assert capsys.readouterr().out == 'CORE REPORT\n'


def test_marketday_review_mode_uses_fast_chain(monkeypatch, capsys) -> None:
    calls = []
    monkeypatch.setattr(job, 'today_ct', lambda: job.datetime(2026, 4, 20, 8, 10, tzinfo=job.CT))
    monkeypatch.setattr(job, 'run_chain', lambda *, mode, fast_core=False: calls.append((mode, fast_core)) or 'FAST REPORT\n')
    code = job.main(['--mode', 'marketday-review'])
    assert code == 0
    assert calls == [('marketday-review', True)]
    assert capsys.readouterr().out == 'FAST REPORT\n'
