from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


SCRIPT_PATH = Path('/Users/leofitz/.openclaw/workspace/finance/scripts/gate_evaluator.py')
FINANCE_SCRIPTS = SCRIPT_PATH.parent


def _load_module():
    if str(FINANCE_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(FINANCE_SCRIPTS))
    spec = importlib.util.spec_from_file_location('gate_evaluator_live_evidence_test_module', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')


def test_live_evidence_freshness_clears_legacy_stale_only_with_support(tmp_path, monkeypatch) -> None:
    module = _load_module()
    evidence = tmp_path / 'live-evidence-records.jsonl'
    monkeypatch.setattr(module, 'LIVE_EVIDENCE', evidence)
    now = datetime(2026, 4, 18, 15, 0, tzinfo=timezone.utc)
    _write_jsonl(evidence, [
        {
            'evidence_id': 'ev:fresh-support',
            'observed_at': '2026-04-18T14:30:00Z',
            'published_at': '2026-04-18T14:25:00Z',
            'ingested_at': '2026-04-18T14:31:00Z',
            'quarantine': {
                'disposition': 'CONTEXT_ONLY',
                'allowed_for_wake': False,
                'allowed_for_judgment_support': True,
                'support_requires_primary_confirmation': True,
            },
            'structured_facts': {
                'support_requires_primary_confirmation': True,
            },
        }
    ])

    summary = module.live_evidence_freshness(now)

    assert summary['status'] == 'fresh_support'
    assert summary['clears_legacy_stale'] is True
    assert summary['wake_allowed_count'] == 0
    assert summary['fresh_support_count'] == 1
    assert summary['support_requires_primary_confirmation_count'] == 1
    assert 'no_wake_eligible_live_evidence' in summary['warnings']
    assert 'fresh_support_requires_primary_confirmation' in summary['warnings']


def test_live_evidence_fresh_context_without_support_does_not_clear_legacy_stale(tmp_path, monkeypatch) -> None:
    module = _load_module()
    evidence = tmp_path / 'live-evidence-records.jsonl'
    monkeypatch.setattr(module, 'LIVE_EVIDENCE', evidence)
    now = datetime(2026, 4, 18, 15, 0, tzinfo=timezone.utc)
    _write_jsonl(evidence, [
        {
            'evidence_id': 'ev:fresh-context',
            'observed_at': '2026-04-18T14:30:00Z',
            'published_at': '2026-04-18T14:25:00Z',
            'ingested_at': '2026-04-18T14:31:00Z',
            'quarantine': {
                'disposition': 'CONTEXT_ONLY',
                'allowed_for_wake': False,
                'allowed_for_judgment_support': False,
            },
        }
    ])

    summary = module.live_evidence_freshness(now)

    assert summary['status'] == 'fresh_context_only'
    assert summary['clears_legacy_stale'] is False
    assert summary['fresh_non_support_context_count'] == 1
    assert 'fresh_context_only_without_judgment_support' in summary['warnings']
