from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
sys.path.insert(0, str(SCRIPTS))

from finance_report_archive_compiler import archive_report, build_line_to_claim_refs


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_line_to_claim_refs_link_matching_subject_lines() -> None:
    refs = build_line_to_claim_refs(
        {'discord_primary_markdown': 'Fact\n- TSLA risk changed\n- BNO oil setup'},
        {'claims': [{'claim_id': 'claim:tsla', 'subject': 'TSLA'}, {'claim_id': 'claim:bno', 'subject': 'BNO'}]},
    )
    assert refs['matched_line_count'] == 2
    assert refs['refs'][0]['match_method'] == 'heuristic_subject_match'
    assert {cid for row in refs['refs'] for cid in row['claim_ids']} == {'claim:tsla', 'claim:bno'}


def test_report_archive_compiler_writes_manifest_and_artifacts(tmp_path, monkeypatch) -> None:
    import finance_report_archive_compiler as mod

    state = tmp_path / 'state'
    workspace = tmp_path / 'workspace'
    envelope = state / 'finance-decision-report-envelope.json'
    _write(envelope, {'report_id': 'R1', 'discord_primary_markdown': 'Fact\n- TSLA changed'})
    _write(state / 'report-reader' / 'R1.json', {'report_handle': 'R1'})
    _write(state / 'source-atoms' / 'latest-report.json', {'atoms': []})
    _write(state / 'claim-graph.json', {'claims': [{'claim_id': 'claim:1', 'subject': 'TSLA'}], 'graph_hash': 'sha256:x'})
    _write(state / 'context-gaps.json', {'gaps': []})
    _write(workspace / 'services' / 'market-ingest' / 'state' / 'source-health.json', {'status': 'pass'})
    _write(state / 'campaign-board.json', {'campaigns': []})
    _write(state / 'options-iv-surface.json', {'symbols': []})

    monkeypatch.setattr(mod, 'STATE', state)
    monkeypatch.setattr(mod, 'READER_DIR', state / 'report-reader')
    monkeypatch.setattr(mod, 'SOURCE_ATOMS_REPORT', state / 'source-atoms' / 'latest-report.json')
    monkeypatch.setattr(mod, 'CLAIM_GRAPH', state / 'claim-graph.json')
    monkeypatch.setattr(mod, 'CONTEXT_GAPS', state / 'context-gaps.json')
    monkeypatch.setattr(mod, 'SOURCE_HEALTH', workspace / 'services' / 'market-ingest' / 'state' / 'source-health.json')
    monkeypatch.setattr(mod, 'CAMPAIGN_BOARD', state / 'campaign-board.json')
    monkeypatch.setattr(mod, 'OPTIONS_IV_SURFACE', state / 'options-iv-surface.json')

    result = archive_report(out_root=state / 'report-archive', envelope_path=envelope)
    manifest = json.loads((state / 'report-archive' / 'R1' / 'manifest.json').read_text())
    line_refs = json.loads((state / 'report-archive' / 'R1' / 'line-to-claim-refs.json').read_text())

    assert result['status'] == 'pass'
    assert manifest['exact_replay_available'] is True
    assert not manifest['missing_required_artifacts']
    assert manifest['artifacts']['options_iv_surface']['available'] is True
    assert line_refs['matched_line_count'] == 1


def test_report_job_runs_archive_compiler_optionally() -> None:
    text = (ROOT / 'scripts' / 'finance_discord_report_job.py').read_text(encoding='utf-8')
    assert 'finance_report_archive_compiler.py' in text
    assert 'run_optional' in text
