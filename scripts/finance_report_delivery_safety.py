#!/usr/bin/env python3
"""Fail-closed safety gate for user-visible finance market reports."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe

WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'

SAFETY_STATE = FINANCE / 'state' / 'report-delivery-safety.json'
JUDGMENT_ENVELOPE = FINANCE / 'state' / 'judgment-envelope.json'
PRODUCT_VALIDATION = FINANCE / 'state' / 'finance-report-product-validation.json'
JUDGMENT_VALIDATION = FINANCE / 'state' / 'judgment-validation.json'
DECISION_LOG_REPORT = FINANCE / 'state' / 'finance-decision-log-report.json'
OUT = FINANCE / 'state' / 'report-delivery-safety-check.json'

MARKET_REPORT_ALLOWED = 'market_report_allowed'
HEALTH_ONLY = 'health_only'
NO_DELIVERY_SMOKE_ONLY = 'no_delivery_smoke_only'
ALLOWED_MODES = {MARKET_REPORT_ALLOWED, HEALTH_ONLY, NO_DELIVERY_SMOKE_ONLY}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_safety_state() -> dict[str, Any]:
    return {
        'generated_at': now_iso(),
        'status': 'active',
        'delivery_mode': HEALTH_ONLY,
        'market_report_allowed': False,
        'reason': 'Packet -1 safety containment is active until JudgmentEnvelope and product-quality validation are live.',
        'required_before_market_report': [
            'judgment_envelope_pass',
            'product_quality_validation_pass',
        ],
        'judgment_envelope_path': str(JUDGMENT_ENVELOPE),
        'judgment_validation_path': str(JUDGMENT_VALIDATION),
        'product_validation_path': str(PRODUCT_VALIDATION),
        'decision_log_report_path': str(DECISION_LOG_REPORT),
    }


def ensure_state(path: Path = SAFETY_STATE) -> dict[str, Any]:
    state = load_json_safe(path, None)
    if isinstance(state, dict) and state:
        return state
    state = default_safety_state()
    atomic_write_json(path, state)
    return state


def _basic_judgment_ok(payload: dict[str, Any]) -> bool:
    required = [
        'judgment_id',
        'packet_id',
        'packet_hash',
        'instrument',
        'thesis_state',
        'actionability',
        'confidence',
        'why_now',
        'why_not',
        'invalidators',
        'required_confirmations',
        'evidence_refs',
        'policy_version',
        'model_id',
    ]
    if not all(key in payload for key in required):
        return False
    return (
        isinstance(payload.get('evidence_refs'), list)
        and bool(payload.get('evidence_refs'))
        and str(payload.get('packet_hash') or '').startswith('sha256:')
    )


def evaluate(
    *,
    safety_path: Path = SAFETY_STATE,
    judgment_path: Path | None = None,
    judgment_validation_path: Path | None = None,
    product_validation_path: Path | None = None,
    decision_log_report_path: Path | None = None,
) -> dict[str, Any]:
    state = ensure_state(safety_path)
    mode = str(state.get('delivery_mode') or '')
    blockers: list[str] = []
    warnings: list[str] = []

    if mode not in ALLOWED_MODES:
        blockers.append('invalid_delivery_safety_mode')
    if state.get('market_report_allowed') is not True:
        blockers.append('market_report_safety_containment_active')
    if mode != MARKET_REPORT_ALLOWED:
        blockers.append(f'delivery_mode:{mode or "missing"}')

    judgment_ref = judgment_path or Path(str(state.get('judgment_envelope_path') or JUDGMENT_ENVELOPE))
    judgment_validation_ref = judgment_validation_path or Path(str(state.get('judgment_validation_path') or JUDGMENT_VALIDATION))
    product_ref = product_validation_path or Path(str(state.get('product_validation_path') or PRODUCT_VALIDATION))
    decision_log_ref = decision_log_report_path or Path(str(state.get('decision_log_report_path') or DECISION_LOG_REPORT))

    judgment = load_json_safe(judgment_ref, {}) or {}
    judgment_validation = load_json_safe(judgment_validation_ref, {}) or {}
    product = load_json_safe(product_ref, {}) or {}
    decision_log = load_json_safe(decision_log_ref, {}) or {}
    judgment_ok = _basic_judgment_ok(judgment)
    judgment_validation_ok = (
        isinstance(judgment_validation, dict)
        and judgment_validation.get('outcome') in {'accepted_for_log', 'requires_operator_review'}
        and not judgment_validation.get('errors')
    )
    product_ok = product.get('status') == 'pass'
    decision_log_ok = (
        isinstance(decision_log, dict)
        and decision_log.get('status') == 'pass'
        and isinstance(decision_log.get('entry'), dict)
        and decision_log.get('append_result', {}).get('status') == 'pass'
    )

    if not judgment_ok:
        blockers.append('judgment_envelope_missing_or_invalid')
    if not judgment_validation_ok:
        blockers.append('judgment_validation_not_pass')
    if not product_ok:
        blockers.append('product_quality_validation_not_pass')
    if not decision_log_ok:
        blockers.append('decision_log_not_pass')

    report = {
        'generated_at': now_iso(),
        'status': 'pass' if not blockers else 'blocked',
        'delivery_mode': mode or None,
        'market_report_allowed': not blockers,
        'blocking_reasons': sorted(set(blockers)),
        'warnings': warnings,
        'safety_state_path': str(safety_path),
        'judgment_envelope_path': str(judgment_ref),
        'judgment_validation_path': str(judgment_validation_ref),
        'product_validation_path': str(product_ref),
        'decision_log_report_path': str(decision_log_ref),
        'judgment_envelope_ok': judgment_ok,
        'judgment_validation_ok': judgment_validation_ok,
        'product_quality_validation_ok': product_ok,
        'decision_log_ok': decision_log_ok,
    }
    return report


def health_only_markdown(report: dict[str, Any]) -> str:
    reasons = ', '.join(report.get('blocking_reasons') or ['safety_containment_active'])
    return '\n'.join([
        'Finance｜系统状态',
        '',
        '## 状态',
        'finance market report delivery 处于 safety containment。',
        '',
        '## 原因',
        f'- {reasons}',
        '',
        '## 当前动作',
        '- 不输出市场判断。',
        '- 不输出交易建议。',
        '- 等待 JudgmentEnvelope 与 product-quality validator 接入后恢复 market report。',
        '',
        '## 机器证据',
        f'- safety_state: {report.get("safety_state_path")}',
        f'- judgment_envelope_ok: {report.get("judgment_envelope_ok")}',
        f'- judgment_validation_ok: {report.get("judgment_validation_ok")}',
        f'- product_quality_validation_ok: {report.get("product_quality_validation_ok")}',
        f'- decision_log_ok: {report.get("decision_log_ok")}',
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Evaluate finance market-report delivery safety.')
    parser.add_argument('--safety-state', default=str(SAFETY_STATE))
    parser.add_argument('--judgment-envelope', default=None)
    parser.add_argument('--judgment-validation', default=None)
    parser.add_argument('--product-validation', default=None)
    parser.add_argument('--decision-log-report', default=None)
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--write-default', action='store_true')
    parser.add_argument('--health-markdown', action='store_true')
    args = parser.parse_args(argv)

    safety_path = Path(args.safety_state)
    if args.write_default:
        state = default_safety_state()
        atomic_write_json(safety_path, state)

    report = evaluate(
        safety_path=safety_path,
        judgment_path=Path(args.judgment_envelope) if args.judgment_envelope else None,
        judgment_validation_path=Path(args.judgment_validation) if args.judgment_validation else None,
        product_validation_path=Path(args.product_validation) if args.product_validation else None,
        decision_log_report_path=Path(args.decision_log_report) if args.decision_log_report else None,
    )
    out = Path(args.out)
    atomic_write_json(out, report)
    if args.health_markdown:
        print(health_only_markdown(report))
    else:
        print(json.dumps({'status': report['status'], 'blocking_reasons': report['blocking_reasons'], 'out': str(out)}, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 2


if __name__ == '__main__':
    raise SystemExit(main())
