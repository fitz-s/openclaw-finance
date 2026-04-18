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

REQUIRED_SECTIONS_BASE = [
    '## 结论',
    '## 期权与风险雷达',
    '## 分层证据',
    '## 矛盾与裁决',
    '## 反证 / Invalidators',
    '## 下一步观察',
    '## 数据质量',
    '## 来源',
]
REQUIRED_SECTIONS_THESIS_DELTA = REQUIRED_SECTIONS_BASE + [
    '## 今日看点',
    '## 为什么现在',
    '## 市场机会雷达（Watchlist / Flow）',
    '## 未知探索（非持仓 / 非Watchlist）',
    '## 潜在机会 / 风险候选',
    '## 持仓影响',
]
REQUIRED_SECTIONS_CAPITAL_DELTA = REQUIRED_SECTIONS_BASE + [
    '## 资本议程',
    '## 替代分析',
    '## 护城河缺口',
    '## Thesis 焦点',
    '## 场景敏感面',
    '## 市场机会雷达',
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

PRIMARY_BANNED = {
    'machine_hashes': re.compile(r'packet_hash|graph_hash|report_hash|judgment_id|model_id', re.I),
    'raw_ref_counts': re.compile(r'\b(?:thesis_refs|scenario_refs|invalidator_refs|opportunity_candidate_refs)\s*=\s*\d+', re.I),
    'raw_evidence_refs': re.compile(r'`?ev:[^`\s]+`?', re.I),
    'route_card_only': re.compile(r'^\s*Finance｜[^\n]+\n值得看：', re.M),
}

THREAD_REQUIRED_TOKENS = ['对象卡', '可直接追问']


BOARD_BANNED = {
    'machine_hashes': re.compile(r'packet_hash|graph_hash|report_hash|judgment_id|model_id', re.I),
    'raw_evidence_refs': re.compile(r'`?ev:[^`\s]+`?', re.I),
}


def error(code: str, message: str) -> dict[str, str]:
    return {'code': code, 'message': message}


def _validate_artifact_markdown(report: dict[str, Any], packet: dict[str, Any], judgment: dict[str, Any], judgment_validation: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    markdown = str(report.get('markdown') or '')
    renderer_id = str(report.get('renderer_id') or '')
    is_capital_delta = 'capital-delta' in renderer_id
    required_sections = REQUIRED_SECTIONS_CAPITAL_DELTA if is_capital_delta else REQUIRED_SECTIONS_THESIS_DELTA
    for section in required_sections:
        if section not in markdown:
            errors.append(error('missing_section', section))
    if 'Core macro triad' not in markdown:
        errors.append(error('missing_core_macro_triad', 'artifact markdown must analyze Gold / Bitcoin / SPX direction'))
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
    max_lines = 85 if is_capital_delta else 70
    max_chars = 6500 if is_capital_delta else 5200
    if len(markdown.splitlines()) > max_lines:
        errors.append(error('report_too_long_lines', f'decision report must stay within {max_lines} lines'))
    if len(markdown) > max_chars:
        errors.append(error('report_too_long_chars', f'decision report must stay within {max_chars} characters'))
    if len(re.findall(r'`ev:[^`]+`', markdown)) > 12:
        errors.append(error('too_many_evidence_refs', 'user report is exposing too many machine evidence refs'))
    # Mode-specific validations
    if is_capital_delta:
        if '## 资本议程' not in markdown:
            errors.append(error('missing_capital_agenda_section', 'capital_delta report must have agenda section'))
        if '报告主轴：资本竞争优先' not in markdown:
            errors.append(error('missing_capital_competition_contract', 'capital_delta must state capital competition axis'))
        if '## 替代分析' not in markdown:
            warnings.append(error('missing_displacement_analysis', 'capital_delta should show displacement reasoning'))
        if not report.get('capital_agenda_refs') and not report.get('capital_graph_hash'):
            warnings.append(error('missing_capital_refs', 'capital_delta should bind agenda/displacement refs'))
    else:
        if '报告主轴：先找非持仓/非 watchlist' not in markdown:
            errors.append(error('missing_opportunity_first_contract', 'report must state opportunity expansion is primary'))
    return errors, warnings


def _validate_operator_primary(report: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]], str]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    primary = str(report.get('discord_primary_markdown') or '')
    primary_missing = not primary
    if not primary:
        primary = str(report.get('markdown') or '')
        warnings.append(error('discord_primary_markdown_missing', 'fallback to artifact markdown'))
    if not primary:
        errors.append(error('primary_missing', 'no primary or fallback markdown available'))
        return errors, warnings, primary
    if not primary_missing:
        for section in ['Fact', 'Interpretation', 'To Verify', '对象']:
            if section not in primary:
                errors.append(error('primary_missing_section', section))
        macro_tokens = ['Macro triad', 'Gold', 'Bitcoin', 'SPX']
        for token in macro_tokens:
            if token not in primary:
                errors.append(error('primary_missing_macro_triad', f'primary must include {token} direction'))
        if not isinstance(report.get('object_alias_map'), dict) or not report.get('object_alias_map'):
            errors.append(error('missing_object_alias_map', 'primary surface requires translated object aliases'))
        if not any(prefix in primary for prefix in ['A1 ', 'T1 ', 'O1 ', 'I1 ']):
            errors.append(error('missing_object_translation', 'primary surface must translate at least one handle into an object line'))
    banned_items = PRIMARY_BANNED.items() if not primary_missing else [('route_card_only', PRIMARY_BANNED['route_card_only'])]
    for code, pattern in banned_items:
        if pattern.search(primary):
            errors.append(error(code, f'primary surface matched banned pattern: {code}'))
    if len(primary) > 800:
        warnings.append(error('primary_too_long', 'discord primary markdown exceeds Core guidance'))
    if len(primary.strip().splitlines()) <= 5:
        errors.append(error('primary_too_shallow', 'primary surface cannot degrade to a route card'))
    return errors, warnings, primary


