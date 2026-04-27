from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import brave_source_activation as activation


def _pack(pack_id: str = 'query-pack:p1') -> dict:
    return {
        'contract': 'query-pack-v1',
        'pack_id': pack_id,
        'lane': 'news_policy_narrative',
        'purpose': 'source_discovery',
        'query': 'fresh Hormuz tanker targeted source confirmation',
        'freshness': 'day',
        'allowed_domains': [],
        'required_entities': [],
        'max_results': 10,
        'planner_not_evidence': True,
        'pack_is_not_authority': True,
        'no_execution': True,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')


def test_activation_falls_back_from_news_no_results_to_web(monkeypatch, tmp_path: Path) -> None:
    packs = tmp_path / 'packs.jsonl'
    registry = tmp_path / 'registry.jsonl'
    report = tmp_path / 'report.json'
    news_out = tmp_path / 'news.jsonl'
    web_out = tmp_path / 'web.jsonl'
    _write_jsonl(packs, [_pack()])

    def fake_default_out(endpoint: str) -> Path:
        return news_out if endpoint == 'news' else web_out

    def fake_fetch(pack, *, endpoint_type, dry_run, registry_path, timeout):
        return {
            'contract': 'source-fetch-record-v1',
            'fetch_id': f'fetch:{endpoint_type}',
            'pack_id': pack['pack_id'],
            'source_id': f'source:brave_{endpoint_type}',
            'endpoint': f'brave/{endpoint_type}/search',
            'fetched_at': '2026-04-18T15:00:00Z',
            'status': 'ok',
            'result_count': 0 if endpoint_type == 'news' else 2,
            'quota_state': {'status_code': 200},
            'result_refs': [] if endpoint_type == 'news' else [{'url': 'https://www.reuters.com/test'}],
            'no_execution': True,
        }

    monkeypatch.setattr(activation, 'safe_state_path', lambda path: True)
    monkeypatch.setattr(activation, 'default_out', fake_default_out)
    monkeypatch.setattr(activation, 'fetch_from_pack', fake_fetch)
    monkeypatch.setattr(activation, 'build_recovery_policy', lambda: {'breaker_open': False, 'reason': 'clear'})

    result = activation.run_activation(
        query_packs_path=packs,
        registry_path=registry,
        report_path=report,
        max_packs=1,
        force=True,
    )

    assert result['status'] == 'pass'
    assert result['fallback_count'] == 1
    assert result['fetch_record_count'] == 2
    assert result['status_counts'] == {'ok': 2}
    assert news_out.exists()
    assert web_out.exists()
    assert json.loads(report.read_text())['records_are_not_evidence'] is True


def test_activation_does_not_fallback_on_missing_credentials(monkeypatch, tmp_path: Path) -> None:
    packs = tmp_path / 'packs.jsonl'
    registry = tmp_path / 'registry.jsonl'
    report = tmp_path / 'report.json'
    news_out = tmp_path / 'news.jsonl'
    _write_jsonl(packs, [_pack()])

    def fake_fetch(pack, *, endpoint_type, dry_run, registry_path, timeout):
        return {
            'contract': 'source-fetch-record-v1',
            'fetch_id': f'fetch:{endpoint_type}',
            'pack_id': pack['pack_id'],
            'source_id': f'source:brave_{endpoint_type}',
            'endpoint': f'brave/{endpoint_type}/search',
            'fetched_at': '2026-04-18T15:00:00Z',
            'status': 'failed',
            'result_count': 0,
            'error_code': 'missing_api_key',
            'application_error_code': 'missing_api_key',
            'error_class': 'missing_credentials',
            'quota_state': {},
            'no_execution': True,
        }

    monkeypatch.setattr(activation, 'safe_state_path', lambda path: True)
    monkeypatch.setattr(activation, 'default_out', lambda endpoint: news_out)
    monkeypatch.setattr(activation, 'fetch_from_pack', fake_fetch)
    monkeypatch.setattr(activation, 'build_recovery_policy', lambda: {'breaker_open': False, 'reason': 'clear'})

    result = activation.run_activation(
        query_packs_path=packs,
        registry_path=registry,
        report_path=report,
        max_packs=1,
        force=True,
    )

    assert result['fetch_record_count'] == 1
    assert result['fallback_count'] == 0
    assert result['status_counts'] == {'failed': 1}
    record = json.loads(news_out.read_text().splitlines()[0])
    assert record['error_class'] == 'missing_credentials'


def test_activation_respects_query_registry_cooldown(monkeypatch, tmp_path: Path) -> None:
    packs = tmp_path / 'packs.jsonl'
    registry = tmp_path / 'registry.jsonl'
    report = tmp_path / 'report.json'
    _write_jsonl(packs, [_pack()])

    called = {'value': False}

    def fake_fetch(*args, **kwargs):
        called['value'] = True
        raise AssertionError('fetch should be skipped')

    monkeypatch.setattr(activation, 'safe_state_path', lambda path: True)
    monkeypatch.setattr(activation, 'should_skip_query', lambda pack, recent: True)
    monkeypatch.setattr(activation, 'fetch_from_pack', fake_fetch)
    monkeypatch.setattr(activation, 'build_recovery_policy', lambda: {'breaker_open': False, 'reason': 'clear'})

    result = activation.run_activation(
        query_packs_path=packs,
        registry_path=registry,
        report_path=report,
        max_packs=1,
        force=False,
    )

    assert called['value'] is False
    assert result['skipped_count'] == 1
    assert result['fetch_record_count'] == 0
