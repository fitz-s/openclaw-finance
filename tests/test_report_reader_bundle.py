"""Tests for finance_report_reader_bundle — exploration surface."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from finance_report_reader_bundle import (
    build_agenda_cards,
    build_invalidator_cards,
    build_opportunity_cards,
    build_portfolio_attachment,
    build_starter_questions,
    build_starter_queries,
    build_thesis_cards,
    compile_bundle,
    decision_id_short,
    report_short_id,
)


def _stub_report(**overrides):
    base = {'report_hash': 'sha256:abc123', 'markdown': '# test'}
    base.update(overrides)
    return base


def _stub_entry(**overrides):
    base = {'decision_id': 'sha256:abc123'}
    base.update(overrides)
    return base


def test_decision_id_short():
    assert decision_id_short('sha256:abcdef1234567890') == 'Rabcdef'
    assert decision_id_short(None) == 'R0'


def test_report_short_id_prefers_report_hash():
    rid = report_short_id({'report_hash': 'sha256:abcdef123456'}, {'decision_id': 'decision:xyz'})
    assert rid == 'RABCD'


def test_thesis_cards_stable_sort():
    registry = {'theses': [
        {'thesis_id': 'thesis:AAPL', 'instrument': 'AAPL', 'status': 'watch', 'linked_watch_intent': 'wi:AAPL'},
        {'thesis_id': 'thesis:TSLA', 'instrument': 'TSLA', 'status': 'active', 'linked_watch_intent': 'wi:TSLA'},
    ]}
    intent = {'intents': [
        {'intent_id': 'wi:AAPL', 'symbol': 'AAPL', 'roles': ['event_sensitive']},
        {'intent_id': 'wi:TSLA', 'symbol': 'TSLA', 'roles': ['event_sensitive']},
    ]}
    handles, cards = build_thesis_cards(registry, intent, {})
    # Active TSLA should be T1
    assert 'T1' in handles
    assert handles['T1']['instrument'] == 'TSLA'
    assert cards[0]['handle'] == 'T1'
    assert cards[0]['instrument'] == 'TSLA'


def test_opportunity_cards_sorted_by_score():
    queue = {'candidates': [
        {'candidate_id': 'opp:low', 'instrument': 'LOW', 'status': 'candidate', 'score': 3},
        {'candidate_id': 'opp:high', 'instrument': 'HIGH', 'status': 'candidate', 'score': 9},
    ]}
    handles, cards = build_opportunity_cards(queue, {})
    assert handles['O1']['instrument'] == 'HIGH'
    assert cards[0]['score'] == 9


def test_invalidator_cards_sorted_by_hits():
    ledger = {'invalidators': [
        {'invalidator_id': 'inv:low', 'status': 'hit', 'hit_count': 1, 'description': 'low'},
        {'invalidator_id': 'inv:high', 'status': 'hit', 'hit_count': 7, 'description': 'high'},
    ]}
    handles, cards = build_invalidator_cards(ledger)
    assert handles['I1']['ref'] == 'inv:high'
    assert cards[0]['hit_count'] == 7


def test_agenda_cards_sorted_by_priority_and_resolve_linked_thesis():
    handles, cards = build_agenda_cards(
        {'agenda_items': [
            {'agenda_id': 'ag:low', 'agenda_type': 'existing_thesis_review', 'priority_score': 1, 'linked_thesis_ids': ['thesis:AAPL'], 'required_questions': ['q1']},
            {'agenda_id': 'ag:high', 'agenda_type': 'new_opportunity', 'priority_score': 9, 'linked_thesis_ids': ['thesis:TSLA'], 'attention_justification': 'test'},
        ]},
        {'theses': [
            {'thesis_id': 'thesis:TSLA', 'instrument': 'TSLA'},
            {'thesis_id': 'thesis:AAPL', 'instrument': 'AAPL'},
        ]},
        {'T1': {'ref': 'thesis:TSLA', 'instrument': 'TSLA'}},
    )
    assert handles['A1']['ref'] == 'ag:high'
    assert cards[0]['linked_thesis_handles'] == ['T1']


def test_portfolio_attachment_groups_roles():
    intent = {'intents': [
        {'symbol': 'AAPL', 'roles': ['held_core']},
        {'symbol': 'IAU', 'roles': ['hedge']},
        {'symbol': 'TSLA', 'roles': ['event_sensitive']},
    ]}
    attach = build_portfolio_attachment(intent, {})
    assert 'AAPL' in attach.get('held_core', [])
    assert 'IAU' in attach.get('hedge', [])
    assert 'TSLA' in attach.get('event_sensitive', [])


def test_starter_questions_from_cards():
    cards = [
        {'handle': 'A1', 'type': 'agenda', 'linked_thesis_handles': ['T1']},
        {'handle': 'T1', 'type': 'thesis', 'instrument': 'TSLA'},
        {'handle': 'O1', 'type': 'opportunity', 'instrument': 'SMR'},
    ]
    starters = build_starter_questions(cards)
    assert len(starters) >= 2
    verbs = {s['verb'] for s in starters}
    assert 'why' in verbs or 'challenge' in verbs


def test_starter_queries_include_expand():
    starters = [
        {'verb': 'why', 'handle': 'A1'},
        {'verb': 'compare', 'handle': 'A1', 'other_handle': 'T1'},
    ]
    queries = build_starter_queries(starters, 'RABCD')
    assert 'why A1' in queries
    assert 'compare A1 T1' in queries
    assert 'expand RABCD' in queries


def test_compile_bundle_basic():
    bundle = compile_bundle(
        _stub_report(), _stub_entry(),
        {'theses': []}, {'intents': []}, {'scenarios': []},
        {'candidates': []}, {'invalidators': []},
        {'agenda_items': []}, {}, {}, {}, {},
    )
    assert bundle['no_execution'] is True
    assert bundle['bundle_id'].startswith('rb:')
    assert isinstance(bundle['handles'], dict)
    assert isinstance(bundle['object_cards'], list)
    assert isinstance(bundle['starter_queries'], list)
    assert isinstance(bundle['object_alias_map'], dict)
    assert isinstance(bundle['followup_slice_index'], dict)
    assert isinstance(bundle['evidence_index_summary'], dict)


def test_compile_bundle_deterministic():
    """Same inputs → same bundle (except generated_at)."""
    kwargs = dict(
        report=_stub_report(),
        decision_log_entry=_stub_entry(),
        thesis_registry={'theses': [{'thesis_id': 'thesis:X', 'instrument': 'X', 'status': 'active'}]},
        watch_intent={'intents': [{'intent_id': 'wi:X', 'symbol': 'X', 'roles': ['event_sensitive']}]},
        scenario_cards_data={'scenarios': []},
        opportunity_queue={'candidates': []},
        invalidator_ledger={'invalidators': []},
        capital_agenda={'agenda_items': []},
        capital_graph={},
        displacement_cases={},
        prices={},
        portfolio={},
    )
    b1 = compile_bundle(**kwargs)
    b2 = compile_bundle(**kwargs)
    # Handles and cards should be identical
    assert b1['handles'] == b2['handles']
    assert len(b1['object_cards']) == len(b2['object_cards'])
    assert b1['starter_queries'] == b2['starter_queries']


def test_compile_bundle_exposes_claim_gap_source_health_slices():
    bundle = compile_bundle(
        _stub_report(), _stub_entry(),
        {'theses': [{'thesis_id': 'thesis:TSLA', 'instrument': 'TSLA', 'status': 'active'}]},
        {'intents': [{'intent_id': 'wi:TSLA', 'symbol': 'TSLA', 'roles': ['event_sensitive']}]},
        {'scenarios': []},
        {'candidates': []}, {'invalidators': []},
        {'agenda_items': []}, {}, {}, {}, {},
        source_atoms=[{'atom_id': 'atom:tsla', 'source_id': 'source:reuters', 'source_lane': 'news_policy_narrative'}],
        claim_graph={'claims': [{'claim_id': 'claim:tsla', 'atom_id': 'atom:tsla', 'subject': 'TSLA', 'predicate': 'mentions', 'object': 'TSLA delivery risk'}]},
        context_gaps={'gaps': [{'gap_id': 'gap:tsla', 'claim_id': 'claim:tsla', 'missing_lane': 'corp_filing_ir'}]},
        source_health={'sources': [{'source_id': 'source:reuters', 'freshness_status': 'fresh', 'rights_status': 'restricted', 'breach_reasons': ['rights_restricted']}]},
    )
    card = next(c for c in bundle['object_cards'] if c['handle'] == 'T1')
    assert card['linked_claims'] == ['claim:tsla']
    assert card['linked_atoms'] == ['atom:tsla']
    assert card['linked_context_gaps'] == ['gap:tsla']
    assert card['lane_coverage']['lanes'] == ['news_policy_narrative']
    assert card['source_health_summary']['degraded_count'] == 1
    trace_slice = bundle['followup_slice_index']['T1']['trace']
    assert trace_slice['linked_claims'] == ['claim:tsla']
    assert trace_slice['content_hash'].startswith('sha256:')
    assert trace_slice['retrieval_score'] == 1.0
    assert trace_slice['permission_metadata']['raw_thread_history_allowed'] is False
