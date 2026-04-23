from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import tradingagents_surface_compiler as compiler


def test_compile_surfaces_updates_latest_files(tmp_path: Path, monkeypatch) -> None:
    run_root = tmp_path / 'run'
    (run_root / 'normalized').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(compiler, 'TRADINGAGENTS_CONTEXT_DIGEST', tmp_path / 'latest-context-digest.json')
    monkeypatch.setattr(compiler, 'TRADINGAGENTS_READER_AUGMENTATION', tmp_path / 'latest-reader-augmentation.json')
    monkeypatch.setattr(compiler, 'TRADINGAGENTS_LATEST', tmp_path / 'latest.json')
    monkeypatch.setattr(compiler, 'TRADINGAGENTS_STATUS', tmp_path / 'status.json')

    request = {
        'run_id': 'ta:test',
        'request_path': str(run_root / 'request.json'),
        'instrument': 'NVDA',
        'analysis_date': '2026-04-23',
        'source_bindings': {
            'report_envelope': {'report_hash': 'sha256:report'},
            'decision_log': {'decision_id': 'decision:123'},
            'context_packet': {'packet_hash': 'sha256:packet'},
        },
    }
    advisory = {
        'summary_title_safe': 'TradingAgents sidecar | NVDA',
        'why_now_safe': ['Demand remains durable and requires validation.'],
        'why_not_now_safe': ['This sidecar cannot change judgment or execution state.'],
        'invalidators_safe': ['If deterministic sources disagree, deprioritize the sidecar.'],
        'required_confirmations_safe': ['Validate source freshness before review use.'],
        'source_gaps_safe': ['No deterministic citation promotion exists yet.'],
        'risk_flags_safe': ['Wait for valuation confirmation.'],
    }
    validation = {
        'status': 'pass',
        'report_hash': 'sha256:report',
        'context_pack_eligible': True,
        'reader_eligible': True,
        'context_digest_max_age_hours': 24,
        'reader_augmentation_max_age_hours': 72,
    }
    (run_root / 'request.json').write_text(json.dumps(request), encoding='utf-8')
    (run_root / 'normalized' / 'advisory-decision.json').write_text(json.dumps(advisory), encoding='utf-8')
    (run_root / 'validation.json').write_text(json.dumps(validation), encoding='utf-8')

    paths = compiler.compile_surfaces(run_root)

    assert Path(paths['context_path']).exists()
    assert Path(paths['reader_path']).exists()
    latest = json.loads((tmp_path / 'latest.json').read_text(encoding='utf-8'))
    assert latest['run_id'] == 'ta:test'
    reader = json.loads((tmp_path / 'latest-reader-augmentation.json').read_text(encoding='utf-8'))
    assert 'TA1' in reader['handles']
    assert reader['review_only'] is True
    assert reader['no_execution'] is True
