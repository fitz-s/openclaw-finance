#!/usr/bin/env python3
"""Compile and append the live finance decision log entry."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


ROOT = Path('/Users/leofitz/.openclaw')
WORKSPACE = ROOT / 'workspace'
FINANCE = WORKSPACE / 'finance'
OPS_STATE = WORKSPACE / 'ops' / 'state'
DECISION_LOG_MODULE = WORKSPACE / 'decisions' / 'decision_log.py'
DEFAULT_LOG = WORKSPACE / 'decisions' / 'state' / 'finance-decision-log.jsonl'
DEFAULT_REPORT = FINANCE / 'state' / 'finance-decision-log-report.json'

PACKET = WORKSPACE / 'services' / 'market-ingest' / 'state' / 'latest-context-packet.json'
JUDGMENT = FINANCE / 'state' / 'judgment-envelope.json'
JUDGMENT_VALIDATION = FINANCE / 'state' / 'judgment-validation.json'
PRODUCT_REPORT = FINANCE / 'state' / 'finance-decision-report-envelope.json'
PRODUCT_VALIDATION = FINANCE / 'state' / 'finance-report-product-validation.json'
DELIVERY_SAFETY = FINANCE / 'state' / 'report-delivery-safety-check.json'
LIVE_REPORT = OPS_STATE / 'finance-native-premarket-brief-live-report.json'
GATE_STATE = FINANCE / 'state' / 'report-gate-state.json'
WAKE_DECISION = FINANCE / 'state' / 'latest-wake-decision.json'
WAKE_DISPATCH = FINANCE / 'state' / 'wake-dispatch-state.json'
ORCHESTRATOR_INPUT = FINANCE / 'state' / 'report-orchestrator-input.json'


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def stable_id(*parts: Any) -> str:
    material = '|'.join(str(part or '') for part in parts)
    return 'decision:' + hashlib.sha1(material.encode('utf-8')).hexdigest()[:20]


def hash_text(text: Any) -> str | None:
    value = str(text or '')
    if not value:
        return None
    return 'sha256:' + hashlib.sha256(value.encode('utf-8')).hexdigest()


def execution_decision(judgment: dict[str, Any], validation: dict[str, Any], product_validation: dict[str, Any], safety: dict[str, Any]) -> str:
    if validation.get('errors') or product_validation.get('status') != 'pass':
        return 'blocked'
    if safety.get('status') == 'pass' and judgment.get('actionability') in {'review', 'high'}:
        return 'review_only'
    if judgment.get('actionability') == 'none':
        return 'none'
    return 'blocked'


def operator_action(decision: str, live: dict[str, Any], safety: dict[str, Any]) -> str:
    if decision == 'none':
        return 'logged_no_trade'
    if decision == 'review_only':
        return 'operator_review_required'
    if live.get('delivered') is False or safety.get('status') == 'blocked':
        return 'blocked_by_safety_gate'
    return 'blocked'


def wake_threshold_attribution(
    *,
    gate: dict[str, Any],
    wake: dict[str, Any],
    dispatch: dict[str, Any],
    orchestrator_input: dict[str, Any],
) -> dict[str, Any]:
    bridge = gate.get('legacyThresholdDispatch') if isinstance(gate.get('legacyThresholdDispatch'), dict) else {}
    bridge_present = bool(bridge)
    wake_class = wake.get('wake_class') or dispatch.get('wake_class')
    dispatch_action = dispatch.get('action')
    report_class = orchestrator_input.get('report_class') if isinstance(orchestrator_input, dict) else None
    if dispatch.get('dispatched') is True and wake_class == 'ISOLATED_JUDGMENT_WAKE':
        attribution = 'canonical_wake_dispatch'
    elif bridge_present and bridge.get('dispatched') is True:
        attribution = 'legacy_threshold_bridge'
    elif report_class == 'ops_escalation':
        attribution = 'ops_escalation'
    elif report_class == 'scheduled_context':
        attribution = 'scheduled_context'
    elif wake_class == 'PACKET_UPDATE_ONLY':
        attribution = 'packet_update_only'
    elif gate.get('shouldSend') is False:
        attribution = 'hold_no_send'
    else:
        attribution = 'blocked_or_failed'
    return {
        'attribution': attribution,
        'gate_evaluated_at': gate.get('evaluatedAt'),
        'gate_should_send': gate.get('shouldSend'),
        'gate_recommended_report_type': gate.get('recommendedReportType'),
        'wake_class': wake_class,
        'wake_dispatch_action': dispatch_action,
        'wake_dispatched': dispatch.get('dispatched'),
        'legacy_threshold_bridge_present': bridge_present,
        'legacy_threshold_bridge_status': bridge.get('status') if bridge_present else None,
        'legacy_threshold_bridge_action': bridge.get('action') if bridge_present else None,
        'legacy_threshold_bridge_dispatched': bridge.get('dispatched') if bridge_present else None,
        'report_class': report_class,
    }


def compile_entry(
    *,
    packet: dict[str, Any],
    judgment: dict[str, Any],
    validation: dict[str, Any],
    product_report: dict[str, Any],
    product_validation: dict[str, Any],
    safety: dict[str, Any],
    live: dict[str, Any],
    gate: dict[str, Any] | None = None,
    wake: dict[str, Any] | None = None,
    dispatch: dict[str, Any] | None = None,
    orchestrator_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision = execution_decision(judgment, validation, product_validation, safety)
    return {
        'decision_id': stable_id(packet.get('packet_hash'), judgment.get('judgment_id'), product_report.get('report_hash'), safety.get('generated_at')),
        'created_at': now_iso(),
        'packet_id': packet.get('packet_id'),
        'packet_hash': packet.get('packet_hash'),
        'judgment_id': judgment.get('judgment_id'),
        'validator_result_id': validation.get('validator_result_id'),
        'execution_decision': decision,
        'operator_action': operator_action(decision, live, safety),
        'policy_version': judgment.get('policy_version') or packet.get('policy_version'),
        'session_ref': live.get('sessionKey') or live.get('session_ref') or 'finance-openclaw-runtime',
        'thesis_refs': judgment.get('thesis_refs') or packet.get('thesis_refs', []),
        'scenario_refs': judgment.get('scenario_refs') or packet.get('scenario_refs', []),
        'opportunity_candidate_refs': judgment.get('opportunity_candidate_refs') or packet.get('opportunity_candidate_refs', []),
        'invalidator_refs': judgment.get('invalidator_refs') or packet.get('invalidator_refs', []),
        'capital_agenda_refs': product_report.get('capital_agenda_refs') or [],
        'displacement_case_refs': product_report.get('displacement_case_refs') or [],
        'capital_graph_hash': product_report.get('capital_graph_hash'),
        'report_id': product_report.get('report_id'),
        'discord_primary_hash': hash_text(product_report.get('discord_primary_markdown')),
        'thread_seed_hash': hash_text(product_report.get('discord_thread_seed_markdown')),
        'followup_bundle_path': product_report.get('followup_bundle_path'),
        'starter_queries': product_report.get('starter_queries') or [],
        'object_alias_map': product_report.get('object_alias_map') or {},
        'wake_threshold_attribution': wake_threshold_attribution(
            gate=gate or {},
            wake=wake or {},
            dispatch=dispatch or {},
            orchestrator_input=orchestrator_input or {},
        ),
    }


def build_report(log_path: Path) -> dict[str, Any]:
    packet = load_json_safe(PACKET, {}) or {}
    judgment = load_json_safe(JUDGMENT, {}) or {}
    validation = load_json_safe(JUDGMENT_VALIDATION, {}) or {}
    product_report = load_json_safe(PRODUCT_REPORT, {}) or {}
    product_validation = load_json_safe(PRODUCT_VALIDATION, {}) or {}
    safety = load_json_safe(DELIVERY_SAFETY, {}) or {}
    live = load_json_safe(LIVE_REPORT, {}) or {}
    gate = load_json_safe(GATE_STATE, {}) or {}
    wake = load_json_safe(WAKE_DECISION, {}) or {}
    dispatch = load_json_safe(WAKE_DISPATCH, {}) or {}
    orchestrator_input = load_json_safe(ORCHESTRATOR_INPUT, {}) or {}
    entry = compile_entry(
        packet=packet,
        judgment=judgment,
        validation=validation,
        product_report=product_report,
        product_validation=product_validation,
        safety=safety,
        live=live,
        gate=gate,
        wake=wake,
        dispatch=dispatch,
        orchestrator_input=orchestrator_input,
    )
    decision_log = load_module(DECISION_LOG_MODULE, 'finance_decision_log_writer')
    if not decision_log.safe_log_path(log_path):
        result = {'status': 'blocked', 'errors': ['unsafe_log_path'], 'log_ref': str(log_path)}
    else:
        result = decision_log.append_decision(entry, log_path)
    return {
        'generated_at': now_iso(),
        'status': 'pass' if result.get('status') == 'pass' else 'fail',
        'entry': entry,
        'append_result': result,
        'refs': {
            'packet': str(PACKET),
            'judgment': str(JUDGMENT),
            'judgment_validation': str(JUDGMENT_VALIDATION),
            'product_report': str(PRODUCT_REPORT),
            'product_validation': str(PRODUCT_VALIDATION),
            'delivery_safety': str(DELIVERY_SAFETY),
            'live_report': str(LIVE_REPORT),
            'gate_state': str(GATE_STATE),
            'wake_decision': str(WAKE_DECISION),
            'wake_dispatch': str(WAKE_DISPATCH),
            'orchestrator_input': str(ORCHESTRATOR_INPUT),
            'decision_log': str(log_path),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', default=str(DEFAULT_LOG))
    parser.add_argument('--report', default=str(DEFAULT_REPORT))
    args = parser.parse_args(argv)
    log_path = Path(args.log)
    report_path = Path(args.report)
    if not report_path.is_absolute() or not str(report_path).startswith(str((FINANCE / 'state').resolve(strict=False))):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_report_path']}, ensure_ascii=False))
        return 2
    report = build_report(log_path)
    atomic_write_json(report_path, report)
    print(json.dumps({'status': report['status'], 'decision_id': report['entry'].get('decision_id'), 'execution_decision': report['entry'].get('execution_decision'), 'out': str(report_path)}, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
