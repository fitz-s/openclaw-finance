#!/usr/bin/env python3
"""Product-quality validator for decision-grade finance reports."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


ROOT = Path('/Users/leofitz/.openclaw')
WORKSPACE = ROOT / 'workspace'
FINANCE = WORKSPACE / 'finance'
REPORT = FINANCE / 'state' / 'finance-decision-report-envelope.json'
PACKET = WORKSPACE / 'services' / 'market-ingest' / 'state' / 'latest-context-packet.json'
JUDGMENT = FINANCE / 'state' / 'judgment-envelope.json'
VALIDATION = FINANCE / 'state' / 'judgment-validation.json'
OUT = FINANCE / 'state' / 'finance-report-product-validation.json'

REQUIRED_SECTIONS = [
    '## 结论',
    '## 今日看点',
    '## 为什么现在',
    '## 市场机会雷达（Watchlist / Flow）',
    '## 未知探索（非持仓 / 非Watchlist）',
    '## 潜在机会 / 风险候选',
    '## 期权与风险雷达',
    '## 分层证据',
    '## 矛盾与裁决',
    '## 持仓影响',
    '## 反证 / Invalidators',
    '## 下一步观察',
    '## 数据质量',
    '## 来源',
]
BANNED = {
    'thresholds_not_met': re.compile(r'thresholds not met', re.I),
    'native_shadow': re.compile(r'Native Shadow', re.I),
    'old_open_title': re.compile(r'开盘短报|盘前简报（Native Shadow）'),
    'raw_flex_xml': re.compile(r'FlexQueryResponse|portfolio-flex-latest\.redacted\.xml', re.I),
    'account_identifier': re.compile(r'\baccountId\b|\bacctAlias\b'),
    'raw_machine_confidence': re.compile(r'confidence:\s*0\.0', re.I),
    'raw_state_labels': re.compile(r'thesis_state:|actionability:', re.I),
    'metadata_only_noise': re.compile(r'metadata_only|ordinary_form4_support_only|support-only', re.I),
    'source_status_as_reason': re.compile(r'Portfolio source status unavailable|Option risk source status stale_source', re.I),
    'expanded_evidence_log': re.compile(r'\(\+\d+ more\)'),
    'raw_provenance_footer': re.compile(r'packet_hash|judgment_id|model_id', re.I),
}


def error(code: str, message: str) -> dict[str, str]:
    return {'code': code, 'message': message}


def validate(report: dict[str, Any], packet: dict[str, Any], judgment: dict[str, Any], judgment_validation: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    markdown = str(report.get('markdown') or '')
    for section in REQUIRED_SECTIONS:
        if section not in markdown:
            errors.append(error('missing_section', section))
    for code, pattern in BANNED.items():
        if pattern.search(markdown):
            errors.append(error(code, f'banned text matched: {code}'))
    if report.get('packet_hash') != packet.get('packet_hash') or report.get('packet_hash') != judgment.get('packet_hash'):
        errors.append(error('packet_hash_mismatch', 'report, packet, and judgment hashes must match'))
    if report.get('judgment_id') != judgment.get('judgment_id'):
        errors.append(error('judgment_id_mismatch', 'report must bind to selected JudgmentEnvelope'))
    if judgment_validation.get('errors'):
        errors.append(error('judgment_validation_errors', 'judgment validation must be clean'))
    if judgment_validation.get('outcome') not in {'accepted_for_log', 'requires_operator_review'}:
        errors.append(error('judgment_validation_not_accepted', 'judgment validation outcome is not accepted'))
    refs = set(judgment.get('evidence_refs', []))
    if not refs:
        errors.append(error('missing_evidence_refs', 'report requires judgment evidence_refs'))
    if not isinstance(report.get('evidence_refs'), list) or set(report.get('evidence_refs', [])) != refs:
        errors.append(error('envelope_evidence_ref_mismatch', 'report envelope must retain judgment evidence_refs'))
    if report.get('actionability') == 'none' and '不下单' not in markdown:
        errors.append(error('missing_no_execution_language', 'no-action report must explicitly say no execution'))
    if report.get('thesis_state') == 'no_trade' and 'no_trade' not in markdown:
        errors.append(error('missing_no_trade_state', 'no_trade state must be visible'))
    if '## 分层证据' in markdown and all(layer not in markdown for layer in ['L0', 'L1', 'L2', 'L3', 'L4']):
        errors.append(error('missing_layer_digest', 'layer digest must mention L0-L4'))
    if len(markdown.strip()) < 600:
        warnings.append(error('short_report', 'decision report is unusually short'))
    if len(markdown.splitlines()) > 70:
        errors.append(error('report_too_long_lines', 'scheduled decision report must stay within 70 lines'))
    if len(markdown) > 5200:
        errors.append(error('report_too_long_chars', 'scheduled decision report must stay within 5200 characters'))
    if len(re.findall(r'`ev:[^`]+`', markdown)) > 12:
        errors.append(error('too_many_evidence_refs', 'user report is exposing too many machine evidence refs'))
    if '报告主轴：先找非持仓/非 watchlist' not in markdown:
        errors.append(error('missing_opportunity_first_contract', 'report must state opportunity expansion is primary'))
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', default=str(REPORT))
    parser.add_argument('--packet', default=str(PACKET))
    parser.add_argument('--judgment', default=str(JUDGMENT))
    parser.add_argument('--judgment-validation', default=str(VALIDATION))
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    report = load_json_safe(Path(args.report), {}) or {}
    packet = load_json_safe(Path(args.packet), {}) or {}
    judgment = load_json_safe(Path(args.judgment), {}) or {}
    validation = load_json_safe(Path(args.judgment_validation), {}) or {}
    errors, warnings = validate(report, packet, judgment, validation)
    payload = {
        'status': 'pass' if not errors else 'fail',
        'error_count': len(errors),
        'warning_count': len(warnings),
        'errors': errors,
        'warnings': warnings,
        'report_path': str(args.report),
        'packet_hash': packet.get('packet_hash'),
        'judgment_id': judgment.get('judgment_id'),
        'product_contract': 'finance-decision-report-v1',
    }
    atomic_write_json(Path(args.out), payload)
    print(json.dumps({'status': payload['status'], 'error_count': payload['error_count'], 'out': str(args.out)}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
