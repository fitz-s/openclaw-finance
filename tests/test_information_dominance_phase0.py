from __future__ import annotations

import json
from pathlib import Path


ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
PLAN = ROOT / 'docs' / 'openclaw-runtime' / 'information-dominance-stack-plan.md'
MAP = ROOT / 'docs' / 'openclaw-runtime' / 'information-dominance-stack-map.json'


def _map() -> dict:
    return json.loads(MAP.read_text(encoding='utf-8'))


def test_phase0_plan_and_map_exist_and_name_target_stack() -> None:
    plan = PLAN.read_text(encoding='utf-8')
    payload = _map()

    assert 'Source-to-Campaign Intelligence Fabric' in plan
    assert 'RALPLAN Gate Protocol' in plan
    assert payload['subtitle'] == 'Source-to-Campaign Intelligence Fabric'
    assert payload['current_phase'] == 'phase_0'
    assert payload['phase_0_status'] == 'prepared'


def test_phase0_does_not_authorize_active_runtime_cutover() -> None:
    payload = _map()
    switches = payload['runtime_switch_defaults']

    assert payload['active_runtime_cutover'] is False
    assert payload['review_only'] is True
    assert payload['no_execution_authority_change'] is True
    assert switches['DISCORD_BOARDS_ENABLED'] is False
    assert switches['DISCORD_THREADS_ENABLED'] is False
    assert switches['FOLLOWUP_ROUTER_ENABLED'] is False
    assert switches['SOURCE_ATOM_ACTIVE_MODE'] is False
    assert switches['CLAIM_GRAPH_ACTIVE_MODE'] is False
    assert switches['CONTEXT_GAP_ACTIVE_MODE'] is False


def test_authority_chain_preserves_existing_report_safety_order() -> None:
    payload = _map()
    chain = payload['authority_chain']

    expected_order = [
        'ContextPacket',
        'WakeDecision',
        'JudgmentEnvelope',
        'finance-decision-report-envelope.json',
        'finance_report_product_validator.py',
        'finance_decision_log_compiler.py',
        'finance_report_delivery_safety.py',
        'OpenClaw Discord delivery',
    ]
    positions = [chain.index(item) for item in expected_order]
    assert positions == sorted(positions)


def test_every_post_phase0_phase_requires_ralplan_before_implementation() -> None:
    payload = _map()
    phases = payload['phases']
    phase0 = next(phase for phase in phases if phase['id'] == 'phase_0')
    later = [phase for phase in phases if phase['id'] != 'phase_0']

    assert phase0['ralplan_required_before_start'] is False
    assert later
    assert all(phase['ralplan_required_before_start'] is True for phase in later)
    assert all(phase['status'].startswith('blocked_until') for phase in later)
    assert payload['ralplan_gate']['required_after_phase_0'] is True
    assert 'Explicit go/no-go for implementation' in payload['ralplan_gate']['required_sections']


def test_pre_cutover_phases_are_shadow_first() -> None:
    payload = _map()
    phases = {phase['id']: phase for phase in payload['phases']}

    for phase_id in ['phase_1', 'phase_2', 'phase_3', 'phase_4', 'phase_5', 'phase_6', 'phase_7']:
        assert phases[phase_id]['shadow_mode_default'] is True
        assert phases[phase_id]['active_mode_default'] is False

    assert phases['phase_8']['deliberate_ralplan_required'] is True
    assert phases['phase_8']['active_mode_default'] is False


def test_rollback_floor_forbids_route_card_only_primary() -> None:
    payload = _map()
    rollback = payload['rollback_floor']

    assert rollback['fallback_primary'] == 'discord_primary_markdown_or_full_markdown'
    assert rollback['forbidden_fallback'] == 'route_card_only_primary'
    assert 'DISCORD_BOARDS_ENABLED' in rollback['disable_switches']
    assert 'FOLLOWUP_ROUTER_ENABLED' in rollback['disable_switches']