def _validate_thread_seed(report: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    thread_seed = str(report.get('discord_thread_seed_markdown') or '')
    if not thread_seed:
        warnings.append(error('discord_thread_seed_missing', 'thread seed markdown missing'))
        return errors, warnings
    for token in THREAD_REQUIRED_TOKENS:
        if token not in thread_seed:
            errors.append(error('thread_seed_missing_token', token))
    starter_queries = report.get('starter_queries')
    if not isinstance(starter_queries, list) or not starter_queries:
        errors.append(error('thread_seed_missing_queries', 'starter_queries required for follow-up thread'))
    bundle_path = str(report.get('followup_bundle_path') or '')
    if not bundle_path.endswith('.json'):
        errors.append(error('thread_seed_missing_bundle_path', 'followup bundle path must point to json bundle'))
    return errors, warnings


def _validate_options_iv_context(report: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    summary = report.get('options_iv_surface_summary')
    if summary is None:
        warnings.append(error('options_iv_surface_summary_missing', 'options IV surface is absent from report source context'))
        return errors, warnings
    if not isinstance(summary, dict):
        errors.append(error('options_iv_surface_summary_invalid', 'options IV surface summary must be a compact object'))
        return errors, warnings
    if summary.get('raw_payload_retained') is True:
        errors.append(error('options_iv_raw_payload_retained', 'options IV context must not retain raw vendor payloads'))
    if summary.get('authority') != 'source_context_only_not_judgment_wake_threshold_or_execution':
        errors.append(error('options_iv_authority_boundary_missing', 'options IV context must remain source-context-only'))
    if summary.get('derived_only') is not True and (summary.get('symbol_count') or 0):
        errors.append(error('options_iv_not_derived_only', 'options IV rows must be derived-only'))
    if report.get('options_iv_authority') != 'source_context_only_not_judgment_wake_threshold_or_execution':
        errors.append(error('options_iv_report_authority_boundary_missing', 'report envelope must keep options IV out of judgment/wake/threshold authority'))
    refs = set(report.get('evidence_refs') or [])
    iv_refs = {str(ref) for ref in summary.get('source_health_refs', []) if isinstance(ref, str)}
    if refs & iv_refs:
        errors.append(error('options_iv_refs_in_judgment_evidence', 'options IV source-health refs must not be JudgmentEnvelope evidence_refs'))
    return errors, warnings


def _validate_campaign_boards(report: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    board_fields = [
        'discord_live_board_markdown',
        'discord_scout_board_markdown',
        'discord_risk_board_markdown',
    ]
    present = [field for field in board_fields if str(report.get(field) or '').strip()]
    if not present:
        return errors, warnings
    for field in present:
        text = str(report.get(field) or '')
        if not text.startswith('Finance｜'):
            errors.append(error('campaign_board_bad_title', f'{field} must start with Finance｜'))
        if field == 'discord_live_board_markdown':
            for token in ['Macro triad', 'Gold', 'Bitcoin', 'SPX']:
                if token not in text:
                    errors.append(error('campaign_board_missing_macro_triad', f'{field} must include {token} direction'))
        for code, pattern in BOARD_BANNED.items():
            if pattern.search(text):
                errors.append(error(code, f'{field} matched banned pattern: {code}'))
    return errors, warnings


def validate_report(report: dict[str, Any], packet: dict[str, Any], judgment: dict[str, Any], judgment_validation: dict[str, Any]) -> dict[str, Any]:
    artifact_errors, artifact_warnings = _validate_artifact_markdown(report, packet, judgment, judgment_validation)
    primary_errors, primary_warnings, primary_text = _validate_operator_primary(report)
    thread_errors, thread_warnings = _validate_thread_seed(report)
    board_errors, board_warnings = _validate_campaign_boards(report)
    options_errors, options_warnings = _validate_options_iv_context(report)
    errors = artifact_errors + primary_errors + board_errors + options_errors
    warnings = artifact_warnings + primary_warnings + thread_errors + thread_warnings + board_warnings + options_warnings
    return {
        'errors': errors,
        'warnings': warnings,
        'artifact_errors': artifact_errors,
        'artifact_warnings': artifact_warnings,
        'operator_errors': primary_errors,
        'operator_warnings': primary_warnings,
        'thread_errors': thread_errors,
        'thread_warnings': thread_warnings,
        'campaign_board_errors': board_errors,
        'campaign_board_warnings': board_warnings,
        'options_iv_errors': options_errors,
        'options_iv_warnings': options_warnings,
        'discord_primary_ok': not primary_errors,
        'thread_followup_ok': not thread_errors,
        'campaign_boards_ok': not board_errors,
        'primary_markdown': primary_text,
    }


def validate(report: dict[str, Any], packet: dict[str, Any], judgment: dict[str, Any], judgment_validation: dict[str, Any]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    result = validate_report(report, packet, judgment, judgment_validation)
    return result['errors'], result['warnings']


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
    result = validate_report(report, packet, judgment, validation)
    payload = {
        'status': 'pass' if not result['errors'] else 'fail',
        'error_count': len(result['errors']),
        'warning_count': len(result['warnings']),
        'errors': result['errors'],
        'warnings': result['warnings'],
        'artifact_errors': result['artifact_errors'],
        'artifact_warnings': result['artifact_warnings'],
        'operator_errors': result['operator_errors'],
        'operator_warnings': result['operator_warnings'],
        'thread_errors': result['thread_errors'],
        'thread_warnings': result['thread_warnings'],
        'campaign_board_errors': result['campaign_board_errors'],
        'campaign_board_warnings': result['campaign_board_warnings'],
        'options_iv_errors': result['options_iv_errors'],
        'options_iv_warnings': result['options_iv_warnings'],
        'discord_primary_ok': result['discord_primary_ok'],
        'thread_followup_ok': result['thread_followup_ok'],
        'campaign_boards_ok': result['campaign_boards_ok'],
        'report_path': str(args.report),
        'packet_hash': packet.get('packet_hash'),
        'judgment_id': judgment.get('judgment_id'),
        'product_contract': 'finance-decision-report-v1',
    }
    atomic_write_json(Path(args.out), payload)
    print(json.dumps({'status': payload['status'], 'error_count': payload['error_count'], 'out': str(args.out)}, ensure_ascii=False))
    return 0 if not result['errors'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
