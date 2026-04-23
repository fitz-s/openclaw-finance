from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import tradingagents_sidecar_job as job


def test_sidecar_job_records_failure_when_runner_fails(tmp_path: Path, monkeypatch) -> None:
    tg_state = tmp_path / 'state' / 'tradingagents'
    monkeypatch.setattr(job, 'TRADINGAGENTS_STATE', tg_state)
    monkeypatch.setattr(job, 'evaluate_runtime_readiness', lambda: {'status': 'pass', 'errors': [], 'warnings': []})

    def fake_build_request(mode, instrument=None):
        run_root = tg_state / 'runs' / 'ta:test'
        run_root.mkdir(parents=True, exist_ok=True)
        return {
            'job_id': f'finance-tradingagents-sidecar:{mode}',
            'run_id': 'ta:test',
            'instrument': instrument or 'NVDA',
            'config': {'timeout_seconds': 5},
            'request_path': str(run_root / 'request.json'),
        }

    def fake_run(*args, **kwargs):
        raw_dir = tg_state / 'runs' / 'ta:test' / 'raw'
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / 'run-artifact.json').write_text(json.dumps({'status': 'fail', 'review_only': True, 'no_execution': True}), encoding='utf-8')
        return SimpleNamespace(returncode=1, stdout='fail', stderr='boom')

    monkeypatch.setattr(job, 'build_request', fake_build_request)
    monkeypatch.setattr(job.subprocess, 'run', fake_run)

    report = job.run_job('manual', 'NVDA')
    assert report['status'] == 'fail'
    assert (tg_state / 'job-reports' / 'ta:test.json').exists()


def test_sidecar_job_success_path(tmp_path: Path, monkeypatch) -> None:
    tg_state = tmp_path / 'state' / 'tradingagents'
    monkeypatch.setattr(job, 'TRADINGAGENTS_STATE', tg_state)
    monkeypatch.setattr(job, 'TRADINGAGENTS_CONTEXT_DIGEST', tg_state / 'latest-context-digest.json')
    monkeypatch.setattr(job, 'TRADINGAGENTS_READER_AUGMENTATION', tg_state / 'latest-reader-augmentation.json')
    monkeypatch.setattr(job, 'evaluate_runtime_readiness', lambda: {'status': 'pass', 'errors': [], 'warnings': []})

    def fake_build_request(mode, instrument=None):
        run_root = tg_state / 'runs' / 'ta:test'
        run_root.mkdir(parents=True, exist_ok=True)
        return {
            'job_id': f'finance-tradingagents-sidecar:{mode}',
            'run_id': 'ta:test',
            'instrument': instrument or 'NVDA',
            'config': {'timeout_seconds': 5},
            'request_path': str(run_root / 'request.json'),
        }

    def fake_run(*args, **kwargs):
        raw_dir = tg_state / 'runs' / 'ta:test' / 'raw'
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / 'run-artifact.json').write_text(json.dumps({'status': 'pass', 'review_only': True, 'no_execution': True}), encoding='utf-8')
        return SimpleNamespace(returncode=0, stdout='ok', stderr='')

    monkeypatch.setattr(job, 'build_request', fake_build_request)
    monkeypatch.setattr(job.subprocess, 'run', fake_run)
    monkeypatch.setattr(job, 'translate_run', lambda run_root: {'status': 'pass'})
    monkeypatch.setattr(job, 'validate_run', lambda run_root: {'status': 'pass', 'errors': []})
    monkeypatch.setattr(job, 'compile_surfaces', lambda run_root: {'context_path': 'context.json', 'reader_path': 'reader.json'})

    report = job.run_job('manual', 'NVDA')
    assert report['status'] == 'pass'
    assert report['steps'][-1]['step'] == 'surface'


def test_sidecar_job_stops_on_runtime_readiness_failure(tmp_path: Path, monkeypatch) -> None:
    tg_state = tmp_path / 'state' / 'tradingagents'
    monkeypatch.setattr(job, 'TRADINGAGENTS_STATE', tg_state)

    def fake_build_request(mode, instrument=None):
        run_root = tg_state / 'runs' / 'ta:test'
        run_root.mkdir(parents=True, exist_ok=True)
        return {
            'job_id': f'finance-tradingagents-sidecar:{mode}',
            'run_id': 'ta:test',
            'instrument': instrument or 'NVDA',
            'config': {'timeout_seconds': 5},
            'request_path': str(run_root / 'request.json'),
        }

    monkeypatch.setattr(job, 'build_request', fake_build_request)
    monkeypatch.setattr(job, 'evaluate_runtime_readiness', lambda: {
        'status': 'fail',
        'errors': ['missing_auth_source:GOOGLE_API_KEY'],
        'warnings': ['python_3_14_plus_langchain_compat_warning'],
    })

    report = job.run_job('manual', 'NVDA')
    assert report['status'] == 'fail'
    assert report['steps'][1]['step'] == 'runtime_readiness'
    assert report['steps'][1]['status'] == 'fail'
    assert (tg_state / 'runtime-readiness.json').exists()
