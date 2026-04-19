from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
sys.path.insert(0, str(SCRIPTS))

from finance_source_to_campaign_cutover_gate import evaluate


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_cutover_gate_holds_when_replay_missing(tmp_path) -> None:
    report = evaluate(tmp_path)
    assert report['status'] == 'hold'
    assert 'latest_report_archive_exact' in report['blocking_reasons']
    assert report['no_execution'] is True
    assert report['no_wake_mutation'] is True


def test_cutover_gate_ready_with_complete_artifacts(tmp_path, monkeypatch) -> None:
    import finance_source_to_campaign_cutover_gate as mod
    monkeypatch.setattr(mod, 'FINANCE', tmp_path)
    docs = tmp_path / 'docs' / 'openclaw-runtime' / 'reviewer-packets'
    state = tmp_path / 'state'
    _write(state / 'campaign-board.json', {
        'discord_risk_board_markdown': 'Risk\nEvidence：lanes=2',
        'campaigns': [{'lane_coverage_summary': {'source_diversity': 2}}],
    })
    _write(state / 'report-archive' / 'R1' / 'manifest.json', {'exact_replay_available': True})
    _write(docs / 'index.json', {'reports': [{'report_id': 'R1', 'exact_replay_available': True}]})
    _write(state / 'followup-context-route.json', {'evidence_slice_coverage': {'coverage_status': 'complete'}})
    _write(state / 'finance-discord-followup-threads.json', {'inactive_after_hours': 72, 'threads': {}})
    _write(state / 'source-roi-report.json', {'source_roi_rows': [{'campaign_value_score': 1.0}]})
    _write(state / 'options-iv-surface.json', {'contract': 'options-iv-surface-v1-shadow'})
    report = evaluate(state)
    assert report['status'] == 'ready'
    assert report['blocking_reasons'] == []
    assert report['readiness_is_authority'] is False


def test_report_job_runs_cutover_gate_optionally() -> None:
    text = (ROOT / 'scripts' / 'finance_discord_report_job.py').read_text(encoding='utf-8')
    assert 'finance_source_to_campaign_cutover_gate.py' in text
    assert 'run_optional' in text
