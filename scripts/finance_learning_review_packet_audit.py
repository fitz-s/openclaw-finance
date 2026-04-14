#!/usr/bin/env python3
"""Audit the finance learning review packet has the live replay/decision chain."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
PACKET = FINANCE / 'state' / 'finance-learning-review-packet.json'
OUT = FINANCE / 'state' / 'finance-learning-review-packet-audit.json'

REQUIRED_INPUTS = [
    'canonical_context_packet_summary',
    'delivery_audit',
    'live_replay',
    'decision_log_report',
    'product_validation',
    'judgment_validation',
]


def audit_packet(packet: dict[str, Any]) -> dict[str, Any]:
    inputs = packet.get('inputs') if isinstance(packet.get('inputs'), dict) else {}
    checks = {
        'has_canonical_context_packet': isinstance(inputs.get('canonical_context_packet_summary'), dict) and bool(inputs.get('canonical_context_packet_summary', {}).get('packet_hash')),
        'has_delivery_audit': isinstance(inputs.get('delivery_audit'), dict) and bool(inputs.get('delivery_audit')),
        'has_live_replay': isinstance(inputs.get('live_replay'), dict) and bool(inputs.get('live_replay')),
        'has_decision_log_report': isinstance(inputs.get('decision_log_report'), dict) and bool(inputs.get('decision_log_report')),
        'has_product_validation': isinstance(inputs.get('product_validation'), dict) and bool(inputs.get('product_validation')),
        'has_judgment_validation': isinstance(inputs.get('judgment_validation'), dict) and bool(inputs.get('judgment_validation')),
        'delivery_audit_pass': inputs.get('delivery_audit', {}).get('status') == 'pass',
        'live_replay_pass': inputs.get('live_replay', {}).get('status') == 'pass',
        'live_replay_no_semantic_drift': inputs.get('live_replay', {}).get('semantic_diff_count') == 0,
        'live_replay_no_invariant_drift': inputs.get('live_replay', {}).get('invariant_diff_count') == 0,
        'decision_log_pass': inputs.get('decision_log_report', {}).get('status') == 'pass',
        'product_validation_pass': inputs.get('product_validation', {}).get('status') == 'pass',
        'judgment_validation_clean': (
            inputs.get('judgment_validation', {}).get('outcome') in {'accepted_for_log', 'requires_operator_review'}
            and not inputs.get('judgment_validation', {}).get('errors')
        ),
        'review_only_contract': packet.get('review_contract', {}).get('mode') == 'review_only',
        'no_auto_threshold_mutation': 'automatic_threshold_mutation' in packet.get('review_contract', {}).get('forbidden_actions', []),
    }
    return {
        'status': 'pass' if all(checks.values()) else 'fail',
        'checks': checks,
        'blocking_reasons': [name for name, ok in checks.items() if not ok],
        'input_keys': sorted(inputs.keys()),
        'live_replay': {
            'status': inputs.get('live_replay', {}).get('status'),
            'semantic_diff_count': inputs.get('live_replay', {}).get('semantic_diff_count'),
            'invariant_diff_count': inputs.get('live_replay', {}).get('invariant_diff_count'),
        },
        'delivery_audit_status': inputs.get('delivery_audit', {}).get('status'),
        'decision_log_status': inputs.get('decision_log_report', {}).get('status'),
        'product_validation_status': inputs.get('product_validation', {}).get('status'),
        'judgment_validation_outcome': inputs.get('judgment_validation', {}).get('outcome'),
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        'Finance｜Learning Replay Gate',
        '',
        '## 状态',
        f"- audit status: `{report.get('status')}`",
        f"- semantic_diff_count: {report.get('live_replay', {}).get('semantic_diff_count')}",
        f"- invariant_diff_count: {report.get('live_replay', {}).get('invariant_diff_count')}",
        '',
        '## 输入闭环',
    ]
    for key in REQUIRED_INPUTS:
        lines.append(f"- `{key}`: {'present' if key in report.get('input_keys', []) else 'missing'}")
    lines.extend([
        '',
        '## 当前动作',
        '- review-only learning gate；不调整 thresholds；不输出市场建议；不执行交易。',
    ])
    if report.get('blocking_reasons'):
        lines.extend(['', '## Blocking', *[f"- {item}" for item in report['blocking_reasons']]])
    return '\n'.join(lines) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', default=str(PACKET))
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--markdown', action='store_true')
    args = parser.parse_args(argv)
    packet = load_json_safe(Path(args.packet), {}) or {}
    report = audit_packet(packet)
    atomic_write_json(Path(args.out), report)
    if args.markdown:
        print(markdown(report))
    else:
        print(json.dumps({'status': report['status'], 'blocking_reasons': report['blocking_reasons'], 'out': str(args.out)}, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
