#!/usr/bin/env python3
"""Persist wake-vs-threshold attribution rows for finance reports."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from atomic_io import load_json_safe
from thesis_spine_util import FINANCE, now_iso


GATE = FINANCE / 'state' / 'report-gate-state.json'
WAKE = FINANCE / 'state' / 'latest-wake-decision.json'
DISPATCH = FINANCE / 'state' / 'wake-dispatch-state.json'
DECISION_LOG = FINANCE / 'state' / 'finance-decision-log-report.json'
OUT = FINANCE / 'state' / 'dispatch-attribution.jsonl'


def stable_event_id(*parts: Any) -> str:
    raw = '|'.join(str(part or '') for part in parts)
    return 'wake-attribution:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def latest_decision_entry(report: dict[str, Any]) -> dict[str, Any]:
    if isinstance(report.get('entry'), dict):
        return report['entry']
    rows = report.get('entries') or report.get('decisions')
    if isinstance(rows, list) and rows:
        return rows[-1] if isinstance(rows[-1], dict) else {}
    return report if isinstance(report, dict) else {}


def build_row(gate: dict[str, Any], wake: dict[str, Any], dispatch: dict[str, Any], decision_log: dict[str, Any]) -> dict[str, Any]:
    entry = latest_decision_entry(decision_log)
    event_id = stable_event_id(
        gate.get('evaluatedAt'),
        wake.get('packet_id'),
        wake.get('wake_class'),
        entry.get('decision_id'),
    )
    return {
        'event_id': event_id,
        'logged_at': now_iso(),
        'gate_evaluated_at': gate.get('evaluatedAt'),
        'window': gate.get('window'),
        'data_stale': gate.get('dataStale'),
        'threshold_should_send': gate.get('shouldSend'),
        'threshold_report_type': gate.get('recommendedReportType'),
        'wake_class': wake.get('wake_class'),
        'wake_reason': wake.get('wake_reason'),
        'wake_score': (wake.get('score_inputs') or {}).get('wake_score') if isinstance(wake.get('score_inputs'), dict) else None,
        'dispatch_action': dispatch.get('action'),
        'dispatch_status': dispatch.get('status'),
        'decision_id': entry.get('decision_id'),
        'execution_decision': entry.get('execution_decision'),
        'operator_action': entry.get('operator_action'),
        'thesis_refs': entry.get('thesis_refs', []),
        'opportunity_candidate_refs': entry.get('opportunity_candidate_refs', []),
    }


def append_unique(path: Path, row: dict[str, Any]) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    seen = set()
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
                if payload.get('event_id'):
                    seen.add(payload['event_id'])
    if row.get('event_id') in seen:
        return False
    rows.append(row)
    tmp = path.with_name(f'{path.name}.tmp')
    tmp.write_text(''.join(json.dumps(item, ensure_ascii=False) + '\n' for item in rows), encoding='utf-8')
    tmp.replace(path)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--gate', default=str(GATE))
    parser.add_argument('--wake', default=str(WAKE))
    parser.add_argument('--dispatch', default=str(DISPATCH))
    parser.add_argument('--decision-log', default=str(DECISION_LOG))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    row = build_row(
        load_json_safe(Path(args.gate), {}) or {},
        load_json_safe(Path(args.wake), {}) or {},
        load_json_safe(Path(args.dispatch), {}) or {},
        load_json_safe(Path(args.decision_log), {}) or {},
    )
    appended = append_unique(Path(args.out), row)
    print(json.dumps({'status': 'pass', 'appended': appended, 'event_id': row['event_id'], 'out': str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
