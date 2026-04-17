from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import source_health_monitor as shm


def test_source_health_marks_brave_quota_audit_as_degraded() -> None:
    report = shm.build_report(
        brave_audit={'quota_failures': [{'line_time': '2026-04-17T13:21:00', 'error': 'USAGE_LIMIT_EXCEEDED'}]},
        generated_at='2026-04-17T22:00:00Z',
    )
    assert report['status'] == 'degraded'
    row = report['sources'][0]
    assert row['source_id'] == 'source:brave_llm_context'
    assert row['quota_status'] == 'degraded'
    assert row['rate_limit_status'] == 'limited'
    assert row['rate_limited_count'] == 1
    assert row['breaker_state'] == 'open'
    assert row['degraded_state'] == 'quota_limited'
    assert 'brave_audit_usage_limit_exceeded' in row['breach_reasons']
    assert row['problem_details']['type'] == 'source-health-degradation'
    assert report['stale_reuse_guard']['status'] == 'active'


def test_source_health_marks_rate_limited_fetch_record() -> None:
    record = {
        'fetch_id': 'fetch:1',
        'source_id': 'source:brave_news',
        'endpoint': 'brave/news/search',
        'status': 'rate_limited',
        'fetched_at': '2026-04-17T21:59:00Z',
        'application_error_code': 'RATE_LIMITED',
        'quota_state': {'status_code': 429, 'retry_after_sec': '60', 'x_ratelimit_remaining': '0'},
    }
    report = shm.build_report(fetch_records=[record], generated_at='2026-04-17T22:00:00Z')
    row = report['sources'][0]
    assert row['quota_status'] == 'degraded'
    assert row['rate_limit_status'] == 'limited'
    assert row['retry_after_sec'] == '60'
    assert row['retry_after_seconds'] == '60'
    assert row['x_ratelimit_remaining'] == '0'
    assert row['quota_remaining'] == '0'
    assert row['coverage_status'] == 'unavailable'
    assert row['health_score'] < 1.0


def test_source_health_dry_run_is_unknown_not_fresh() -> None:
    record = {
        'fetch_id': 'fetch:dry',
        'source_id': 'source:brave_news',
        'endpoint': 'brave/news/search',
        'status': 'dry_run',
        'fetched_at': '2026-04-17T21:59:00Z',
        'quota_state': {},
    }
    report = shm.build_report(fetch_records=[record], generated_at='2026-04-17T22:00:00Z')
    row = report['sources'][0]
    assert row['coverage_status'] == 'unknown'
    assert row['quota_status'] == 'unknown'
    assert 'dry_run_no_live_fetch' in row['breach_reasons']
    assert row['freshness_status'] == 'unknown'
    assert row['freshness_lag_seconds'] is None


def test_source_health_atoms_contribute_freshness_and_rights() -> None:
    atoms = [
        {
            'atom_id': 'atom:fresh',
            'source_id': 'source:reuters',
            'ingested_at': '2026-04-17T21:30:00Z',
            'freshness_budget_seconds': 3600,
            'compliance_class': 'public',
            'redistribution_policy': 'raw_ok',
        },
        {
            'atom_id': 'atom:stale',
            'source_id': 'source:unknown_web',
            'ingested_at': '2026-04-15T21:30:00Z',
            'freshness_budget_seconds': 3600,
            'compliance_class': 'unknown',
            'redistribution_policy': 'unknown',
        },
    ]
    report = shm.build_report(atoms=atoms, generated_at='2026-04-17T22:00:00Z')
    rows = {row['source_id']: row for row in report['sources']}
    assert rows['source:reuters']['freshness_status'] == 'fresh'
    assert rows['source:reuters']['freshness_lag_seconds'] == 1800
    assert rows['source:reuters']['rights_status'] == 'ok'
    assert rows['source:unknown_web']['freshness_status'] == 'stale'
    assert rows['source:unknown_web']['rights_status'] == 'unknown'
    assert rows['source:unknown_web']['health_hash'].startswith('sha256:')


def test_source_health_cli_writes_report_and_history(tmp_path: Path, monkeypatch) -> None:
    out = Path('/Users/leofitz/.openclaw/workspace/finance/state/test-source-health.json')
    history = Path('/Users/leofitz/.openclaw/workspace/finance/state/test-source-health-history.jsonl')
    atoms = tmp_path / 'atoms.jsonl'
    atoms.write_text(json.dumps({'atom_id': 'atom:1', 'source_id': 'source:reuters', 'ingested_at': '2026-04-17T21:00:00Z', 'freshness_budget_seconds': 3600, 'compliance_class': 'public', 'redistribution_policy': 'raw_ok'}) + '\n', encoding='utf-8')
    monkeypatch.setattr(shm, 'SOURCE_ATOMS', atoms)
    monkeypatch.setattr(shm, 'BRAVE_WEB', tmp_path / 'missing-web.jsonl')
    monkeypatch.setattr(shm, 'BRAVE_NEWS', tmp_path / 'missing-news.jsonl')
    monkeypatch.setattr(shm, 'BRAVE_CONTEXT', tmp_path / 'missing-context.jsonl')
    monkeypatch.setattr(shm, 'BRAVE_ANSWERS', tmp_path / 'missing-answers.jsonl')
    monkeypatch.setattr(shm, 'BRAVE_AUDIT', tmp_path / 'missing-audit.json')
    monkeypatch.setattr(shm, 'REDUCER_REPORT', tmp_path / 'missing-reducer.json')
    try:
        code = shm.main(['--out', str(out), '--history', str(history)])
        assert code == 0
        payload = json.loads(out.read_text(encoding='utf-8'))
        assert payload['source_count'] == 1
        assert payload['no_execution'] is True
        assert history.exists()
    finally:
        out.unlink(missing_ok=True)
        history.unlink(missing_ok=True)
