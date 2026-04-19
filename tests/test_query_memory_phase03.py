from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from query_registry_compiler import build_query_run_record, should_skip_query
from source_memory_index import build_lane_watermarks, build_source_memory_index, claim_novelty_score


def _pack() -> dict:
    return {
        'pack_id': 'query-pack:test',
        'lane': 'news_policy_narrative',
        'purpose': 'source_discovery',
        'query': 'site:reuters.com TSLA stock news',
        'freshness': 'day',
        'date_after': '2026-04-17',
        'allowed_domains': ['reuters.com'],
        'no_execution': True,
    }


def test_query_registry_suppresses_zero_yield_repeat_queries() -> None:
    pack = _pack()
    record = build_query_run_record(
        pack,
        [{'status': 'ok', 'result_count': 0}],
        novel_claim_count=0,
        repeated_claim_count=0,
        fresh_result_ratio=0.0,
        fetched_at='2026-04-17T14:00:00Z',
    )
    assert record['outcome'] == 'low_yield'
    assert record['normalization_profile_version'] == 'query-normalization-v1'
    assert record['retention_class'] == 'metadata_only'
    assert should_skip_query(pack, [record], now='2026-04-17T15:00:00Z') is True


def test_query_registry_does_not_skip_high_yield_queries() -> None:
    pack = _pack()
    record = build_query_run_record(
        pack,
        [{'status': 'ok', 'result_count': 5, 'result_urls': ['https://www.reuters.com/markets/test']}],
        novel_claim_count=2,
        repeated_claim_count=0,
        fresh_result_ratio=0.8,
        fetched_at='2026-04-17T14:00:00Z',
    )
    assert record['outcome'] == 'high_yield'
    assert should_skip_query(pack, [record], now='2026-04-17T15:00:00Z') is False


def test_query_registry_captures_rate_limit_next_eligible_metadata() -> None:
    pack = _pack()
    record = build_query_run_record(
        pack,
        [{'status': 'rate_limited', 'result_count': 0, 'headers': {'Retry-After': '120', 'X-RateLimit-Remaining': '0'}, 'error_code': '429'}],
        fetched_at='2026-04-17T14:00:00Z',
    )
    assert record['outcome'] == 'failed'
    assert record['retry_after_sec'] == 120
    assert record['x_ratelimit_remaining'] == 0
    assert record['next_eligible_at'] == '2026-04-17T14:02:00Z'
    assert record['restricted_payload_present'] is False


def test_claim_novelty_uses_subject_predicate_horizon_not_theme_text() -> None:
    first = {'claim_id': 'claim:1', 'subject': 'TSLA', 'predicate': 'mentions', 'horizon': 'multi_day', 'direction': 'bearish', 'object': 'old text'}
    second = {'claim_id': 'claim:2', 'subject': 'TSLA', 'predicate': 'mentions', 'horizon': 'multi_day', 'direction': 'bearish', 'object': 'different summary text'}
    third = {'claim_id': 'claim:3', 'subject': 'TSLA', 'predicate': 'files', 'horizon': 'multi_day', 'direction': 'bearish', 'object': 'same ticker different predicate'}
    assert claim_novelty_score(first, []) == 1.0
    assert claim_novelty_score(second, [first]) == 0.75
    assert claim_novelty_score(third, [first, second]) == 1.0


def test_source_memory_index_groups_by_claim_identity_not_summary() -> None:
    atoms = [
        {'atom_id': 'atom:1', 'source_lane': 'news_policy_narrative', 'source_id': 'source:reuters', 'raw_uri': 'https://www.reuters.com/markets/tesla-a', 'event_time': '2026-04-17T14:00:00Z', 'ingested_at': '2026-04-17T14:01:00Z'},
        {'atom_id': 'atom:2', 'source_lane': 'news_policy_narrative', 'source_id': 'source:reuters', 'raw_uri': 'https://www.reuters.com/markets/tesla-b', 'event_time': '2026-04-17T15:00:00Z', 'ingested_at': '2026-04-17T15:01:00Z'},
    ]
    graph = {'claims': [
        {'claim_id': 'claim:1', 'atom_id': 'atom:1', 'source_lane': 'news_policy_narrative', 'source_id': 'source:reuters', 'subject': 'TSLA', 'predicate': 'mentions', 'horizon': 'multi_day', 'direction': 'bearish', 'object': 'summary one'},
        {'claim_id': 'claim:2', 'atom_id': 'atom:2', 'source_lane': 'news_policy_narrative', 'source_id': 'source:reuters', 'subject': 'TSLA', 'predicate': 'mentions', 'horizon': 'multi_day', 'direction': 'bearish', 'object': 'summary two'},
    ], 'graph_hash': 'sha256:test'}
    report = build_source_memory_index(atoms, graph, generated_at='2026-04-17T16:00:00Z')
    assert report['status'] == 'pass'
    assert report['restricted_payload_present'] is False
    assert report['memory_count'] == 1
    entry = report['entries'][0]
    assert entry['entity_key'] == 'TSLA'
    assert entry['predicate'] == 'mentions'
    assert entry['seen_count'] == 2
    assert entry['saturation_score'] == 0.25
    assert report['claim_novelty']['claim:2'] == 0.75


def test_lane_watermarks_emit_latest_fetch_and_novel_claim_times() -> None:
    atoms = [
        {'atom_id': 'atom:1', 'source_lane': 'news_policy_narrative', 'source_id': 'source:reuters', 'raw_uri': 'https://www.reuters.com/markets/tesla-a', 'event_time': '2026-04-17T14:00:00Z', 'ingested_at': '2026-04-17T14:01:00Z'},
        {'atom_id': 'atom:2', 'source_lane': 'news_policy_narrative', 'source_id': 'source:reuters', 'raw_uri': 'https://www.reuters.com/markets/tesla-b', 'event_time': '2026-04-17T15:00:00Z', 'ingested_at': '2026-04-17T15:01:00Z'},
    ]
    graph = {'claims': [
        {'claim_id': 'claim:1', 'atom_id': 'atom:1', 'source_lane': 'news_policy_narrative', 'source_id': 'source:reuters', 'subject': 'TSLA', 'predicate': 'mentions', 'horizon': 'multi_day', 'direction': 'bearish'},
        {'claim_id': 'claim:2', 'atom_id': 'atom:2', 'source_lane': 'news_policy_narrative', 'source_id': 'source:reuters', 'subject': 'TSLA', 'predicate': 'mentions', 'horizon': 'multi_day', 'direction': 'bearish'},
    ], 'graph_hash': 'sha256:test'}
    memory = build_source_memory_index(atoms, graph, generated_at='2026-04-17T16:00:00Z')
    watermarks = build_lane_watermarks(atoms, graph, memory, generated_at='2026-04-17T16:00:00Z')
    assert watermarks['status'] == 'pass'
    row = watermarks['watermarks'][0]
    assert row['lane'] == 'news_policy_narrative'
    assert row['entity_key'] == 'TSLA'
    assert row['domain'] == 'reuters.com'
    assert row['last_effective_fetch_at'] == '2026-04-17T15:01:00Z'
    assert row['last_novel_claim_at'] == '2026-04-17T15:00:00Z'
    assert row['merge_policy'] == 'lane_independent'
