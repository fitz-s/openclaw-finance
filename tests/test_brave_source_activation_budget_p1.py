from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from brave_budget_guard import normalize_state
import brave_source_activation as activation
from brave_source_activation import run_activation

STATE = Path('/Users/leofitz/.openclaw/workspace/finance/state')


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows), encoding='utf-8')


def _pack() -> dict:
    return {
        'contract': 'query-pack-v1',
        'pack_id': 'query-pack:p1-budget',
        'lane': 'news_policy_narrative',
        'purpose': 'source_discovery',
        'query': 'fresh macro cross asset confirmation',
        'freshness': 'day',
        'allowed_domains': [],
        'required_entities': [],
        'max_results': 1,
        'authority_level': 'canonical_candidate',
        'session_aperture': {'aperture_id': 'aperture:test:pre', 'session_class': 'pre_open_gap', 'is_offhours': True},
        'budget_request': {'requires_budget_guard': True, 'search_units': 1, 'aperture_id': 'aperture:test:pre', 'session_class': 'pre_open_gap'},
        'pack_is_not_authority': True,
        'planner_not_evidence': True,
        'no_execution': True,
    }


def test_brave_source_activation_blocks_budget_denied_pack_without_fetch(monkeypatch) -> None:
    monkeypatch.setattr(activation, 'build_recovery_policy', lambda: {'breaker_open': False, 'reason': 'clear'})
    query_packs = STATE / 'test-p1-query-packs-denied.jsonl'
    registry = STATE / 'test-p1-query-registry-denied.jsonl'
    report = STATE / 'test-p1-brave-activation-denied.json'
    budget = STATE / 'test-p1-brave-budget-denied.json'
    for path in (registry, report, budget):
        path.unlink(missing_ok=True)
    _write_jsonl(query_packs, [_pack()])
    budget_state = normalize_state({}, aperture_id='aperture:test:pre', session_class='pre_open_gap', now=datetime(2026, 4, 19, tzinfo=timezone.utc))
    budget_state['usage']['search_aperture'] = 1
    budget.write_text(json.dumps(budget_state), encoding='utf-8')

    result = run_activation(query_packs_path=query_packs, registry_path=registry, report_path=report, max_packs=1, dry_run=False, force=True, budget_state_path=budget)

    assert result['status'] == 'pass'
    assert result['budget_blocked_count'] == 1
    assert result['fetch_record_count'] == 0
    assert result['pack_results'][0]['reason'] == 'budget_guard_denied'


def test_brave_source_activation_dry_run_budget_does_not_consume(monkeypatch) -> None:
    monkeypatch.setattr(activation, 'build_recovery_policy', lambda: {'breaker_open': False, 'reason': 'clear'})
    query_packs = STATE / 'test-p1-query-packs-dry.jsonl'
    registry = STATE / 'test-p1-query-registry-dry.jsonl'
    report = STATE / 'test-p1-brave-activation-dry.json'
    budget = STATE / 'test-p1-brave-budget-dry.json'
    for path in (registry, report, budget):
        path.unlink(missing_ok=True)
    _write_jsonl(query_packs, [_pack()])
    budget_state = normalize_state({}, aperture_id='aperture:test:pre', session_class='pre_open_gap', now=datetime(2026, 4, 19, tzinfo=timezone.utc))
    budget.write_text(json.dumps(budget_state), encoding='utf-8')

    result = run_activation(query_packs_path=query_packs, registry_path=registry, report_path=report, max_packs=1, dry_run=True, force=True, budget_state_path=budget)
    saved = json.loads(budget.read_text(encoding='utf-8'))

    assert result['budget_checked_count'] == 1
    assert result['pack_results'][0]['budget_decision']['allowed'] is True
    assert saved['usage']['search_aperture'] == 0


def test_query_registry_skip_does_not_consume_budget(monkeypatch) -> None:
    monkeypatch.setattr(activation, 'build_recovery_policy', lambda: {'breaker_open': False, 'reason': 'clear'})
    query_packs = STATE / 'test-p1-query-packs-skip.jsonl'
    registry = STATE / 'test-p1-query-registry-skip.jsonl'
    report = STATE / 'test-p1-brave-activation-skip.json'
    budget = STATE / 'test-p1-brave-budget-skip.json'
    for path in (registry, report, budget):
        path.unlink(missing_ok=True)
    _write_jsonl(query_packs, [_pack()])
    budget_state = normalize_state({}, aperture_id='aperture:test:pre', session_class='pre_open_gap', now=datetime(2026, 4, 19, tzinfo=timezone.utc))
    budget.write_text(json.dumps(budget_state), encoding='utf-8')

    first = run_activation(query_packs_path=query_packs, registry_path=registry, report_path=report, max_packs=1, dry_run=True, force=False, budget_state_path=budget)
    second = run_activation(query_packs_path=query_packs, registry_path=registry, report_path=report, max_packs=1, dry_run=False, force=False, budget_state_path=budget)
    saved = json.loads(budget.read_text(encoding='utf-8'))

    assert first['budget_checked_count'] == 1
    assert second['pack_results'][0]['status'] == 'skipped'
    assert second['pack_results'][0]['reason'] == 'query_registry_cooldown'
    assert second['budget_checked_count'] == 0
    assert saved['usage']['search_aperture'] == 0
