#!/usr/bin/env python3
"""Post-hoc validator for finance follow-up answers in the review room."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
OUT = FINANCE / 'state' / 'followup-answer-validation.json'

VALID_VERBS = {'why', 'challenge', 'compare', 'scenario', 'sources', 'expand', 'trace', 'open'}

REQUIRED_SECTIONS = {
    'Fact', 'Interpretation', 'Unknown', 'What Would Change',
}

EXECUTION_PATTERNS = [
    r'\b(buy|sell|execute|place order|market order|limit order|stop loss)\b',
    r'\blive_authority\s*[=:]\s*true\b',
    r'\bexecution_adapter\b',
]

FORBIDDEN_KEYS = {
    'thesis_state_mutation', 'actionability_change', 'live_authority',
    'trade_recommendation', 'position_size',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def validate_binding(answer: dict[str, Any], bundle: dict[str, Any]) -> list[str]:
    """Check answer binds to valid report + bundle + handle."""
    errors: list[str] = []

    report_id = answer.get('report_ref')
    bundle_id = answer.get('bundle_ref')
    handle = answer.get('selected_handle')

    if not report_id:
        errors.append('missing_report_ref')
    if not bundle_id:
        errors.append('missing_bundle_ref')
    if bundle and bundle_id and bundle.get('bundle_id') != bundle_id:
        errors.append('bundle_id_mismatch')

    handles = bundle.get('handles', {}) if isinstance(bundle.get('handles'), dict) else {}
    if handle and handle not in handles:
        errors.append(f'handle_not_in_bundle:{handle}')
    if not handle:
        errors.append('missing_selected_handle')

    return errors


def validate_verb(answer: dict[str, Any]) -> list[str]:
    """Check interrogation verb is valid."""
    verb = answer.get('verb')
    if not verb:
        return ['missing_verb']
    if verb not in VALID_VERBS:
        return [f'invalid_verb:{verb}']
    return []


def validate_evidence_slice(answer: dict[str, Any]) -> list[str]:
    if answer.get('verb') == 'open':
        return []
    if not answer.get('evidence_slice_id'):
        return ['missing_evidence_slice_id']
    coverage = answer.get('evidence_slice_coverage')
    if isinstance(coverage, dict):
        missing = coverage.get('missing_fields')
        has_missing = isinstance(missing, list) and bool(missing)
        status = str(answer.get('answer_status') or '').lower()
        text = str(answer.get('answer_text') or answer.get('text') or '').lower()
        if has_missing and status != 'insufficient_data' and 'insufficient_data' not in text:
            return ['answered_with_missing_required_evidence']
    return []


def validate_review_only(answer_text: str) -> list[str]:
    """Check answer does not contain execution language."""
    errors: list[str] = []
    lower = answer_text.lower()
    for pattern in EXECUTION_PATTERNS:
        if re.search(pattern, lower):
            errors.append(f'execution_language_detected:{pattern}')

    return errors


def validate_structure(answer_text: str) -> list[str]:
    """Check answer follows Fact/Interpretation/Unknown/What Would Change structure."""
    warnings: list[str] = []
    if 'insufficient_data' in answer_text.lower():
        return warnings
    for section in REQUIRED_SECTIONS:
        # Check for section header presence (flexible matching)
        if section.lower() not in answer_text.lower() and section.replace(' ', '').lower() not in answer_text.lower():
            warnings.append(f'missing_section:{section}')
    if 'to verify' not in answer_text.lower() and 'unknown' not in answer_text.lower():
        warnings.append('missing_section:To Verify')
    return warnings


def validate_forbidden_keys(answer: dict[str, Any]) -> list[str]:
    """Check answer does not smuggle forbidden state mutations."""
    errors: list[str] = []
    for key in FORBIDDEN_KEYS:
        if key in answer:
            errors.append(f'forbidden_key:{key}')
    return errors


def validate(
    answer: dict[str, Any],
    bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a follow-up answer against the followup-answer-contract."""
    answer_text = str(answer.get('answer_text') or answer.get('text') or '')
    all_errors: list[str] = []
    all_warnings: list[str] = []

    all_errors.extend(validate_binding(answer, bundle or {}))
    all_errors.extend(validate_verb(answer))
    all_errors.extend(validate_evidence_slice(answer))
    all_errors.extend(validate_review_only(answer_text))
    all_errors.extend(validate_forbidden_keys(answer))

    # Structure check is a warning, not a hard error
    structure_issues = validate_structure(answer_text)
    all_warnings.extend(structure_issues)

    return {
        'generated_at': now_iso(),
        'status': 'pass' if not all_errors else 'fail',
        'errors': sorted(set(all_errors)),
        'warnings': sorted(set(all_warnings)),
        'report_ref': answer.get('report_ref'),
        'bundle_ref': answer.get('bundle_ref'),
        'selected_handle': answer.get('selected_handle'),
        'verb': answer.get('verb'),
        'evidence_slice_id': answer.get('evidence_slice_id'),
        'answer_status': answer.get('answer_status') or ('insufficient_data' if 'insufficient_data' in answer_text.lower() else 'answered'),
        'review_only': True,
        'no_execution': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Validate finance follow-up answer.')
    parser.add_argument('--answer', required=True, help='Path to answer JSON')
    parser.add_argument('--bundle', default=None, help='Path to reader bundle JSON')
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)

    answer = load_json_safe(Path(args.answer), {}) or {}
    bundle = load_json_safe(Path(args.bundle), {}) if args.bundle else {}

    report = validate(answer, bundle)
    atomic_write_json(Path(args.out), report)
    print(json.dumps({
        'status': report['status'],
        'errors': report['errors'],
        'warnings': report['warnings'],
        'out': args.out,
    }, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
