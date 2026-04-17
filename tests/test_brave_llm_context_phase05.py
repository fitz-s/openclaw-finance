from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import brave_llm_context_fetcher as ctx


def _pack(**overrides: object) -> dict:
    pack = {
        'pack_id': 'query-pack:ctx-test',
        'lane': 'news_policy_narrative',
        'purpose': 'source_reading',
        'query': 'TSLA delivery update Reuters source context',
        'freshness': 'day',
        'allowed_domains': ['reuters.com'],
        'maximum_number_of_tokens': 999999,
        'maximum_number_of_urls': 99,
        'maximum_number_of_snippets': 999,
        'no_execution': True,
    }
    pack.update(overrides)
    return pack


def test_llm_context_blocks_unscoped_first_pass_discovery() -> None:
    record = ctx.fetch_context(_pack(allowed_domains=[], selected_urls=[], goggles=None))
    assert record['status'] == 'blocked'
    assert 'unscoped_reader_query' in record['blocking_reasons']
    assert record['selected_source_reading'] is True
    assert record['no_execution'] is True


def test_llm_context_params_cap_budget_and_scope_domains() -> None:
    params = ctx.build_context_params(_pack())
    assert params['maximum_number_of_tokens'] == 32768
    assert params['maximum_number_of_urls'] == 50
    assert params['maximum_number_of_snippets'] == 100
    assert params['freshness'] == 'pd'
    assert params['context_threshold_mode'] == 'strict'
    assert 'site:reuters.com' in params['q']


def test_llm_context_total_snippet_ceiling_is_configurable() -> None:
    params = ctx.build_context_params(_pack(maximum_number_of_snippets=999, maximum_number_of_snippets_cap=256))
    assert params['maximum_number_of_snippets'] == 256


def test_llm_context_record_keeps_digests_not_raw_snippets(monkeypatch) -> None:
    payload = {
        'grounding': {
            'generic': [
                {'url': 'https://www.reuters.com/markets/tesla-context', 'title': 'TSLA Context', 'snippets': ['raw extracted snippet should not be persisted']}
            ]
        },
        'sources': {
            'https://www.reuters.com/markets/tesla-context': {'title': 'TSLA Context', 'hostname': 'reuters.com', 'age': ['2026-04-17']}
        },
    }

    def fake_execute(params, *, api_key, timeout=30):
        assert api_key == 'secret-key'
        return 'ok', 200, {'X-RateLimit-Remaining': '10'}, payload, None

    monkeypatch.setattr(ctx, 'execute_context_request', fake_execute)
    record = ctx.fetch_context(_pack(), api_key='secret-key')
    text = json.dumps(record, sort_keys=True)
    assert record['status'] == 'ok'
    assert record['endpoint'] == 'brave/llm/context'
    assert record['result_count'] == 1
    assert record['context_refs'][0]['hostname'] == 'reuters.com'
    assert record['context_refs'][0]['snippet_count'] == 1
    assert record['context_refs'][0]['snippet_digest'].startswith('sha256:')
    assert record['local_recall_summary']['raw_local_payload_persisted'] is False
    assert record['raw_context_persisted'] is False
    assert record['raw_snippets_persisted'] is False
    assert 'raw extracted snippet' not in text
    assert 'secret-key' not in text


def test_llm_context_rate_limit_error_metadata(monkeypatch) -> None:
    def fake_execute(params, *, api_key, timeout=30):
        return 'rate_limited', 429, {'Retry-After': '30'}, {'code': 'RATE_LIMITED'}, '429'

    monkeypatch.setattr(ctx, 'execute_context_request', fake_execute)
    record = ctx.fetch_context(_pack(), api_key='secret-key')
    assert record['status'] == 'rate_limited'
    assert record['application_error_code'] == 'RATE_LIMITED'
    assert record['error_class'] == 'throttle_or_quota'
    assert record['retryable'] is True
    assert record['quota_state']['retry_after_sec'] == '30'


def test_llm_context_dry_run_requires_no_api_key_or_network(monkeypatch) -> None:
    called = {'value': False}

    def fake_execute(*args, **kwargs):
        called['value'] = True
        raise AssertionError('network should not be called')

    monkeypatch.setattr(ctx, 'execute_context_request', fake_execute)
    record = ctx.fetch_context(_pack(), dry_run=True)
    assert record['status'] == 'dry_run'
    assert record['result_count'] == 0
    assert record['raw_context_persisted'] is False
    assert called['value'] is False
