from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from event_watcher import claim_signal_for_watcher
from undercurrent_compiler import compile_undercurrents
from test_undercurrent_engine import _atoms, _claim_graph, _context_gaps, _invalidators, _opportunities


def test_event_watcher_detects_claim_signal_without_theme_overlap() -> None:
    watcher = {'theme': 'delivery issue', 'tickers': ['TSLA'], 'seenClaimIds': []}
    signal = claim_signal_for_watcher(
        watcher,
        _claim_graph(),
        _context_gaps(),
        {'sources': [{'source_id': 'source:reuters', 'freshness_status': 'fresh', 'rights_status': 'ok'}]},
    )
    assert signal['has_new_signal'] is True
    assert 'claim:news' in signal['claim_ids']
    assert 'gap:filing' in signal['context_gap_ids']
    assert signal['reason'].startswith('claim_graph:')


def test_event_watcher_suppresses_seen_claim_ids() -> None:
    watcher = {'theme': 'delivery issue', 'tickers': ['TSLA'], 'seenClaimIds': ['claim:news', 'claim:price']}
    signal = claim_signal_for_watcher(watcher, _claim_graph(), _context_gaps(), {'sources': []})
    assert signal['has_new_signal'] is False
    assert signal['claim_ids'] == []


def test_event_watcher_exposes_degraded_source_health() -> None:
    watcher = {'theme': 'delivery issue', 'tickers': ['TSLA'], 'seenClaimIds': []}
    graph = _claim_graph()
    for claim in graph['claims']:
        if claim['claim_id'] == 'claim:news':
            claim['source_id'] = 'source:reuters'
    signal = claim_signal_for_watcher(
        watcher,
        graph,
        _context_gaps(),
        {'sources': [{'source_id': 'source:reuters', 'freshness_status': 'fresh', 'rights_status': 'ok', 'quota_status': 'degraded', 'coverage_status': 'unavailable'}]},
    )
    assert signal['degraded_sources'] == ['source:reuters']


def test_undercurrent_uses_quota_and_coverage_health_degradation() -> None:
    graph = _claim_graph()
    for claim in graph['claims']:
        claim['source_id'] = 'source:reuters' if claim['claim_id'] == 'claim:news' else 'source:yfinance'
    source_health = {'sources': [
        {'source_id': 'source:reuters', 'freshness_status': 'fresh', 'rights_status': 'ok', 'quota_status': 'degraded', 'coverage_status': 'unavailable', 'breach_reasons': ['quota_or_rate_limited']},
        {'source_id': 'source:yfinance', 'freshness_status': 'fresh', 'rights_status': 'ok'},
    ]}
    result = compile_undercurrents(_invalidators(), _opportunities(), {}, source_health=source_health, atoms=_atoms(), claim_graph=graph, context_gaps=_context_gaps())
    first = result['undercurrents'][0]
    assert first['source_health_summary']['quota_degraded_count'] == 1
    assert first['source_health_summary']['unavailable_count'] == 1
    assert 'quota_or_rate_limited' in first['source_health_summary']['degraded_reasons']
    assert first['claim_persistence_score'] >= 2
    assert first['claim_ids']
