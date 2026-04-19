from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from brave_budget_guard import normalize_state
from brave_source_activation import run_activation

STATE = Path('/Users/leofitz/.openclaw/workspace/finance/state')


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows), encoding='utf-8')


def _pack() -> dict:
    return {
        'pack_id': 'query-pack:p8-recovery',
        'lane': 'news_policy_narrative',
        'purpose': 'source_discovery',
        'query': 'fresh source recovery test',
        'pack_is_not_authority': True,
        'no_execution': True,
        'budget_request': {'requires_budget_guard': True, 'search_units': 1, 'aperture_id': 'aperture:test', 'session_class': 'weekend_aperture'},
    }


def _paths(name: str) -> dict[str, Path]:
    return {
        'query': STATE / f'test-p8-{name}-query.jsonl',
        'registry': STATE / f'test-p8-{name}-registry.jsonl',
        'report': STATE / f'test-p8-{name}-report.json',
        'budget': STATE / f'test-p8-{name}-budget.json',
        'recovery': STATE / f'test-p8-{name}-recovery.json',
    }


def _clean(paths: dict[str, Path]) -> None:
    for path in paths.values():
        path.unlink(missing_ok=True)


def test_activation_deferred_by_recovery_breaker_before_budget(monkeypatch) -> None:
    paths = _paths('breaker')
    _clean(paths)
    _write_jsonl(paths['query'], [_pack()])
    paths['budget'].write_text(json.dumps(normalize_state({}, aperture_id='aperture:test', session_class='weekend_aperture', now=datetime(2026, 4, 20, tzinfo=timezone.utc))), encoding='utf-8')
    import brave_source_activation as activation
    monkeypatch.setattr(activation, 'build_recovery_policy', lambda: {'breaker_open': True, 'reason': 'recent_brave_quota_or_rate_limit', 'breaker_until': '2026-04-20T16:00:00Z'})

    report = run_activation(query_packs_path=paths['query'], registry_path=paths['registry'], report_path=paths['report'], budget_state_path=paths['budget'], recovery_policy_path=paths['recovery'], max_packs=1, dry_run=False, force=True)
    budget = json.loads(paths['budget'].read_text(encoding='utf-8'))

    assert report['source_recovery_deferred_count'] == 1
    assert report['budget_checked_count'] == 0
    assert report['fetch_record_count'] == 0
    assert budget['usage']['search_aperture'] == 0
    assert report['pack_results'][0]['reason'] == 'source_recovery_deferred'


def test_dry_run_activation_not_blocked_by_recovery_breaker(monkeypatch) -> None:
    paths = _paths('dry')
    _clean(paths)
    _write_jsonl(paths['query'], [_pack()])
    paths['budget'].write_text(json.dumps(normalize_state({}, aperture_id='aperture:test', session_class='weekend_aperture', now=datetime(2026, 4, 20, tzinfo=timezone.utc))), encoding='utf-8')
    import brave_source_activation as activation
    monkeypatch.setattr(activation, 'build_recovery_policy', lambda: {'breaker_open': True, 'reason': 'recent_brave_quota_or_rate_limit', 'breaker_until': '2026-04-20T16:00:00Z'})

    report = run_activation(query_packs_path=paths['query'], registry_path=paths['registry'], report_path=paths['report'], budget_state_path=paths['budget'], recovery_policy_path=paths['recovery'], max_packs=1, dry_run=True, force=True)
    assert report['source_recovery_deferred_count'] == 0
    assert report['budget_checked_count'] == 1
    assert report['status_counts']['dry_run'] == 1
