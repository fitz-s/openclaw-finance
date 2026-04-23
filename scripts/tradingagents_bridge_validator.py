#!/usr/bin/env python3
"""Validate TradingAgents normalized artifacts before surface publication."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tradingagents_bridge_types import (
    CHINESE_EXECUTION_PATTERNS,
    ENGLISH_EXECUTION_PATTERNS,
    SECRET_PATTERNS,
    age_hours,
    load_json,
    matches_any,
    now_iso,
    write_json,
)


def _validate_texts(payload: dict[str, Any], keys: list[str]) -> list[str]:
    errors: list[str] = []
    for key in keys:
        value = payload.get(key)
        rows = value if isinstance(value, list) else [value]
        for row in rows:
            text = str(row or '')
            lower = text.lower()
            if matches_any(lower, ENGLISH_EXECUTION_PATTERNS):
                errors.append(f'execution_language_detected:{key}')
                break
            if matches_any(text, CHINESE_EXECUTION_PATTERNS):
                errors.append(f'execution_language_detected:{key}')
                break
            if matches_any(text, SECRET_PATTERNS):
                errors.append(f'secret_or_account_leak:{key}')
                break
    return errors


def validate_advisory(advisory: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if advisory.get('execution_readiness') != 'disabled':
        errors.append('execution_readiness_must_be_disabled')
    if advisory.get('review_only') is not True:
        errors.append('review_only_missing')
    if advisory.get('no_execution') is not True:
        errors.append('no_execution_missing')
    errors.extend(_validate_texts(advisory, [
        'summary_title_safe',
        'why_now_safe',
        'why_not_now_safe',
        'invalidators_safe',
        'required_confirmations_safe',
        'source_gaps_safe',
        'risk_flags_safe',
    ]))
    if advisory.get('hypothetical_rating') and advisory.get('hypothetical_rating') not in {'BUY', 'OVERWEIGHT', 'HOLD', 'UNDERWEIGHT', 'SELL'}:
        warnings.append('unexpected_hypothetical_rating')

    report_hash = ((request.get('source_bindings') or {}).get('report_envelope') or {}).get('report_hash')
    packet_hash = ((request.get('source_bindings') or {}).get('context_packet') or {}).get('packet_hash')
    generated_at = advisory.get('generated_at')
    context_max_age = ((request.get('surface_policy') or {}).get('context_digest_max_age_hours') or 24)
    reader_max_age = ((request.get('surface_policy') or {}).get('reader_augmentation_max_age_hours') or 72)

    return {
        'generated_at': now_iso(),
        'status': 'pass' if not errors else 'fail',
        'errors': sorted(set(errors)),
        'warnings': sorted(set(warnings)),
        'surface_eligible': not errors,
        'context_pack_eligible': not errors and bool(packet_hash or report_hash),
        'reader_eligible': not errors and bool(report_hash),
        'report_hash': report_hash,
        'packet_hash': packet_hash,
        'age_hours': age_hours(str(generated_at) if generated_at else None),
        'context_digest_max_age_hours': context_max_age,
        'reader_augmentation_max_age_hours': reader_max_age,
        'review_only': True,
        'no_execution': True,
    }


def validate_run(run_root: Path) -> dict[str, Any]:
    advisory = load_json(run_root / 'normalized' / 'advisory-decision.json', {}) or {}
    request = load_json(run_root / 'request.json', {}) or {}
    report = validate_advisory(advisory, request)
    write_json(run_root / 'validation.json', report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Validate TradingAgents advisory artifacts.')
    parser.add_argument('--run-root', required=True)
    args = parser.parse_args(argv)
    report = validate_run(Path(args.run_root))
    print(json.dumps({'status': report['status'], 'errors': report['errors'], 'out': str(Path(args.run_root) / 'validation.json')}, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
