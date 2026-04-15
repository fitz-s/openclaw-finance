#!/usr/bin/env python3
"""Persist review-only thesis outcome rows from decision logs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from atomic_io import load_json_safe
from thesis_spine_util import FINANCE, now_iso
from wake_attribution_logger import append_unique, latest_decision_entry


THESIS_REGISTRY = FINANCE / 'state' / 'thesis-registry.json'
DECISION_LOG = FINANCE / 'state' / 'finance-decision-log-report.json'
PRODUCT_VALIDATION = FINANCE / 'state' / 'finance-report-product-validation.json'
OUT = FINANCE / 'state' / 'thesis-outcomes.jsonl'


def event_id(decision_id: str | None, thesis_id: str | None) -> str:
    raw = f'{decision_id or ""}|{thesis_id or ""}'
    return 'thesis-outcome:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def thesis_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        item.get('thesis_id'): item
        for item in registry.get('theses', [])
        if isinstance(item, dict) and item.get('thesis_id')
    }


def build_rows(registry: dict[str, Any], decision_log: dict[str, Any], product_validation: dict[str, Any]) -> list[dict[str, Any]]:
    entry = latest_decision_entry(decision_log)
    theses = thesis_map(registry)
    refs = entry.get('thesis_refs') if isinstance(entry.get('thesis_refs'), list) else []
    rows = []
    for thesis_id in refs:
        thesis = theses.get(thesis_id, {})
        rows.append({
            'event_id': event_id(entry.get('decision_id'), thesis_id),
            'logged_at': now_iso(),
            'thesis_id': thesis_id,
            'instrument': thesis.get('instrument'),
            'thesis_status': thesis.get('status'),
            'thesis_maturity': thesis.get('maturity'),
            'decision_id': entry.get('decision_id'),
            'execution_decision': entry.get('execution_decision'),
            'operator_action': entry.get('operator_action'),
            'product_validation_status': product_validation.get('status'),
            'outcome_scope': 'review_only_decision_support',
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--thesis-registry', default=str(THESIS_REGISTRY))
    parser.add_argument('--decision-log', default=str(DECISION_LOG))
    parser.add_argument('--product-validation', default=str(PRODUCT_VALIDATION))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    rows = build_rows(
        load_json_safe(Path(args.thesis_registry), {}) or {},
        load_json_safe(Path(args.decision_log), {}) or {},
        load_json_safe(Path(args.product_validation), {}) or {},
    )
    appended = 0
    for row in rows:
        if append_unique(Path(args.out), row):
            appended += 1
    print(json.dumps({'status': 'pass', 'row_count': len(rows), 'appended': appended, 'out': str(args.out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
