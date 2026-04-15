#!/usr/bin/env python3
"""Validate Finance ReportEnvelope before delivery."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe

WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
REPORT_ENVELOPE = FINANCE / 'state' / 'finance-report-envelope.json'
INPUT_PACKET = FINANCE / 'state' / 'report-input-packet.json'
VALIDATION_OUT = FINANCE / 'state' / 'finance-report-validation.json'

BANNED_MARKDOWN_PATTERNS = {
    'internal_threshold_phrase': re.compile(r'thresholds not met', re.I),
    'native_shadow_title': re.compile(r'Native Shadow', re.I),
    'internal_gate_reason': re.compile(r'short\+core|core fires|short fires|perpetual short-only|cv=\d|importance=\d', re.I),
    'raw_flex_xml': re.compile(r'FlexQueryResponse|portfolio-flex-latest\.redacted\.xml', re.I),
    'raw_account_attribute': re.compile(r'\baccountId\b|\bacctAlias\b'),
    'raw_iso_timestamp': re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}'),
}
REQUIRED_MARKDOWN_SECTIONS = {
    'conclusion': '## 结论',
    'portfolio': '## 持仓',
    'why_now': '## 为什么现在',
    'evidence': '## 核心证据',
    'data_quality': '## 数据质量',
    'next_watch': '## 下一步',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_payload(payload: dict[str, Any]) -> str:
    clone = dict(payload)
    clone.pop('envelope_hash', None)
    raw = json.dumps(clone, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def error(code: str, message: str) -> dict[str, str]:
    return {'code': code, 'message': message}


def source_names(envelope: dict[str, Any]) -> set[str]:
    return {str(item.get('name')) for item in envelope.get('source_refs', []) if isinstance(item, dict)}


def validate_envelope(envelope: dict[str, Any], packet: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    required = [
        'report_policy_version',
        'prompt_version',
        'renderer_id',
        'model_id',
        'input_packet_hash',
        'envelope_hash',
        'headline',
        'market_snapshot',
        'portfolio_snapshot',
        'risk_flags',
        'watchlist_moves',
        'data_quality',
        'why_no_alert',
        'next_watch_conditions',
        'source_refs',
        'markdown',
    ]
    for key in required:
        if key not in envelope:
            errors.append(error('missing_field', key))
    if errors:
        return errors, warnings

    packet_hash = packet.get('packet_hash')
    if not packet_hash:
        errors.append(error('input_packet_missing_hash', 'Input packet must carry packet_hash.'))
    elif envelope.get('input_packet_hash') != packet_hash:
        errors.append(error('input_packet_hash_mismatch', 'Envelope input_packet_hash does not match packet_hash.'))
    expected_hash = hash_payload(envelope)
    if envelope.get('envelope_hash') != expected_hash:
        errors.append(error('envelope_hash_mismatch', 'Envelope hash does not match envelope content.'))

    markdown = str(envelope.get('markdown') or '')
    for code, pattern in BANNED_MARKDOWN_PATTERNS.items():
        if pattern.search(markdown) or pattern.search(str(envelope.get('headline') or '')):
            errors.append(error(code, f'Banned report text matched: {code}'))

    for code, marker in REQUIRED_MARKDOWN_SECTIONS.items():
        if marker not in markdown:
            errors.append(error(f'missing_section:{code}', f'Missing markdown section marker: {marker}'))

    if not str(envelope.get('why_no_alert') or '').strip():
        errors.append(error('missing_why_no_alert', 'why_no_alert must be present even when observations exist.'))
    if not envelope.get('next_watch_conditions'):
        errors.append(error('missing_next_watch_conditions', 'next_watch_conditions must be non-empty.'))

    if '[持仓数据不可用]' in markdown and not re.search(r'抑制|避免|等待|不可用原因|fail-closed', markdown, re.I):
        errors.append(error('unexplained_holdings_unavailable', 'Holdings unavailable text must explain consequence.'))

    names = source_names(envelope)
    if len(names) < 5 and packet.get('unavailable_facts') != ['packet_unavailable']:
        errors.append(error('insufficient_source_refs', 'Report must carry at least five source refs unless packet is unavailable.'))

    pnl_claim = re.search(r'(盈亏|P&L|pnl).{0,30}([+-]?\$?\d[\d,]*(?:\.\d+)?)', markdown, re.I)
    if pnl_claim and 'performance' not in names:
        errors.append(error('pnl_claim_without_performance_ref', 'P&L/盈亏 numeric claims require a performance source ref.'))

    unavailable = set(packet.get('unavailable_facts', []))
    if 'open_position_unrealized_pnl' in unavailable and re.search(r'未实现盈亏\s*[+$-]?\d', markdown):
        errors.append(error('unavailable_open_position_pnl_claimed', 'OpenPosition unrealized PnL is unavailable and must not be narrated as fresh.'))

    for fact_group in ['market_snapshot', 'risk_flags', 'watchlist_moves', 'data_quality']:
        for item in envelope.get(fact_group, []):
            if isinstance(item, dict) and item.get('source_ref') and item['source_ref'] not in names:
                errors.append(error('unknown_fact_source_ref', f'{fact_group} references unknown source_ref {item["source_ref"]}.'))

    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Validate finance report envelope.')
    parser.add_argument('--envelope', default=str(REPORT_ENVELOPE))
    parser.add_argument('--input-packet', default=str(INPUT_PACKET))
    parser.add_argument('--out', default=str(VALIDATION_OUT))
    args = parser.parse_args(argv)
    envelope = load_json_safe(Path(args.envelope), {}) or {}
    packet = load_json_safe(Path(args.input_packet), {}) or {}
    errors, warnings = validate_envelope(envelope, packet)
    report = {
        'generated_at': now_iso(),
        'status': 'pass' if not errors else 'fail',
        'error_count': len(errors),
        'warning_count': len(warnings),
        'errors': errors,
        'warnings': warnings,
        'envelope_path': str(args.envelope),
        'input_packet_path': str(args.input_packet),
    }
    atomic_write_json(Path(args.out), report)
    print(json.dumps({'status': report['status'], 'error_count': report['error_count'], 'out': str(args.out)}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
