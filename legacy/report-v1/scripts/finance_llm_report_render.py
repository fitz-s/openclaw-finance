#!/usr/bin/env python3
"""Gate optional LLM prose rendering for finance reports.

This script never calls a model by itself. The OpenClaw report job may create a
candidate markdown file; this script wraps that candidate into a ReportEnvelope,
validates it, and selects either the candidate or deterministic fallback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe
from finance_report_delivery_safety import SAFETY_STATE, evaluate as evaluate_delivery_safety, health_only_markdown

WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
PROMPT = FINANCE / 'prompts' / 'report-renderer.md'
INPUT_PACKET = FINANCE / 'state' / 'report-input-packet.json'
BASE_ENVELOPE = FINANCE / 'state' / 'finance-report-envelope.json'
CANDIDATE_ENVELOPE = FINANCE / 'state' / 'finance-report-envelope-llm.json'
CANDIDATE_MARKDOWN = FINANCE / 'state' / 'finance-report-llm-candidate.md'
LLM_REPORT = FINANCE / 'state' / 'finance-report-llm-render-report.json'
VALIDATOR = FINANCE / 'scripts' / 'finance_report_validator.py'
NUMERIC_CLAIM_RE = re.compile(
    r'(?:DTE\s*\d+)|(?:[+-]?\$\d[\d,]*(?:\.\d+)?)|(?:[+-]?\d+(?:\.\d+)?%)|(?:\d+(?:\.\d+)?x)'
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def envelope_hash(envelope: dict[str, Any]) -> str:
    clone = dict(envelope)
    clone.pop('envelope_hash', None)
    raw = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def numeric_claims(markdown: str) -> list[str]:
    return sorted(match.group(0).replace(' ', '') for match in NUMERIC_CLAIM_RE.finditer(markdown or ''))


def write_report(path: Path, payload: dict[str, Any]) -> None:
    payload.setdefault('generated_at', now_iso())
    atomic_write_json(path, payload)
    print(json.dumps({'status': payload['status'], 'blocking_reasons': payload.get('blocking_reasons', []), 'out': str(path)}, ensure_ascii=False))


def validate_candidate(candidate: Path, packet: Path, report_path: Path) -> tuple[int, dict[str, Any]]:
    validation_path = report_path.with_name(f'{report_path.stem}-validator.json')
    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            '--envelope', str(candidate),
            '--input-packet', str(packet),
            '--out', str(validation_path),
        ],
        capture_output=True,
        text=True,
    )
    validation = load_json_safe(validation_path, {}) or {}
    return result.returncode, validation


def numeric_preservation_errors(base_path: Path, candidate_path: Path) -> list[str]:
    base = load_json_safe(base_path, {}) or {}
    candidate = load_json_safe(candidate_path, {}) or {}
    base_claims = numeric_claims(str(base.get('markdown') or ''))
    candidate_claims = numeric_claims(str(candidate.get('markdown') or ''))
    if base_claims != candidate_claims:
        return ['numeric_claims_changed']
    return []


def write_candidate_envelope(
    *,
    base_path: Path,
    candidate_markdown_path: Path,
    candidate_envelope_path: Path,
    model_id: str,
    renderer_id: str,
    prompt_version: str,
) -> dict[str, Any]:
    base = load_json_safe(base_path, {}) or {}
    markdown = candidate_markdown_path.read_text(encoding='utf-8')
    candidate = dict(base)
    candidate['renderer_id'] = renderer_id
    candidate['model_id'] = model_id
    candidate['prompt_version'] = prompt_version
    candidate['markdown'] = markdown
    candidate['envelope_hash'] = envelope_hash(candidate)
    atomic_write_json(candidate_envelope_path, candidate)
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Optional gated LLM finance report renderer.')
    parser.add_argument('--enable-llm', action='store_true')
    parser.add_argument('--prompt', default=str(PROMPT))
    parser.add_argument('--input-packet', default=str(INPUT_PACKET))
    parser.add_argument('--base-envelope', default=str(BASE_ENVELOPE))
    parser.add_argument('--candidate-envelope', default=str(CANDIDATE_ENVELOPE))
    parser.add_argument('--candidate-markdown', default=str(CANDIDATE_MARKDOWN))
    parser.add_argument('--allow-fallback', action='store_true')
    parser.add_argument('--model-id', default='openclaw-cron-model')
    parser.add_argument('--renderer-id', default='llm-v1')
    parser.add_argument('--prompt-version', default='report-renderer-v1')
    parser.add_argument('--delivery-safety', default=str(SAFETY_STATE))
    parser.add_argument('--out', default=str(LLM_REPORT))
    args = parser.parse_args(argv)

    out = Path(args.out)
    prompt_path = Path(args.prompt)
    packet_path = Path(args.input_packet)
    base_path = Path(args.base_envelope)
    candidate_path = Path(args.candidate_envelope)
    candidate_markdown_path = Path(args.candidate_markdown)
    safety_path = Path(args.delivery_safety)

    if not args.enable_llm:
        write_report(out, {
            'status': 'skipped',
            'llm_enabled': False,
            'blocking_reasons': ['llm_disabled_by_default'],
            'prompt_path': str(prompt_path),
            'input_packet_path': str(packet_path),
            'base_envelope_path': str(base_path),
            'candidate_envelope_path': None,
            'selected_envelope_path': str(base_path),
            'selected_renderer': 'deterministic_fallback',
        })
        return 0

    if not prompt_path.exists() or not packet_path.exists() or not base_path.exists():
        missing = [
            name for name, path in {
                'prompt': prompt_path,
                'input_packet': packet_path,
                'base_envelope': base_path,
            }.items()
            if not path.exists()
        ]
        write_report(out, {
            'status': 'fail',
            'llm_enabled': True,
            'blocking_reasons': [f'missing_required_artifact:{",".join(missing)}'],
        })
        return 1

    safety = evaluate_delivery_safety(safety_path=safety_path)
    if safety['status'] != 'pass':
        write_report(out, {
            'status': 'blocked',
            'llm_enabled': True,
            'blocking_reasons': safety['blocking_reasons'],
            'safety_check': safety,
            'health_only_markdown': health_only_markdown(safety),
            'prompt_path': str(prompt_path),
            'input_packet_path': str(packet_path),
            'base_envelope_path': str(base_path),
            'candidate_envelope_path': str(candidate_path) if candidate_path.exists() else None,
            'selected_envelope_path': None,
            'selected_renderer': None,
        })
        return 2

    if candidate_markdown_path.exists():
        write_candidate_envelope(
            base_path=base_path,
            candidate_markdown_path=candidate_markdown_path,
            candidate_envelope_path=candidate_path,
            model_id=args.model_id,
            renderer_id=args.renderer_id,
            prompt_version=args.prompt_version,
        )

    if not candidate_path.exists():
        write_report(out, {
            'status': 'fail',
            'llm_enabled': True,
            'blocking_reasons': ['candidate_envelope_required'],
            'prompt_path': str(prompt_path),
            'input_packet_path': str(packet_path),
            'base_envelope_path': str(base_path),
        })
        return 1

    rc, validation = validate_candidate(candidate_path, packet_path, out)
    preservation_errors = numeric_preservation_errors(base_path, candidate_path)
    if rc != 0 or preservation_errors:
        if args.allow_fallback:
            write_report(out, {
                'status': 'fallback',
                'llm_enabled': True,
                'blocking_reasons': ['candidate_failed_validator'] if rc != 0 else preservation_errors,
                'validator': validation,
                'candidate_envelope_path': str(candidate_path),
                'selected_envelope_path': str(base_path),
                'selected_renderer': 'deterministic_fallback',
            })
            return 0
        write_report(out, {
            'status': 'fail',
            'llm_enabled': True,
            'blocking_reasons': ['candidate_failed_validator'] if rc != 0 else preservation_errors,
            'validator': validation,
            'candidate_envelope_path': str(candidate_path),
            'selected_envelope_path': None,
        })
        return 1

    write_report(out, {
        'status': 'pass',
        'llm_enabled': True,
        'blocking_reasons': [],
        'prompt_path': str(prompt_path),
        'input_packet_path': str(packet_path),
        'base_envelope_path': str(base_path),
        'candidate_envelope_path': str(candidate_path),
        'selected_envelope_path': str(candidate_path),
        'selected_renderer': args.renderer_id,
        'validator': validation,
    })
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
