from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from finance_decision_report_render import build_report
from finance_report_product_validator import validate_report


def _packet():
    return {
        'packet_id': 'packet:test',
        'packet_hash': 'sha256:' + 'a' * 64,
        'instrument': 'TSLA',
        'layer_digest': {'L0': ['ev:1'], 'L1': [], 'L2': [], 'L3': [], 'L4': []},
        'contradictions': [],
        'evidence_refs': ['ev:1'],
        'thesis_refs': ['thesis:tsla'],
        'scenario_refs': [],
        'opportunity_candidate_refs': ['opp:xlb'],
        'invalidator_refs': ['inv:tsla'],
        'source_quality_summary': {'wake_eligible_count': 0, 'judgment_support_count': 1, 'record_count': 1},
    }


def _judgment():
    return {
        'judgment_id': 'judgment:test',
        'packet_id': 'packet:test',
        'packet_hash': 'sha256:' + 'a' * 64,
        'thesis_state': 'no_trade',
        'actionability': 'review',
        'confidence': 0.4,
        'evidence_refs': ['ev:1'],
        'why_now': ['typed evidence available'],
        'why_not': ['review only'],
        'invalidators': ['source correction'],
        'required_confirmations': ['价格/量能二次确认', '与现有暴露重叠度'],
        'thesis_refs': ['thesis:tsla'],
        'scenario_refs': [],
        'opportunity_candidate_refs': ['opp:xlb'],
        'invalidator_refs': ['inv:tsla'],
        'policy_version': 'test',
        'model_id': 'test-model',
    }


def _validation():
    return {'outcome': 'accepted_for_log', 'errors': []}


def _report():
    return build_report(
        _packet(),
        _judgment(),
        _validation(),
        report_mode='capital_delta',
        capital_graph={'graph_hash': 'sha256:test123'},
        capital_agenda={'agenda_items': [{
            'agenda_id': 'ag:1',
            'agenda_type': 'new_opportunity',
            'priority_score': 9.0,
            'linked_thesis_ids': ['thesis:tsla'],
            'attention_justification': 'new opportunity from uranium services chain',
            'required_questions': ['价格/量能二次确认', '与现有能源暴露的重叠程度'],
            'no_execution': True,
        }]},
        thesis_registry={'theses': [{'thesis_id': 'thesis:tsla', 'instrument': 'TSLA', 'status': 'active'}]},
        opportunity_queue={'candidates': [{'candidate_id': 'opp:xlb', 'instrument': 'XLB', 'status': 'candidate', 'score': 8.0, 'theme': 'materials dislocation'}]},
        invalidator_ledger={'invalidators': [{'invalidator_id': 'inv:tsla', 'description': 'price_vs_negative_upstream:TSLA', 'status': 'hit', 'hit_count': 3}]},
        option_risk={'data_status': 'stale_source', 'option_count': 0, 'exercise_assignment': {'status': 'unknown'}},
        displacement_cases={'cases': []},
    )


def test_discord_primary_fallbacks_to_markdown():
    report = _report()
    report['discord_primary_markdown'] = ''
    result = validate_report(report, _packet(), _judgment(), _validation())
    assert result['discord_primary_ok'] is True
    assert any(item['code'] == 'discord_primary_markdown_missing' for item in result['operator_warnings'])


def test_route_card_never_as_primary_delivery():
    report = _report()
    report['discord_primary_markdown'] = 'Finance｜Review\n值得看：x\n为什么现在：y\n你只要决定：z\n对象：T1=TSLA'
    result = validate_report(report, _packet(), _judgment(), _validation())
    assert any(item['code'] == 'route_card_only' for item in result['operator_errors'])


def test_primary_contains_object_translation():
    report = _report()
    assert 'A1 ' in report['discord_primary_markdown']
    assert 'T1 ' in report['discord_primary_markdown']
    assert report['object_alias_map']['A1'].startswith('新机会｜')


def test_primary_hides_machine_hashes_and_raw_ref_counts():
    report = _report()
    primary = report['discord_primary_markdown']
    assert 'packet_hash' not in primary
    assert 'graph_hash' not in primary
    assert 'model_id' not in primary
    assert 'thesis_refs=' not in primary


def test_thread_followup_uses_bundle_not_raw_thread_history():
    from finance_llm_context_pack import build_packs

    followup = build_packs()['report-followup']
    assert 'bundle is memory' in followup['rehydration_rule']
    assert 'thread_history_as_context' in followup['forbidden_actions']


