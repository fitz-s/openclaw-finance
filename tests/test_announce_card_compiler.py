"""Tests for announce_card_compiler — deterministic notification surface."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from announce_card_compiler import (
    build_display_handles,
    classify_attention,
    compile_card,
    decision_id_short,
    find_dominant_object,
    render_announce_markdown,
    validate_posting_contract,
)


def _stub_report(**overrides):
    base = {
        'renderer_id': 'thesis-delta-deterministic-v1',
        'markdown': '# report',
        'report_hash': 'sha256:abc123',
        'thesis_state': 'no_trade',
    }
    base.update(overrides)
    return base


def _stub_log_entry(**overrides):
    base = {'decision_id': 'sha256:abc123', 'wake_threshold_attribution': {'attribution': 'packet_update_only'}}
    base.update(overrides)
    return base


def _stub_agenda(items=None):
    return {'agenda_items': items or []}


def _stub_opps(candidates=None):
    return {'candidates': candidates or []}


def _stub_invs(invs=None):
    return {'invalidators': invs or []}


def _stub_theses(theses=None):
    return {'theses': theses or []}


def test_decision_id_short():
    assert decision_id_short('sha256:abcdef1234567890') == 'Rabcdef'
    assert decision_id_short(None) == 'R0'
    assert decision_id_short('') == 'R0'


def test_attention_class_ops_on_missing_markdown():
    report = _stub_report(markdown='')
    assert classify_attention(report, _stub_log_entry(), _stub_agenda(), _stub_invs()) == 'ops'


def test_attention_class_review_with_agenda():
    items = [{'agenda_id': 'a1', 'agenda_type': 'test', 'priority_score': 5}]
    assert classify_attention(_stub_report(), _stub_log_entry(), _stub_agenda(items), _stub_invs()) == 'review'


def test_attention_class_skim_fallback():
    assert classify_attention(_stub_report(), _stub_log_entry(), _stub_agenda(), _stub_invs()) == 'skim'


def test_attention_class_deep_dive():
    log = _stub_log_entry(wake_threshold_attribution={'attribution': 'canonical_wake_dispatch'})
    invs = _stub_invs([{'invalidator_id': 'i1', 'status': 'hit', 'hit_count': 5}])
    assert classify_attention(_stub_report(), log, _stub_agenda(), invs) == 'deep_dive'


def test_dominant_agenda_first():
    agenda = _stub_agenda([{'agenda_id': 'a1', 'agenda_type': 'invalidator_escalation', 'attention_justification': 'invalidator direction_conflict:theme:unknown_discovery has hit 11 times'}])
    dom = find_dominant_object(agenda, _stub_opps(), _stub_invs(), _stub_theses())
    assert dom['type'] == 'agenda'
    assert '11' in dom['label']
    assert '方向冲突' in dom['label']


def test_dominant_opp_if_no_agenda():
    opps = _stub_opps([{'candidate_id': 'o1', 'instrument': 'SMR', 'status': 'candidate', 'score': 8}])
    dom = find_dominant_object(_stub_agenda(), opps, _stub_invs(), _stub_theses())
    assert dom['type'] == 'opportunity'
    assert dom['instrument'] == 'SMR'


def test_dominant_inv_if_no_opp():
    invs = _stub_invs([{'invalidator_id': 'i1', 'status': 'hit', 'hit_count': 3, 'description': 'test'}])
    dom = find_dominant_object(_stub_agenda(), _stub_opps(), invs, _stub_theses())
    assert dom['type'] == 'invalidator'


def test_dominant_steady_state_if_empty():
    dom = find_dominant_object(_stub_agenda(), _stub_opps(), _stub_invs(), _stub_theses())
    assert dom['type'] == 'system_steady_state'


def test_compile_card_basic():
    card = compile_card(
        _stub_report(), _stub_log_entry(), _stub_agenda(),
        _stub_opps(), _stub_invs(), _stub_theses(),
    )
    assert card['no_execution'] is True
    assert 'Finance｜' in card['announce_markdown']
    assert card['attention_class'] in {'skim', 'review', 'ops', 'deep_dive', 'ignore'}
    assert card['card_id'].startswith('announce:')
    assert isinstance(card['display_handles'], list)


def test_announce_markdown_format():
    md = render_announce_markdown(
        'review',
        {'type': 'opportunity', 'label': 'SMR 候选'},
        '有新证据',
        '要不要深挖',
        ['T1=TSLA', 'O1=SMR'],
    )
    assert md.startswith('Finance｜Review')
    assert '对象' in md
    assert 'T1=TSLA' in md


def test_posting_contract_clean():
    md = 'Finance｜Review\n值得看：test\n为什么现在：test\n你只要决定：test\n对象：T1=TSLA'
    assert validate_posting_contract(md) == []


def test_posting_contract_blocks_utc():
    md = 'Finance｜Review\n12:30 UTC something'
    violations = validate_posting_contract(md)
    assert any('UTC' in v for v in violations)


def test_ignore_on_duplicate_skim():
    card = compile_card(
        _stub_report(), _stub_log_entry(), _stub_agenda(),
        _stub_opps(), _stub_invs(), _stub_theses(),
        prev_card={'attention_class': 'skim', 'dominant_object': {'id': '', 'type': 'system_steady_state'}},
    )
    assert card['attention_class'] == 'ignore'


def test_display_handles_show_labels_not_report_handle():
    display = build_display_handles(
        _stub_theses([
            {'thesis_id': 't:1', 'instrument': 'TSLA', 'status': 'active'},
            {'thesis_id': 't:2', 'instrument': 'SMR', 'status': 'watch'},
        ]),
        _stub_opps([
            {'candidate_id': 'o:1', 'instrument': 'XLB', 'status': 'candidate', 'score': 9},
        ]),
        _stub_invs([
            {'invalidator_id': 'i:1', 'status': 'hit', 'hit_count': 4, 'description': 'price_vs_negative_upstream:TSLA'},
        ]),
    )
    assert display == ['T1=TSLA', 'T2=SMR', 'O1=XLB', 'I1=TSLA反证']
