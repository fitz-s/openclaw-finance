"""Tests for finance_followup_answer_guard — review room answer validation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from finance_followup_answer_guard import validate


def _stub_bundle():
    return {
        'bundle_id': 'rb:Rabc123',
        'handles': {
            'Rabc12': {'type': 'report'},
            'T1': {'type': 'thesis', 'ref': 'thesis:TSLA', 'instrument': 'TSLA'},
            'O1': {'type': 'opportunity', 'ref': 'opp:SMR', 'instrument': 'SMR'},
        },
    }


def _stub_answer(**overrides):
    base = {
        'report_ref': 'sha256:abc123',
        'bundle_ref': 'rb:Rabc123',
        'selected_handle': 'T1',
        'verb': 'trace',
        'evidence_slice_id': 'slice:test',
        'answer_text': 'Fact\n- TSLA at $265\nInterpretation\n- sideways\nUnknown\n- volume\nWhat Would Change\n- breakout above $280',
    }
    base.update(overrides)
    return base


def test_valid_answer_passes():
    result = validate(_stub_answer(), _stub_bundle())
    assert result['status'] == 'pass'
    assert result['errors'] == []


def test_missing_report_ref():
    result = validate(_stub_answer(report_ref=None), _stub_bundle())
    assert result['status'] == 'fail'
    assert 'missing_report_ref' in result['errors']


def test_missing_handle():
    result = validate(_stub_answer(selected_handle=None), _stub_bundle())
    assert result['status'] == 'fail'
    assert 'missing_selected_handle' in result['errors']


def test_handle_not_in_bundle():
    result = validate(_stub_answer(selected_handle='T99'), _stub_bundle())
    assert result['status'] == 'fail'
    assert any('handle_not_in_bundle' in e for e in result['errors'])


def test_invalid_verb():
    result = validate(_stub_answer(verb='destroy'), _stub_bundle())
    assert result['status'] == 'fail'
    assert any('invalid_verb' in e for e in result['errors'])


def test_execution_language_blocked():
    answer = _stub_answer(answer_text='Fact\n- buy 100 shares at market order\nInterpretation\n- obvious\nUnknown\n- none\nWhat Would Change\n- nothing')
    result = validate(answer, _stub_bundle())
    assert result['status'] == 'fail'
    assert any('execution_language' in e for e in result['errors'])


def test_missing_structure_warns():
    answer = _stub_answer(answer_text='just a plain text answer without structure')
    result = validate(answer, _stub_bundle())
    # Missing structure is warning not error
    assert len(result['warnings']) > 0
    assert any('missing_section' in w for w in result['warnings'])


def test_forbidden_keys_blocked():
    answer = _stub_answer(thesis_state_mutation='lean_long')
    result = validate(answer, _stub_bundle())
    assert result['status'] == 'fail'
    assert any('forbidden_key' in e for e in result['errors'])


def test_bundle_id_mismatch():
    result = validate(_stub_answer(bundle_ref='rb:wrong'), _stub_bundle())
    assert result['status'] == 'fail'
    assert 'bundle_id_mismatch' in result['errors']


def test_review_only_always_set():
    result = validate(_stub_answer(), _stub_bundle())
    assert result['review_only'] is True
    assert result['no_execution'] is True


def test_missing_evidence_slice_id_blocked():
    answer = _stub_answer()
    answer.pop('evidence_slice_id')
    result = validate(answer, _stub_bundle())
    assert result['status'] == 'fail'
    assert 'missing_evidence_slice_id' in result['errors']


def test_insufficient_data_answer_allowed_but_still_review_only():
    answer = _stub_answer(answer_text='insufficient_data: missing linked_displacement_cases', answer_status='insufficient_data')
    result = validate(answer, _stub_bundle())
    assert result['status'] == 'pass'
    assert result['answer_status'] == 'insufficient_data'
    assert result['review_only'] is True


def test_followup_guard_blocks_answered_response_with_missing_required_coverage():
    answer = _stub_answer(
        answer_status='answered',
        evidence_slice_coverage={
            'coverage_status': 'insufficient',
            'missing_fields': ['linked_displacement_cases'],
        },
    )
    result = validate(answer, _stub_bundle())
    assert result['status'] == 'fail'
    assert 'answered_with_missing_required_evidence' in result['errors']