def test_followup_guard_blocks_new_judgment_and_execution():
    from finance_followup_answer_guard import validate as validate_followup

    bundle = {'bundle_id': 'rb:RAAAA', 'handles': {'A1': {'type': 'agenda'}}}
    answer = {
        'report_ref': 'sha256:abc',
        'bundle_ref': 'rb:RAAAA',
        'selected_handle': 'A1',
        'verb': 'why',
        'answer_text': 'Fact\n- buy at market order\nInterpretation\n- x\nTo Verify\n- y\nWhat Would Change\n- z',
        'thesis_state_mutation': 'lean_long',
    }
    result = validate_followup(answer, bundle)
    assert result['status'] == 'fail'
    assert any('execution_language' in item for item in result['errors'])
    assert any('forbidden_key' in item for item in result['errors'])


def test_health_only_still_delivers_without_followup_router():
    from finance_report_delivery_safety import evaluate
    import json
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        safety = root / 'safety.json'
        judgment = root / 'judgment.json'
        judgment_validation = root / 'judgment-validation.json'
        product = root / 'product.json'
        decision_log = root / 'decision-log.json'
        report = root / 'report.json'
        safety.write_text(json.dumps({
            'delivery_mode': 'market_report_allowed',
            'market_report_allowed': True,
            'judgment_envelope_path': str(judgment),
            'judgment_validation_path': str(judgment_validation),
            'product_validation_path': str(product),
            'report_envelope_path': str(report),
            'decision_log_report_path': str(decision_log),
        }))
        judgment.write_text(json.dumps({
            'judgment_id': 'judgment:test',
            'packet_id': 'packet:test',
            'packet_hash': 'sha256:' + 'a' * 64,
            'instrument': 'TSLA',
            'thesis_state': 'watch',
            'actionability': 'review',
            'confidence': 0.4,
            'why_now': ['typed evidence available'],
            'why_not': ['review only'],
            'invalidators': ['source correction'],
            'required_confirmations': ['operator review'],
            'evidence_refs': ['ev:test'],
            'policy_version': 'finance-semantic-v1',
            'model_id': 'test-model',
        }))
        judgment_validation.write_text(json.dumps({'outcome': 'requires_operator_review', 'errors': []}))
        product.write_text(json.dumps({'status': 'pass', 'discord_primary_ok': True, 'thread_followup_ok': False}))
        report.write_text(json.dumps({'discord_primary_markdown': 'Finance｜资本议程\n\nFact\n- x\n\nInterpretation\n- y\n\nTo Verify\n- z\n\n对象\n- A1 test'}))
        decision_log.write_text(json.dumps({'status': 'pass', 'entry': {'decision_id': 'decision:test'}, 'append_result': {'status': 'pass'}}))
        result = evaluate(
            safety_path=safety,
            judgment_path=judgment,
            judgment_validation_path=judgment_validation,
            product_validation_path=product,
            decision_log_report_path=decision_log,
        )
        assert result['status'] == 'pass'
        assert result['discord_primary_ok'] is True
        assert result['thread_followup_ok'] is False
        assert 'thread_followup_not_ready' in result['warnings']


def test_core_report_requires_macro_triad_in_primary_and_artifact():
    report = _report()
    primary = report['discord_primary_markdown']
    artifact = report['markdown']
    for token in ['Macro triad', 'Gold', 'Bitcoin', 'SPX']:
        assert token in primary
    assert 'Core macro triad' in artifact


def test_validator_blocks_primary_without_macro_triad():
    report = _report()
    report['discord_primary_markdown'] = report['discord_primary_markdown'].replace('Macro triad', 'Macro removed').replace('Gold', 'Au').replace('Bitcoin', 'Crypto').replace('SPX', 'Index')
    result = validate_report(report, _packet(), _judgment(), _validation())
    assert any(item['code'] == 'primary_missing_macro_triad' for item in result['operator_errors'])


def test_options_iv_context_cannot_become_judgment_authority():
    report = _report()
    report['options_iv_surface_summary']['source_health_refs'] = ['ev:1']
    result = validate_report(report, _packet(), _judgment(), _validation())
    assert any(item['code'] == 'options_iv_refs_in_judgment_evidence' for item in result['options_iv_errors'])


def test_options_iv_context_rejects_raw_payload_retention():
    report = _report()
    report['options_iv_surface_summary']['raw_payload_retained'] = True
    result = validate_report(report, _packet(), _judgment(), _validation())
    assert any(item['code'] == 'options_iv_raw_payload_retained' for item in result['options_iv_errors'])
