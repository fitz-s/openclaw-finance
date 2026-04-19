from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import brave_answers_sidecar as answers


def _pack(**overrides: object) -> dict:
    pack = {
        'pack_id': 'query-pack:answers-test',
        'lane': 'news_policy_narrative',
        'purpose': 'sidecar_synthesis',
        'authority_level': 'sidecar_only',
        'query': 'Explain whether TSLA delivery news has fresh source support.',
        'enable_entities': True,
        'country': 'US',
        'language': 'en',
        'no_execution': True,
    }
    pack.update(overrides)
    return pack


def _sse(content: str) -> str:
    return 'data: ' + json.dumps({'choices': [{'delta': {'content': content}}]}) + '\n\ndata: [DONE]\n'


def test_answers_sidecar_blocks_non_sidecar_authority() -> None:
    record = answers.run_sidecar(_pack(authority_level='canonical_candidate'), dry_run=True)
    assert record['status'] == 'blocked'
    assert 'answers_requires_sidecar_only_authority' in record['blocking_reasons']
    assert record['promotion_eligible'] is False
    assert record['sidecar_only'] is True


def test_answers_sidecar_dry_run_requires_no_api_key_or_network(monkeypatch) -> None:
    called = {'value': False}

    def fake_execute(*args, **kwargs):
        called['value'] = True
        raise AssertionError('network should not be called')

    monkeypatch.setattr(answers, 'execute_answers_request', fake_execute)
    record = answers.run_sidecar(_pack(), dry_run=True)
    assert record['status'] == 'dry_run'
    assert record['citation_count'] == 0
    assert record['promotion_eligible'] is False
    assert record['request_params']['stream'] is True
    assert record['request_params']['enable_citations'] is True
    assert called['value'] is False


def test_answers_sidecar_extracts_citations_as_evidence_candidates(monkeypatch) -> None:
    citation = {
        'number': 1,
        'url': 'https://www.reuters.com/markets/tesla-citation',
        'favicon': 'https://reuters.com/favicon.ico',
        'snippet': 'raw snippet should be digested only',
        'start_index': 10,
        'end_index': 20,
    }
    stream = _sse('TSLA has source support <citation>' + json.dumps(citation) + '</citation><enum_item>{"entity":"TSLA"}</enum_item><usage>{"input_tokens":10,"output_tokens":20}</usage>')

    def fake_execute(payload, *, api_key, timeout=60):
        assert api_key == 'secret-key'
        assert payload['model'] == 'brave'
        assert payload['stream'] is True
        assert payload['enable_citations'] is True
        assert payload['enable_entities'] is True
        assert payload['country'] == 'US'
        return 'ok', 200, {'X-RateLimit-Remaining': '1'}, stream, {}, None

    monkeypatch.setattr(answers, 'execute_answers_request', fake_execute)
    record = answers.run_sidecar(_pack(), api_key='secret-key')
    text = json.dumps(record, sort_keys=True)
    assert record['status'] == 'ok'
    assert record['citation_count'] == 1
    assert record['promotion_eligible'] is True
    assert record['citations'][0]['url'] == 'https://www.reuters.com/markets/tesla-citation'
    assert record['citations'][0]['snippet_digest'].startswith('sha256:')
    assert record['citations'][0]['raw_snippet_persisted'] is False
    assert record['citation_evidence_candidates'][0]['promotion_path'] == 'citation_only'
    assert record['answer_text_is_canonical_evidence'] is False
    assert record['entity_telemetry']['count'] == 1
    assert record['usage_telemetry']['input_tokens'] == 10
    assert 'raw snippet should be digested only' not in text
    assert 'secret-key' not in text
    assert 'data:' not in text


def test_answers_without_citations_cannot_promote(monkeypatch) -> None:
    def fake_execute(payload, *, api_key, timeout=60):
        return 'ok', 200, {}, _sse('This is a source-free answer.'), {}, None

    monkeypatch.setattr(answers, 'execute_answers_request', fake_execute)
    record = answers.run_sidecar(_pack(), api_key='secret-key')
    assert record['status'] == 'ok'
    assert record['citation_count'] == 0
    assert record['promotion_eligible'] is False
    assert record['citation_evidence_candidates'] == []
    assert record['promotion_rule'] == 'citations_only; answer_text_never_promotes'


def test_answers_rate_limit_metadata(monkeypatch) -> None:
    def fake_execute(payload, *, api_key, timeout=60):
        return 'rate_limited', 429, {'Retry-After': '60', 'X-RateLimit-Remaining': '0'}, '', {'code': 'RATE_LIMITED'}, '429'

    monkeypatch.setattr(answers, 'execute_answers_request', fake_execute)
    record = answers.run_sidecar(_pack(), api_key='secret-key')
    assert record['status'] == 'rate_limited'
    assert record['application_error_code'] == 'RATE_LIMITED'
    assert record['error_class'] == 'throttle_or_quota'
    assert record['retryable'] is True
    assert record['quota_state']['retry_after_sec'] == '60'
