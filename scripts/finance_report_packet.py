#!/usr/bin/env python3
"""Compile the compact, provenance-bound input packet for finance reports."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe

WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
OPS_STATE = WORKSPACE / 'ops' / 'state'

PRICES = FINANCE / 'state' / 'prices.json'
SCAN_STATE = FINANCE / 'state' / 'intraday-open-scan-state.json'
GATE_STATE = FINANCE / 'state' / 'report-gate-state.json'
PORTFOLIO = FINANCE / 'state' / 'portfolio-resolved.json'
PERFORMANCE = FINANCE / 'state' / 'portfolio-performance.json'
CASH_NAV = FINANCE / 'state' / 'portfolio-cash-nav.json'
OPTION_RISK = FINANCE / 'state' / 'portfolio-option-risk.json'
SCANNER_REPORT = OPS_STATE / 'finance-native-market-hours-live-report.json'
MISSING_SCANNER_OUTPUT = OPS_STATE / 'missing-scanner-output.json'
PACKET_OUT = FINANCE / 'state' / 'report-input-packet.json'
LATEST_CONTEXT_PACKET = WORKSPACE / 'services' / 'market-ingest' / 'state' / 'latest-context-packet.json'
REPORT_POLICY_VERSION = 'finance-report-input-v1'
CANONICAL_AUTHORITY = 'typed_decision_flow'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_path(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def packet_hash(packet: dict[str, Any]) -> str:
    raw = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def source_ref(name: str, path: Path, payload: Any) -> dict[str, Any]:
    exists = path.exists()
    data = payload if isinstance(payload, dict) else {}
    return {
        'name': name,
        'path': str(path),
        'exists': exists,
        'sha256': sha256_path(path),
        'data_status': data.get('data_status'),
        'quality': data.get('quality'),
        'generated_at': data.get('generated_at'),
        'fetched_at': data.get('fetched_at'),
        'source_redacted_sha256': data.get('source_redacted_sha256'),
        'source_statement_from': data.get('source_statement_from'),
        'source_statement_to': data.get('source_statement_to'),
    }


def canonical_context_packet_summary(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    layer_digest = payload.get('layer_digest', {}) if isinstance(payload, dict) else {}
    layer_counts = {
        str(key): len(value) if isinstance(value, list) else 0
        for key, value in layer_digest.items()
    }
    return {
        'path': str(path),
        'packet_id': payload.get('packet_id'),
        'packet_hash': payload.get('packet_hash'),
        'evidence_ref_count': len(payload.get('evidence_refs', [])) if isinstance(payload.get('evidence_refs'), list) else 0,
        'contradiction_count': len(payload.get('contradictions', [])) if isinstance(payload.get('contradictions'), list) else 0,
        'layer_digest_counts': layer_counts,
        'source_quality_summary': payload.get('source_quality_summary', {}),
    }


def quote_for_symbol(quotes: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    quote = quotes.get(symbol) or quotes.get(symbol.replace('/', '-')) or quotes.get(symbol.replace('-', '/'))
    return quote if isinstance(quote, dict) else None


def quote_pct(quote: dict[str, Any]) -> float | None:
    pct = quote.get('change_pct', quote.get('pct_change'))
    return round(float(pct), 4) if isinstance(pct, (int, float)) else None


def compact_quote(symbol: str, quote: dict[str, Any]) -> dict[str, Any]:
    return {
        'symbol': symbol,
        'price': quote.get('price', quote.get('close')),
        'change': quote.get('change'),
        'change_pct': quote_pct(quote),
        'status': quote.get('status'),
        'source': 'prices.json',
    }


def watchlist_symbols(watchlist: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ['indexes', 'tickers', 'crypto']:
        for item in watchlist.get(key, []) if isinstance(watchlist, dict) else []:
            if isinstance(item, dict) and item.get('symbol'):
                out.append(str(item['symbol']))
    return out


def market_snapshot(prices: dict[str, Any], watchlist: dict[str, Any]) -> dict[str, Any]:
    quotes = prices.get('quotes', {}) if isinstance(prices, dict) else {}
    symbols = []
    for symbol in ['SPY', 'QQQ', 'BTC/USD', 'IAU']:
        quote = quote_for_symbol(quotes, symbol)
        if isinstance(quote, dict):
            symbols.append(compact_quote(symbol, quote))
    moves = []
    for symbol in watchlist_symbols(watchlist):
        quote = quote_for_symbol(quotes, symbol)
        if not isinstance(quote, dict):
            continue
        pct = quote_pct(quote)
        if pct is None:
            continue
        moves.append(compact_quote(symbol, quote))
    moves.sort(key=lambda item: abs(item.get('change_pct') or 0), reverse=True)
    return {
        'fetched_at': prices.get('fetched_at') if isinstance(prices, dict) else None,
        'core_quotes': symbols,
        'top_watchlist_moves': moves[:8],
    }


def normalize_gate_reason(reason: Any) -> str | None:
    if not isinstance(reason, str) or not reason.strip():
        return None
    lowered = reason.strip().lower()
    if lowered == 'thresholds not met':
        return 'no_candidate_met_report_threshold'
    if lowered.startswith('data stale'):
        return 'data_stale_waiting_for_refresh'
    if 'core fires' in lowered or 'short+core both passed' in lowered:
        return 'core_report_gate_recommended'
    if 'short fires' in lowered:
        return 'short_report_gate_recommended'
    return 'gate_reason_normalized'


def gate_snapshot(scan_state: dict[str, Any], gate_state: dict[str, Any]) -> dict[str, Any]:
    return {
        'last_scan_time': scan_state.get('last_scan_time') if isinstance(scan_state, dict) else None,
        'window': gate_state.get('window') if isinstance(gate_state, dict) else None,
        'accumulated_count': len(scan_state.get('accumulated', [])) if isinstance(scan_state, dict) else 0,
        'recommended_report_type': gate_state.get('recommendedReportType') if isinstance(gate_state, dict) else None,
        'candidate_count': gate_state.get('candidateCount', 0) if isinstance(gate_state, dict) else 0,
        'decision_reason': normalize_gate_reason(gate_state.get('decisionReason')) if isinstance(gate_state, dict) else None,
        'total_urgency': gate_state.get('totalUrgency') if isinstance(gate_state, dict) else None,
        'total_importance': gate_state.get('totalImportance') if isinstance(gate_state, dict) else None,
        'total_cumulative_value': gate_state.get('totalCumulativeValue') if isinstance(gate_state, dict) else None,
        'max_single_urgency': gate_state.get('maxSingleUrgency') if isinstance(gate_state, dict) else None,
    }


def portfolio_snapshot(portfolio: dict[str, Any]) -> dict[str, Any]:
    summary = portfolio.get('summary', {}) if isinstance(portfolio, dict) else {}
    selected_source = portfolio.get('selected_source') if isinstance(portfolio, dict) else None
    total_unrealized_pnl = summary.get('total_unrealized_pnl')
    if selected_source == 'flex':
        total_unrealized_pnl = None
    return {
        'selected_source': selected_source,
        'source': portfolio.get('source') if isinstance(portfolio, dict) else None,
        'data_status': portfolio.get('data_status') if isinstance(portfolio, dict) else None,
        'fetched_at': portfolio.get('fetched_at') if isinstance(portfolio, dict) else None,
        'summary': {
            'stock_positions': summary.get('stock_positions'),
            'option_positions': summary.get('option_positions'),
            'total_stock_value': summary.get('total_stock_value'),
            'total_option_value': summary.get('total_option_value'),
            'total_portfolio_value': summary.get('total_portfolio_value'),
            'total_unrealized_pnl': total_unrealized_pnl,
        },
        'source_quality': portfolio.get('source_quality', {}) if isinstance(portfolio, dict) else {},
        'enrichment_refs': portfolio.get('enrichment_refs', {}) if isinstance(portfolio, dict) else {},
    }


def performance_snapshot(performance: dict[str, Any]) -> dict[str, Any]:
    summary = performance.get('portfolio_summary', {}) if isinstance(performance, dict) else {}
    underlyings = performance.get('underlyings', {}) if isinstance(performance, dict) else {}
    rows = []
    for symbol, item in underlyings.items():
        if not isinstance(item, dict):
            continue
        rows.append({'symbol': symbol, 'total': item.get('total'), 'prior_open_mtm': item.get('prior_open_mtm')})
    rows.sort(key=lambda item: abs(item.get('total') or 0), reverse=True)
    return {
        'data_status': performance.get('data_status') if isinstance(performance, dict) else None,
        'total_mtm': summary.get('total'),
        'prior_open_mtm': summary.get('prior_open_mtm'),
        'top_attribution': rows[:6],
    }


def cash_nav_snapshot(cash_nav: dict[str, Any]) -> dict[str, Any]:
    exposure = cash_nav.get('exposure', {}) if isinstance(cash_nav, dict) else {}
    nav = cash_nav.get('nav', {}) if isinstance(cash_nav, dict) else {}
    cash = cash_nav.get('cash', {}) if isinstance(cash_nav, dict) else {}
    return {
        'data_status': cash_nav.get('data_status') if isinstance(cash_nav, dict) else None,
        'ending_cash': cash.get('ending_cash'),
        'ending_settled_cash': cash.get('ending_settled_cash'),
        'nav_total': nav.get('total'),
        'gross_exposure': exposure.get('gross_exposure'),
        'gross_exposure_ratio': exposure.get('gross_exposure_ratio'),
        'cash_ratio': exposure.get('cash_ratio'),
    }


def compact_option(option: dict[str, Any]) -> dict[str, Any]:
    return {
        'underlying': option.get('underlying'),
        'description': option.get('description'),
        'direction': option.get('direction'),
        'expiry': option.get('expiry'),
        'dte': option.get('dte'),
        'market_value': option.get('market_value'),
        'risk_flags': option.get('risk_flags', []),
        'moneyness_status': option.get('moneyness_status'),
    }


def option_risk_snapshot(option_risk: dict[str, Any]) -> dict[str, Any]:
    return {
        'data_status': option_risk.get('data_status') if isinstance(option_risk, dict) else None,
        'option_count': option_risk.get('option_count') if isinstance(option_risk, dict) else 0,
        'dte_buckets': option_risk.get('dte_buckets', {}) if isinstance(option_risk, dict) else {},
        'near_expiry_options': [compact_option(item) for item in option_risk.get('near_expiry_options', [])[:5] if isinstance(item, dict)] if isinstance(option_risk, dict) else [],
        'large_decay_risk': [compact_option(item) for item in option_risk.get('large_decay_risk', [])[:5] if isinstance(item, dict)] if isinstance(option_risk, dict) else [],
        'exercise_assignment_status': (option_risk.get('exercise_assignment') or {}).get('status') if isinstance(option_risk, dict) else None,
        'quality_notes': option_risk.get('quality_notes', []) if isinstance(option_risk, dict) else [],
    }


def scanner_output_path(scanner_report: dict[str, Any]) -> Path | None:
    output_path = scanner_report.get('output_path') if isinstance(scanner_report, dict) else None
    if not isinstance(output_path, str):
        return None
    path = Path(output_path)
    try:
        path.resolve().relative_to(WORKSPACE.resolve())
    except Exception:
        return None
    return path


def compact_observation(item: dict[str, Any], source_ref: str) -> dict[str, Any]:
    return {
        'id': item.get('id'),
        'theme': item.get('theme'),
        'summary': item.get('summary') or item.get('description'),
        'sources': item.get('sources', []),
        'urgency': item.get('urgency'),
        'importance': item.get('importance'),
        'novelty': item.get('novelty'),
        'cumulative_value': item.get('cumulative_value'),
        'source_ref': source_ref,
        'observed_at': item.get('observed_at') or item.get('ts'),
        'published_at': item.get('published_at'),
        'detected_at': item.get('detected_at'),
    }


def scanner_observations(scan_state: dict[str, Any], scanner_report: dict[str, Any]) -> list[dict[str, Any]]:
    path = scanner_output_path(scanner_report)
    if path is not None:
        output = load_json_safe(path, {}) or {}
        observations = [
            compact_observation(item, 'scanner_output')
            for item in output.get('observations', []) if isinstance(output, dict) and isinstance(item, dict)
        ]
        if observations:
            return observations[:8]

    accumulated = scan_state.get('accumulated', []) if isinstance(scan_state, dict) else []
    observations = [
        compact_observation(item, 'scan_state')
        for item in accumulated
        if isinstance(item, dict) and (item.get('theme') or item.get('summary') or item.get('description'))
    ]
    observations.sort(
        key=lambda item: (
            float(item.get('importance') or 0) + float(item.get('urgency') or 0) + float(item.get('cumulative_value') or 0),
            float(item.get('novelty') or 0),
        ),
        reverse=True,
    )
    return observations[:8]


def data_quality(source_refs: dict[str, dict[str, Any]], portfolio: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    items: list[dict[str, Any]] = []
    unavailable: list[str] = []
    for key, ref in source_refs.items():
        status = 'available' if ref['exists'] else 'missing'
        if ref.get('data_status') in {'stale_source', 'error', 'unavailable', 'portfolio_unavailable'}:
            status = 'unavailable'
        items.append({'key': key, 'status': status, 'data_status': ref.get('data_status'), 'sha256': ref.get('sha256')})
        if status != 'available':
            unavailable.append(key)
    source_quality = portfolio.get('source_quality', {}) if isinstance(portfolio, dict) else {}
    for key, ok in source_quality.items():
        if ok is False:
            unavailable.append(key)
    return items, sorted(set(unavailable))


def build_packet(
    *,
    prices: dict[str, Any],
    scan_state: dict[str, Any],
    gate_state: dict[str, Any],
    portfolio: dict[str, Any],
    performance: dict[str, Any],
    cash_nav: dict[str, Any],
    option_risk: dict[str, Any],
    scanner_report: dict[str, Any],
    watchlist: dict[str, Any],
    canonical_context_packet: dict[str, Any],
    paths: dict[str, Path],
) -> dict[str, Any]:
    generated_at = now_iso()
    refs = {
        'prices': source_ref('prices', paths['prices'], prices),
        'scan_state': source_ref('scan_state', paths['scan_state'], scan_state),
        'gate_state': source_ref('gate_state', paths['gate_state'], gate_state),
        'portfolio': source_ref('portfolio', paths['portfolio'], portfolio),
        'performance': source_ref('performance', paths['performance'], performance),
        'cash_nav': source_ref('cash_nav', paths['cash_nav'], cash_nav),
        'option_risk': source_ref('option_risk', paths['option_risk'], option_risk),
        'scanner_report': source_ref('scanner_report', paths['scanner_report'], scanner_report),
        'canonical_context_packet': source_ref('canonical_context_packet', paths['canonical_context_packet'], canonical_context_packet),
    }
    scanner_output = scanner_output_path(scanner_report)
    scanner_output_payload = load_json_safe(scanner_output, {}) if scanner_output is not None else {}
    if scanner_output is not None and scanner_output.exists():
        refs['scanner_output'] = source_ref('scanner_output', scanner_output, scanner_output_payload or {})
    quality, unavailable = data_quality(refs, portfolio)
    if portfolio.get('selected_source') == 'flex':
        unavailable.append('open_position_unrealized_pnl')
    unavailable = sorted(set(unavailable))
    packet = {
        'report_policy_version': REPORT_POLICY_VERSION,
        'packet_id': f"finance-report-input-{generated_at}",
        'generated_at': generated_at,
        'compatibility_view_only': True,
        'must_not_be_used_as_cognition_source': True,
        'canonical_authority': CANONICAL_AUTHORITY,
        'compatibility_note': (
            'This packet exists only for deprecated compatibility tools. '
            'The active user-visible finance report uses ContextPacket -> '
            'JudgmentEnvelope -> product report -> decision log -> safety gate.'
        ),
        'authoritative_artifacts': {
            'context_packet': str(paths['canonical_context_packet']),
            'gate_state': str(paths['gate_state']),
            'judgment_envelope': str(FINANCE / 'state' / 'judgment-envelope.json'),
            'product_report': str(FINANCE / 'state' / 'finance-decision-report-envelope.json'),
            'decision_log_report': str(FINANCE / 'state' / 'finance-decision-log-report.json'),
        },
        'market_snapshot': market_snapshot(prices, watchlist),
        'gate_snapshot': gate_snapshot(scan_state, gate_state),
        'portfolio_snapshot': portfolio_snapshot(portfolio),
        'performance_snapshot': performance_snapshot(performance),
        'cash_nav_snapshot': cash_nav_snapshot(cash_nav),
        'option_risk_snapshot': option_risk_snapshot(option_risk),
        'scanner_observations': scanner_observations(scan_state, scanner_report),
        'data_quality': quality,
        'unavailable_facts': unavailable,
        'required_omissions': [
            'raw_flex_xml',
            'raw_account_identifiers',
            'raw_source_attribute_values',
            'internal_threshold_phrase',
            'open_position_unrealized_pnl_zero_claim',
            'raw_news_text',
        ],
        'source_refs': refs,
        'canonical_context_packet': canonical_context_packet_summary(paths['canonical_context_packet'], canonical_context_packet),
    }
    packet['packet_hash'] = packet_hash(packet)
    return packet


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compile finance report input packet.')
    parser.add_argument('--prices', default=str(PRICES))
    parser.add_argument('--scan-state', default=str(SCAN_STATE))
    parser.add_argument('--gate-state', default=str(GATE_STATE))
    parser.add_argument('--portfolio', default=str(PORTFOLIO))
    parser.add_argument('--performance', default=str(PERFORMANCE))
    parser.add_argument('--cash-nav', default=str(CASH_NAV))
    parser.add_argument('--option-risk', default=str(OPTION_RISK))
    parser.add_argument('--scanner-report', default=str(SCANNER_REPORT))
    parser.add_argument('--canonical-context-packet', default=str(LATEST_CONTEXT_PACKET))
    parser.add_argument('--watchlist', default=str(FINANCE / 'state' / 'watchlist-resolved.json'))
    parser.add_argument('--out', default=str(PACKET_OUT))
    args = parser.parse_args(argv)
    paths = {
        'prices': Path(args.prices),
        'scan_state': Path(args.scan_state),
        'gate_state': Path(args.gate_state),
        'portfolio': Path(args.portfolio),
        'performance': Path(args.performance),
        'cash_nav': Path(args.cash_nav),
        'option_risk': Path(args.option_risk),
        'scanner_report': Path(args.scanner_report),
        'canonical_context_packet': Path(args.canonical_context_packet),
    }
    packet = build_packet(
        prices=load_json_safe(paths['prices'], {}) or {},
        scan_state=load_json_safe(paths['scan_state'], {}) or {},
        gate_state=load_json_safe(paths['gate_state'], {}) or {},
        portfolio=load_json_safe(paths['portfolio'], {}) or {},
        performance=load_json_safe(paths['performance'], {}) or {},
        cash_nav=load_json_safe(paths['cash_nav'], {}) or {},
        option_risk=load_json_safe(paths['option_risk'], {}) or {},
        scanner_report=load_json_safe(paths['scanner_report'], {}) or {},
        watchlist=load_json_safe(Path(args.watchlist), {}) or load_json_safe(FINANCE / 'watchlists' / 'core.json', {}) or {},
        canonical_context_packet=load_json_safe(paths['canonical_context_packet'], {}) or {},
        paths=paths,
    )
    atomic_write_json(Path(args.out), packet)
    print(json.dumps({
        'status': 'pass',
        'packet_hash': packet['packet_hash'],
        'source_ref_count': len(packet['source_refs']),
        'scanner_observation_count': len(packet['scanner_observations']),
        'unavailable_fact_count': len(packet['unavailable_facts']),
        'out': str(args.out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
