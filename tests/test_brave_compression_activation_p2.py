from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from brave_budget_guard import normalize_state
from brave_compression_activation import run_activation

STATE = Path('/Users/leofitz/.openclaw/workspace/finance/state')


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows), encoding='utf-8')


def _pack() -> dict:
    return {
        'pack_id': 'query-pack:p2-compression',
        'lane': 'news_policy_narrative',
        'purpose': 'source_discovery',
        'query': 'fresh oil supply-chain confirmation',
        'freshness': 'day',
        'max_results': 2,
        'pack_is_not_authority': True,
        'no_execution': True,
    }


def _web_record() -> dict:
    return {
        'status': 'ok',
        'endpoint': 'brave/web/search',
        'result_urls': ['https://example.com/a', 'https://example.com/b'],
        'fetched_at': '2026-04-19T09:00:00Z',
        'no_execution': True,
    }


def _router() -> dict:
    return {
        'session_aperture': {
            'aperture_id': 'aperture:test:weekend',
            'session_class': 'weekend_aperture',
            'is_offhours': True,
            'is_long_gap': True,
            'answers_budget_class': 'high',
            'calendar_confidence': 'ok',
        }
    }


def _paths(name: str) -> dict[str, Path]:
    return {
        'query': STATE / f'test-p2-{name}-query.jsonl',
        'web': STATE / f'test-p2-{name}-web.jsonl',
        'news': STATE / f'test-p2-{name}-news.jsonl',
        'router': STATE / f'test-p2-{name}-router.json',
        'budget': STATE / f'test-p2-{name}-budget.json',
        'report': STATE / f'test-p2-{name}-report.json',
        'context': STATE / f'test-p2-{name}-context.jsonl',
        'answers': STATE / f'test-p2-{name}-answers.jsonl',
    }


def _clean(paths: dict[str, Path]) -> None:
    for path in paths.values():
        path.unlink(missing_ok=True)


def test_compression_activation_requires_seed_urls_before_context_or_answers() -> None:
    paths = _paths('missing-seed')
    _clean(paths)
    _write_jsonl(paths['query'], [_pack()])
    _write_jsonl(paths['web'], [])
    _write_jsonl(paths['news'], [])
    paths['router'].write_text(json.dumps(_router()), encoding='utf-8')
    paths['budget'].write_text(json.dumps(normalize_state({}, aperture_id='aperture:test:weekend', session_class='weekend_aperture', now=datetime(2026, 4, 19, tzinfo=timezone.utc))), encoding='utf-8')

    report = run_activation(query_packs_path=paths['query'], web_records_path=paths['web'], news_records_path=paths['news'], router_state_path=paths['router'], budget_state_path=paths['budget'], report_path=paths['report'], context_out=paths['context'], answers_out=paths['answers'])

    assert report['seed_url_count'] == 0
    assert report['results'][0]['reason'] == 'missing_seed_urls'
    assert report['context_record_count'] == 0
    assert report['answer_record_count'] == 0


def test_compression_activation_budget_denial_blocks_context_and_answers() -> None:
    paths = _paths('budget-denied')
    _clean(paths)
    _write_jsonl(paths['query'], [_pack()])
    _write_jsonl(paths['web'], [_web_record()])
    _write_jsonl(paths['news'], [])
    paths['router'].write_text(json.dumps(_router()), encoding='utf-8')
    budget = normalize_state({}, aperture_id='aperture:test:weekend', session_class='weekend_aperture', now=datetime(2026, 4, 19, tzinfo=timezone.utc))
    budget['usage']['llm_context_aperture'] = 4
    budget['usage']['answers_aperture'] = 3
    paths['budget'].write_text(json.dumps(budget), encoding='utf-8')

    report = run_activation(query_packs_path=paths['query'], web_records_path=paths['web'], news_records_path=paths['news'], router_state_path=paths['router'], budget_state_path=paths['budget'], report_path=paths['report'], context_out=paths['context'], answers_out=paths['answers'])

    assert report['budget_blocked_count'] == 2
    assert {result['kind'] for result in report['results']} == {'llm_context', 'answers'}
    assert all(result['reason'] == 'budget_guard_denied' for result in report['results'])


def test_compression_activation_dry_run_records_are_not_authority_and_do_not_consume_budget() -> None:
    paths = _paths('dry-run')
    _clean(paths)
    _write_jsonl(paths['query'], [_pack()])
    _write_jsonl(paths['web'], [_web_record()])
    _write_jsonl(paths['news'], [])
    paths['router'].write_text(json.dumps(_router()), encoding='utf-8')
    paths['budget'].write_text(json.dumps(normalize_state({}, aperture_id='aperture:test:weekend', session_class='weekend_aperture', now=datetime(2026, 4, 19, tzinfo=timezone.utc))), encoding='utf-8')

    report = run_activation(query_packs_path=paths['query'], web_records_path=paths['web'], news_records_path=paths['news'], router_state_path=paths['router'], budget_state_path=paths['budget'], report_path=paths['report'], context_out=paths['context'], answers_out=paths['answers'], dry_run=True)
    saved = json.loads(paths['budget'].read_text(encoding='utf-8'))

    assert report['context_record_count'] == 1
    assert report['answer_record_count'] == 1
    assert report['compression_records_are_not_authority'] is True
    assert report['answers_sidecar_only'] is True
    assert saved['usage']['llm_context_aperture'] == 0
    assert saved['usage']['answers_aperture'] == 0
    context_record = json.loads(paths['context'].read_text(encoding='utf-8').splitlines()[-1])
    answer_record = json.loads(paths['answers'].read_text(encoding='utf-8').splitlines()[-1])
    assert context_record['compression_activation_runner'] == 'brave-compression-activation-v1'
    assert answer_record['sidecar_only'] is True
    assert answer_record['answer_text_is_canonical_evidence'] is False
