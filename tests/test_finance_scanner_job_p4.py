from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import finance_scanner_job as job


def test_scanner_job_uses_single_deterministic_chain() -> None:
    steps = job.build_steps()
    names = [name for name, _cmd, _required, _timeout in steps]
    assert names == [
        'finance_context_pack',
        'query_pack_planner',
        'finance_worker',
        'parent_market_ingest_cutover',
        'gate_evaluator',
    ]
    assert all(required for _name, _cmd, required, _timeout in steps)
    assert all(cmd[0] == str(job.PYTHON) for _name, cmd, _required, _timeout in steps)


def test_scanner_job_stdout_success_is_single_machine_line(monkeypatch, capsys, tmp_path: Path) -> None:
    report = tmp_path / 'scanner-report.json'
    monkeypatch.setattr(job, 'REPORT', report)
    monkeypatch.setattr(job, 'build_steps', lambda: [])
    monkeypatch.setattr(job, 'load_gate_summary', lambda: {
        'recommendedReportType': 'hold',
        'shouldSend': False,
    })
    code = job.main(['--mode', 'market-hours-scan'])
    out = capsys.readouterr().out.strip()
    assert code == 0
    assert out == 'scanner=ok mode=market-hours-scan gate=hold send=false'
    payload = json.loads(report.read_text())
    assert payload['no_execution'] is True


def test_scanner_job_failure_is_single_machine_line(monkeypatch, capsys, tmp_path: Path) -> None:
    report = tmp_path / 'scanner-report.json'
    monkeypatch.setattr(job, 'REPORT', report)
    monkeypatch.setattr(job, 'build_steps', lambda: [('bad_step', [str(job.PYTHON), '--version'], True, 1)])

    def fail_step(*args, **kwargs):
        raise RuntimeError('boom')

    monkeypatch.setattr(job, 'run_step', fail_step)
    code = job.main(['--mode', 'offhours-scan'])
    out = capsys.readouterr().out.strip()
    assert code == 1
    assert out.startswith('scanner=fail mode=offhours-scan check=')
    payload = json.loads(report.read_text())
    assert payload['status'] == 'fail'
