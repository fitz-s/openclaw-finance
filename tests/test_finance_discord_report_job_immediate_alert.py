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


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def test_immediate_alert_delivers_when_tradingagents_context_is_present(monkeypatch, capsys, tmp_path: Path) -> None:
    guard = tmp_path / 'guard.json'
    context_pack = tmp_path / 'report-orchestrator.json'
    alert_state = tmp_path / 'finance-immediate-alert-state.json'
    monkeypatch.setattr(job, 'REPORT_CALENDAR_GUARD', guard)
    monkeypatch.setattr(job, 'CONTEXT_PACK', context_pack)
    monkeypatch.setattr(job, 'IMMEDIATE_ALERT_STATE', alert_state)
    monkeypatch.setattr(job, 'today_ct', lambda: datetime(2026, 4, 23, 11, 55, tzinfo=CT))
    monkeypatch.setattr(job, 'run_chain', lambda *, mode, fast_core=False: 'ALERT REPORT\n')
    monkeypatch.setattr(job, 'ENVELOPE', tmp_path / 'envelope.json')
    _write_json(tmp_path / 'envelope.json', {'report_hash': 'sha256:report'})
    _write_json(context_pack, {
        'tradingagents_sidecar': {
            'run_id': 'ta:abc',
            'generated_at': '2026-04-23T16:45:00Z',
        }
    })

    assert job.main(['--mode', 'immediate-alert']) == 0
    assert capsys.readouterr().out == 'ALERT REPORT\n'
    state = json.loads(alert_state.read_text(encoding='utf-8'))
    assert state['should_deliver'] is True
    assert state['tradingagents_run_id'] == 'ta:abc'


def test_immediate_alert_suppresses_without_tradingagents_context(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(job, 'REPORT_CALENDAR_GUARD', tmp_path / 'guard.json')
    monkeypatch.setattr(job, 'CONTEXT_PACK', tmp_path / 'report-orchestrator.json')
    monkeypatch.setattr(job, 'IMMEDIATE_ALERT_STATE', tmp_path / 'finance-immediate-alert-state.json')
    monkeypatch.setattr(job, 'today_ct', lambda: datetime(2026, 4, 23, 11, 55, tzinfo=CT))
    monkeypatch.setattr(job, 'run_chain', lambda *, mode, fast_core=False: 'ALERT REPORT\n')
    monkeypatch.setattr(job, 'ENVELOPE', tmp_path / 'envelope.json')
    _write_json(tmp_path / 'envelope.json', {'report_hash': 'sha256:report'})
    _write_json(tmp_path / 'report-orchestrator.json', {})

    assert job.main(['--mode', 'immediate-alert']) == 0
    assert capsys.readouterr().out.strip() == 'NO_REPLY'
    state = json.loads((tmp_path / 'finance-immediate-alert-state.json').read_text(encoding='utf-8'))
    assert state['should_deliver'] is False
    assert state['suppressed_reason'] == 'missing_tradingagents_sidecar_context'


def test_immediate_alert_suppresses_duplicate_primary_markdown(monkeypatch, capsys, tmp_path: Path) -> None:
    monkeypatch.setattr(job, 'REPORT_CALENDAR_GUARD', tmp_path / 'guard.json')
    monkeypatch.setattr(job, 'CONTEXT_PACK', tmp_path / 'report-orchestrator.json')
    monkeypatch.setattr(job, 'IMMEDIATE_ALERT_STATE', tmp_path / 'finance-immediate-alert-state.json')
    monkeypatch.setattr(job, 'today_ct', lambda: datetime(2026, 4, 23, 11, 55, tzinfo=CT))
    monkeypatch.setattr(job, 'run_chain', lambda *, mode, fast_core=False: 'ALERT REPORT\n')
    monkeypatch.setattr(job, 'ENVELOPE', tmp_path / 'envelope.json')
    _write_json(tmp_path / 'envelope.json', {'report_hash': 'sha256:report'})
    _write_json(tmp_path / 'report-orchestrator.json', {
        'tradingagents_sidecar': {
            'run_id': 'ta:abc',
            'generated_at': '2026-04-23T16:45:00Z',
        }
    })
    _write_json(tmp_path / 'finance-immediate-alert-state.json', {
        'last_delivered_primary_sha256': job.text_sha256('ALERT REPORT\n'),
        'last_delivered_at': '2026-04-23T16:25:00Z',
        'last_tradingagents_run_id': 'ta:abc',
    })

    assert job.main(['--mode', 'immediate-alert']) == 0
    assert capsys.readouterr().out.strip() == 'NO_REPLY'
    state = json.loads((tmp_path / 'finance-immediate-alert-state.json').read_text(encoding='utf-8'))
    assert state['should_deliver'] is False
    assert state['suppressed_reason'] == 'duplicate_primary_markdown'
