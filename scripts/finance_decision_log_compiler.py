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


def compile_entry(
    *,
    packet: dict[str, Any],
    judgment: dict[str, Any],
    validation: dict[str, Any],
    product_report: dict[str, Any],
    product_validation: dict[str, Any],
    safety: dict[str, Any],
    live: dict[str, Any],
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
    }


def build_report(log_path: Path) -> dict[str, Any]:
    packet = load_json_safe(PACKET, {}) or {}
    judgment = load_json_safe(JUDGMENT, {}) or {}
    validation = load_json_safe(JUDGMENT_VALIDATION, {}) or {}
    product_report = load_json_safe(PRODUCT_REPORT, {}) or {}
    product_validation = load_json_safe(PRODUCT_VALIDATION, {}) or {}
    safety = load_json_safe(DELIVERY_SAFETY, {}) or {}
    live = load_json_safe(LIVE_REPORT, {}) or {}
    entry = compile_entry(
        packet=packet,
        judgment=judgment,
        validation=validation,
        product_report=product_report,
        product_validation=product_validation,
        safety=safety,
        live=live,
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
