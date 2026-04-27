from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from finance_report_reader_bundle import compile_bundle


def _stub_report(**overrides):
    base = {'report_hash': 'sha256:report', 'markdown': '# test'}
    base.update(overrides)
    return base


def _stub_entry(**overrides):
    base = {'decision_id': 'decision:123'}
    base.update(overrides)
    return base


def test_compile_bundle_merges_tradingagents_augmentation() -> None:
    augmentation = {
        'generated_at': '2099-04-23T00:00:00Z',
        'report_hash': 'sha256:report',
        'handles': {'TA1': {'type': 'tradingagents_research', 'ref': 'ta:test', 'instrument': 'NVDA', 'label': 'TradingAgents sidecar | NVDA'}},
        'object_cards': [{'handle': 'TA1', 'type': 'tradingagents_research', 'label': 'TradingAgents sidecar | NVDA', 'no_execution': True}],
        'starter_questions': [{'verb': 'why', 'handle': 'TA1'}],
        'starter_queries': ['why TA1'],
        'object_alias_map': {'TA1': 'TradingAgents sidecar | NVDA'},
        'followup_digest': ['TA1: review-only TradingAgents sidecar summary; no execution.'],
        'followup_slice_index': {'TA1': {'why': {'evidence_slice_id': 'slice:ta:test:TA1:why', 'linked_claims': [], 'linked_atoms': [], 'linked_context_gaps': [], 'lane_coverage': {}, 'source_health_summary': {}, 'retrieval_score': 0.0, 'permission_metadata': {'review_only': True, 'raw_thread_history_allowed': False, 'raw_source_dump_allowed': False}, 'content_hash': 'sha256:test', 'no_execution': True}}},
        'review_only': True,
        'no_execution': True,
        'max_age_hours': 72,
    }
    bundle = compile_bundle(
        _stub_report(), _stub_entry(),
        {'theses': []}, {'intents': []}, {'scenarios': []},
        {'candidates': []}, {'invalidators': []},
        {'agenda_items': []}, {}, {}, {}, {},
        tradingagents_aug=augmentation,
    )
    assert 'TA1' in bundle['handles']
    assert any(card['handle'] == 'TA1' for card in bundle['object_cards'])
    assert 'why TA1' in bundle['starter_queries']
    assert 'TA1' in bundle['followup_slice_index']
    assert bundle['no_execution'] is True


def test_compile_bundle_ignores_unbound_tradingagents_augmentation() -> None:
    augmentation = {
        'generated_at': '2099-04-23T00:00:00Z',
        'report_hash': 'sha256:other',
        'handles': {'TA1': {'type': 'tradingagents_research', 'ref': 'ta:test'}},
        'object_cards': [{'handle': 'TA1', 'type': 'tradingagents_research'}],
        'review_only': True,
        'no_execution': True,
        'max_age_hours': 72,
    }
    bundle = compile_bundle(
        _stub_report(), _stub_entry(),
        {'theses': []}, {'intents': []}, {'scenarios': []},
        {'candidates': []}, {'invalidators': []},
        {'agenda_items': []}, {}, {}, {}, {},
        tradingagents_aug=None,
    )
    assert 'TA1' not in bundle['handles']
