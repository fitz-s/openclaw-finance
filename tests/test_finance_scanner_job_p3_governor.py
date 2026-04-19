from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from finance_scanner_job import build_steps, main


def test_finance_scanner_job_offhours_includes_governor_and_market_hours_does_not() -> None:
    off = [name for name, _cmd, _required, _timeout in build_steps('offhours-scan')]
    market = [name for name, _cmd, _required, _timeout in build_steps('market-hours-scan')]
    assert off[:2] == ['offhours_source_router', 'offhours_cadence_governor']
    assert 'offhours_cadence_governor' not in market


def test_offhours_skip_is_single_machine_line(monkeypatch, capsys, tmp_path: Path) -> None:
    import finance_scanner_job as job
    report = tmp_path / 'scanner-report.json'
    monkeypatch.setattr(job, 'REPORT', report)
    monkeypatch.setattr(job, 'build_steps', lambda mode='offhours-scan': [('offhours_cadence_governor', ['noop'], True, 1)])
    monkeypatch.setattr(job, 'run_step', lambda *args, **kwargs: {'name': 'offhours_cadence_governor', 'ok': True, 'returncode': 0, 'stdout_tail': []})
    monkeypatch.setattr(job, 'load_governor_summary', lambda: {'should_run': False, 'skip_reason': 'budget', 'session_class': 'weekend_aperture'})
    code = main(['--mode', 'offhours-scan'])
    out = capsys.readouterr().out.strip()
    assert code == 0
    assert out == 'scanner=skip mode=offhours-scan reason=budget session=weekend_aperture'
