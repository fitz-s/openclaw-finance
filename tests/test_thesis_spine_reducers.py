from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from invalidator_ledger_compiler import compile_ledger
from opportunity_queue_builder import build_queue
from thesis_registry_compiler import compile_registry
from thesis_spine_util import stable_id


def test_thesis_registry_preserves_manual_lifecycle_fields() -> None:
    intent = {
        'generated_at': '2026-04-01T00:00:00Z',
        'intents': [
            {
                'intent_id': 'watch-intent:xyz',
                'symbol': 'XYZ',
                'roles': ['held_core'],
            }
        ],
    }
    thesis_id = stable_id('thesis', 'XYZ')
    existing = {
        'theses': [
            {
                'thesis_id': thesis_id,
                'instrument': 'XYZ',
                'status': 'suppressed',
                'maturity': 'developing',
                'bull_case': ['manual bull case'],
                'bear_case': ['manual bear case'],
                'invalidators': ['manual invalidator'],
                'required_confirmations': ['manual confirmation'],
                'evidence_refs': ['ev:manual'],
                'scenario_refs': ['scenario:manual'],
                'last_meaningful_change_at': '2026-03-30T00:00:00Z',
                'promotion_reason': 'manual promotion',
                'retirement_reason': 'manual retirement',
            }
        ]
    }

    registry, active = compile_registry(intent, existing)
    card = registry['theses'][0]

    assert card['status'] == 'suppressed'
    assert card['maturity'] == 'developing'
    assert card['bull_case'] == ['manual bull case']
    assert card['bear_case'] == ['manual bear case']
    assert 'manual invalidator' in card['invalidators']
    assert 'packet staleness' in card['invalidators']
    assert 'manual confirmation' in card['required_confirmations']
    assert card['evidence_refs'] == ['ev:manual']
    assert card['scenario_refs'] == ['scenario:manual']
    assert card['last_meaningful_change_at'] == '2026-03-30T00:00:00Z'
    assert thesis_id not in active['active_thesis_ids']


def test_opportunity_queue_preserves_status_and_excludes_known_symbols() -> None:
    scan_state = {
        'last_scan_time': '2026-04-01T10:00:00Z',
        'accumulated': [
            {
                'tickers': ['ABC'],
                'discovery_scope': 'non_watchlist',
                'theme': 'new supply-chain dislocation',
                'novelty': 4,
                'importance': 5,
                'urgency': 3,
                'ts': '2026-04-01T10:01:00Z',
                'sources': ['source:abc'],
            },
            {
                'tickers': ['AAPL'],
                'discovery_scope': 'non_watchlist',
                'theme': 'known watchlist item',
                'novelty': 5,
                'importance': 5,
                'urgency': 5,
            },
            {
                'tickers': None,
                'theme': 'malformed discovery row',
                'novelty': 5,
            },
        ],
    }
    watchlist = {'tickers': [{'symbol': 'AAPL'}]}
    candidate_id = stable_id('opportunity', 'new supply-chain dislocation', 'ABC')
    existing = {
        'candidates': [
            {
                'candidate_id': candidate_id,
                'status': 'suppressed',
                'promotion_reason': 'manual promotion',
                'suppression_reason': 'too noisy',
                'linked_thesis_id': 'thesis:abc',
                'first_seen_at': '2026-03-30T00:00:00Z',
            }
        ]
    }

    queue = build_queue(scan_state, watchlist, existing)

    assert [item['instrument'] for item in queue['candidates']] == ['ABC']
    candidate = queue['candidates'][0]
    assert candidate['candidate_id'] == candidate_id
    assert candidate['status'] == 'suppressed'
    assert candidate['promotion_reason'] == 'manual promotion'
    assert candidate['suppression_reason'] == 'too noisy'
    assert candidate['linked_thesis_id'] == 'thesis:abc'
    assert candidate['first_seen_at'] == '2026-03-30T00:00:00Z'
    assert candidate['last_seen_at'] == '2026-04-01T10:01:00Z'


def test_opportunity_queue_penalizes_stale_external_sources() -> None:
    scan_state = {
        'last_updated': '2026-04-17T17:00:00Z',
        'last_scan_time': '2026-04-17T17:00:00Z',
        'accumulated': [
            {
                'tickers': ['BNO'],
                'discovery_scope': 'non_watchlist',
                'theme': 'BNO stale Reuters story',
                'novelty': 5,
                'importance': 5,
                'urgency': 5,
                'ts': '2026-04-17T17:00:00Z',
                'sources': [
                    'https://www.reuters.com/business/energy/oil-prices-fall-second-day-expectations-us-iran-talks-may-resume-2026-04-15/',
                    'https://www.reuters.com/business/energy/goldman-sachs-flags-twoway-risks-their-2026-oil-price-outlook-2026-04-15/',
                ],
            },
            {
                'tickers': ['USO'],
                'discovery_scope': 'non_watchlist',
                'theme': 'USO fresh market dislocation',
                'novelty': 4,
                'importance': 4,
                'urgency': 4,
                'ts': '2026-04-17T17:00:00Z',
                'sources': ['state:broad-market-proxy.json USO -9.58% 2026-04-17T17:00Z'],
            },
        ],
    }
    queue = build_queue(scan_state, {'tickers': []}, {})
    assert queue['candidates'][0]['instrument'] == 'USO'
    stale = next(item for item in queue['candidates'] if item['instrument'] == 'BNO')
    assert stale['source_freshness_status'] == 'stale'
    assert stale['external_stale_source_count'] == 2
    assert stale['score'] < stale['score_before_source_penalty']


def test_invalidator_ledger_is_idempotent_for_same_source_time() -> None:
    packet = {
        'packet_id': 'packet:test',
        'compiled_at': '2026-04-01T10:00:00Z',
        'contradictions': [
            {
                'contradiction_key': 'direction_conflict:test',
                'supports': ['ev:support'],
                'conflicts_with': ['ev:conflict'],
            }
        ],
    }
    judgment = {
        'judgment_id': 'judgment:test',
        'invalidators': ['packet staleness'],
        'evidence_refs': ['ev:support', 'ev:conflict'],
    }

    first = compile_ledger(packet, judgment, {})
    second = compile_ledger(packet, judgment, first)

    assert second['invalidators'] == first['invalidators']

    later_packet = {**packet, 'compiled_at': '2026-04-01T11:00:00Z'}
    third = compile_ledger(later_packet, judgment, second)

    assert [item['hit_count'] for item in third['invalidators']] == [2, 2]
    assert {item['last_seen_at'] for item in third['invalidators']} == {'2026-04-01T11:00:00Z'}
