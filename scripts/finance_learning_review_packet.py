#!/usr/bin/env python3
"""Compile compact inputs for the OpenClaw finance weekly learning reviewer."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe

WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
OPS = WORKSPACE / 'ops'
OPENCLAW = Path('/Users/leofitz/.openclaw')

SIGNAL_WEIGHTS = FINANCE / 'state' / 'signal-weights.json'
CALIBRATION_ANCHORS = FINANCE / 'state' / 'calibration-anchors.json'
CONTEXT_PACKET = WORKSPACE / 'services' / 'market-ingest' / 'state' / 'latest-context-packet.json'
REPORT_PACKET_VIEW = FINANCE / 'state' / 'report-input-packet.json'
DELIVERY_AUDIT = OPS / 'state' / 'finance-report-delivery-audit.json'
LIVE_REPLAY = WORKSPACE / 'replay' / 'state' / 'live-finance-replay-report.json'
DECISION_LOG_REPORT = FINANCE / 'state' / 'finance-decision-log-report.json'
PRODUCT_VALIDATION = FINANCE / 'state' / 'finance-report-product-validation.json'
JUDGMENT_VALIDATION = FINANCE / 'state' / 'judgment-validation.json'
LEARNING_PACKET = FINANCE / 'state' / 'finance-learning-review-packet.json'
RUNS_DIR = OPENCLAW / 'cron' / 'runs'

FINANCE_JOB_IDS = {
    'finance-subagent-scanner': 'c031f32c-0392-45bb-ae1a-ad7e7aec6938',
    'finance-subagent-scanner-offhours': 'f57c165f-7683-4816-ab2c-10abda099b9f',
    'finance-premarket-brief': 'b2c3d4e5-f6a7-8901-bcde-f01234567890',
}


def tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines()[-limit * 3:]:
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows[-limit:]


def compact_runs(limit: int) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for name, job_id in FINANCE_JOB_IDS.items():
        rows = []
        for row in tail_jsonl(RUNS_DIR / f'{job_id}.jsonl', limit):
            rows.append({
                'ts': row.get('ts'),
                'status': row.get('status'),
                'durationMs': row.get('durationMs'),
                'model': row.get('model'),
                'provider': row.get('provider'),
                'delivered': row.get('delivered'),
                'deliveryStatus': row.get('deliveryStatus'),
                'summary': str(row.get('summary') or row.get('error') or '')[:1200],
            })
        out[name] = rows
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compile finance learning review packet.')
    parser.add_argument('--out', default=str(LEARNING_PACKET))
    parser.add_argument('--run-limit', type=int, default=5)
    args = parser.parse_args(argv)
    packet = {
        'packet_version': 'finance-learning-review-v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'inputs': {
            'signal_weights': load_json_safe(SIGNAL_WEIGHTS, {}) or {},
            'calibration_anchors': load_json_safe(CALIBRATION_ANCHORS, {}) or {},
            'canonical_context_packet_summary': {
                key: value for key, value in (load_json_safe(CONTEXT_PACKET, {}) or {}).items()
                if key in ['packet_id', 'packet_hash', 'instrument', 'generated_at', 'source_manifest', 'candidate_invalidators']
            },
            'compat_report_input_packet_summary': {
                key: value for key, value in (load_json_safe(REPORT_PACKET_VIEW, {}) or {}).items()
                if key in ['report_policy_version', 'packet_hash', 'unavailable_facts', 'data_quality']
            },
            'delivery_audit': load_json_safe(DELIVERY_AUDIT, {}) or {},
            'judgment_validation': load_json_safe(JUDGMENT_VALIDATION, {}) or {},
            'product_validation': load_json_safe(PRODUCT_VALIDATION, {}) or {},
            'decision_log_report': load_json_safe(DECISION_LOG_REPORT, {}) or {},
            'live_replay': load_json_safe(LIVE_REPLAY, {}) or {},
            'cron_runs': compact_runs(args.run_limit),
        },
        'review_contract': {
            'mode': 'review_only',
            'must_distinguish': ['Fact', 'Interpretation', 'Recommendation'],
            'allowed_recommendation_targets': ['policy', 'schema', 'tests', 'prompt', 'model_routing'],
            'forbidden_actions': ['automatic_threshold_mutation', 'trade_execution', 'raw_flex_memory_write'],
        },
    }
    atomic_write_json(Path(args.out), packet)
    print(json.dumps({
        'status': 'pass',
        'out': str(args.out),
        'run_groups': len(packet['inputs']['cron_runs']),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
