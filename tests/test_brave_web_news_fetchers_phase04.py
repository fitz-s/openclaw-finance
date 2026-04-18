from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import brave_search_fetcher_common as brave


def _pack(**overrides: object) -> dict:
    pack = {
        'pack_id': 'query-pack:brave-test',
        'lane': 'news_policy_narrative',
        'purpose': 'source_discovery',
        'query': 'TSLA stock news',
        'freshness': 'day',
        'allowed_domains': ['reuters.com'],
        'required_entities': ['TSLA'],
        'max_results': 100,
        'no_execution': True,
    }
    pack.update(overrides)
    return pack


def test_brave_web_params_cap_count_and_freshness() -> None:
    params = brave.build_request_params(_pack(), endpoint_type='web')
    assert params['count'] == 20
    assert params['freshness'] == 'pd'
    assert params['safesearch'] == 'moderate'
    assert 'site:reuters.com' in params['q']
    assert params['extra_snippets'] == 'false'
    assert 'goggles_id' not in params


def test_brave_news_params_cap_count_and_date_range() -> None:
    params = brave.build_request_params(
        _pack(freshness=None, date_after='2026-04-01', date_before='2026-04-17', max_results=80),
        endpoint_type='news',
    )
    assert params['count'] == 50
    assert params['freshness'] == '2026-04-01to2026-04-17'
    assert params['safesearch'] == 'strict'


def test_brave_fetch_record_sanitizes_api_key_and_raw_snippets(monkeypatch) -> None:
    payload = {
        'web': {
            'results': [
                {
                    'title': 'Should not persist title',
                    'description': 'Should not persist description',
                    'extra_snippets': ['do not persist'],
                    'url': 'https://www.reuters.com/markets/tesla-test',
                    'age': '1 hour ago',
                    'profile': {'name': 'Reuters'},
                }
            ]
        }
    }

    def fake_execute(params, *, endpoint_type, api_key, timeout=20):
        assert api_key == 'secret-key'
        return 'ok', 200, {'X-RateLimit-Remaining': '42'}, payload, None

    monkeypatch.setattr(brave, 'execute_request', fake_execute)
    record = brave.fetch_from_pack(_pack(), endpoint_type='web', api_key='secret-key')
    text = json.dumps(record, sort_keys=True)
    assert record['status'] == 'ok'
    assert record['endpoint'] == 'brave/web/search'
    assert record['quota_state']['x_ratelimit_remaining'] == '42'
    assert record['raw_response_persisted'] is False
    assert record['raw_snippets_persisted'] is False
    assert 'secret-key' not in text
    assert 'Should not persist' not in text
    assert record['result_refs'][0]['url'] == 'https://www.reuters.com/markets/tesla-test'
    assert record['result_refs'][0]['metadata_only'] is True


def test_brave_rate_limit_error_becomes_fetch_record_metadata(monkeypatch) -> None:
    def fake_execute(params, *, endpoint_type, api_key, timeout=20):
        return 'rate_limited', 429, {'Retry-After': '60', 'X-RateLimit-Remaining': '0'}, {'code': 'RATE_LIMITED'}, '429'

    monkeypatch.setattr(brave, 'execute_request', fake_execute)
    record = brave.fetch_from_pack(_pack(), endpoint_type='news', api_key='secret-key')
    assert record['status'] == 'rate_limited'
    assert record['endpoint'] == 'brave/news/search'
    assert record['quota_state']['status_code'] == 429
    assert record['quota_state']['retry_after_sec'] == '60'
    assert record['result_count'] == 0
    assert record['error_code'] == '429'
    assert record['application_error_code'] == 'RATE_LIMITED'
    assert record['error_class'] == 'throttle_or_quota'
    assert record['retryable'] is True
    assert record['no_execution'] is True


def test_brave_dry_run_does_not_require_api_key_or_network(monkeypatch) -> None:
    called = {'value': False}

    def fake_execute(*args, **kwargs):
        called['value'] = True
        raise AssertionError('network should not be called')

    monkeypatch.setattr(brave, 'execute_request', fake_execute)
    record = brave.fetch_from_pack(_pack(), endpoint_type='news', dry_run=True)
    assert record['status'] == 'dry_run'
    assert record['dry_run'] is True
    assert record['result_count'] == 0
    assert called['value'] is False
    assert record['request_params']['freshness'] == 'pd'


def test_brave_missing_api_key_is_distinct_from_dry_run(monkeypatch) -> None:
    called = {'value': False}

    def fake_execute(*args, **kwargs):
        called['value'] = True
        raise AssertionError('network should not be called without an API key')

    monkeypatch.delenv('BRAVE_SEARCH_API_KEY', raising=False)
    monkeypatch.delenv('BRAVE_API_KEY', raising=False)
    monkeypatch.setattr(brave, 'read_api_key', lambda: None)
    monkeypatch.setattr(brave, 'execute_request', fake_execute)
    record = brave.fetch_from_pack(_pack(), endpoint_type='news', dry_run=False)
    assert record['status'] == 'failed'
    assert record['error_code'] == 'missing_api_key'
    assert record['application_error_code'] == 'missing_api_key'
    assert record['error_class'] == 'missing_credentials'
    assert record['retryable'] is False
    assert called['value'] is False


def test_brave_api_key_can_resolve_from_openclaw_exec_secret_ref(monkeypatch, tmp_path: Path) -> None:
    config = {
        'plugins': {
            'entries': {
                'brave': {
                    'config': {
                        'webSearch': {
                            'apiKey': {'source': 'exec', 'provider': 'keychain_exec', 'id': 'brave_search_api_key'}
                        }
                    }
                }
            }
        },
        'secrets': {
            'providers': {
                'keychain_exec': {'source': 'exec', 'command': '/safe/keychain_resolver.py', 'timeoutMs': 5000}
            }
        },
    }
    config_path = tmp_path / 'openclaw.json'
    config_path.write_text(json.dumps(config), encoding='utf-8')

    class Result:
        returncode = 0
        stdout = json.dumps({'protocolVersion': 1, 'values': {'brave_search_api_key': 'resolved-secret'}})

    def fake_run(cmd, *, input, capture_output, text, timeout):
        assert cmd == ['/safe/keychain_resolver.py']
        assert json.loads(input) == {'ids': ['brave_search_api_key']}
        return Result()

    monkeypatch.delenv('BRAVE_SEARCH_API_KEY', raising=False)
    monkeypatch.delenv('BRAVE_API_KEY', raising=False)
    monkeypatch.setattr(brave.subprocess, 'run', fake_run)
    assert brave.read_api_key(config_path=config_path) == 'resolved-secret'
