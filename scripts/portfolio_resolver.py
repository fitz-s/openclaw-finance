#!/usr/bin/env python3
"""Resolve the current finance portfolio from Client Portal and Flex sources."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
CLIENT_PORTAL = FINANCE / 'state' / 'portfolio.json'
CLIENT_HELD = FINANCE / 'state' / 'held-tickers.json'
FLEX_PORTFOLIO = FINANCE / 'state' / 'portfolio-flex.json'
PERFORMANCE = FINANCE / 'state' / 'portfolio-performance.json'
CASH_NAV = FINANCE / 'state' / 'portfolio-cash-nav.json'
OPTION_RISK = FINANCE / 'state' / 'portfolio-option-risk.json'
RESOLVED_PORTFOLIO = FINANCE / 'state' / 'portfolio-resolved.json'
RESOLVED_HELD = FINANCE / 'state' / 'held-tickers-resolved.json'
SOURCE_STATUS = FINANCE / 'state' / 'portfolio-source-status.json'
CLIENT_MAX_AGE_HOURS = 24
FLEX_MAX_AGE_HOURS = 36
ENRICHMENT_ARTIFACTS = {
    'performance': {
        'path': PERFORMANCE,
        'fresh_status': 'fresh',
        'quality_key': 'performance_fresh',
    },
    'cash_nav': {
        'path': CASH_NAV,
        'fresh_status': 'fresh',
        'quality_key': 'cash_nav_fresh',
    },
    'option_risk': {
        'path': OPTION_RISK,
        'fresh_status': 'fresh',
        'quality_key': 'option_risk_fresh',
    },
}


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def age_hours(payload: dict[str, Any], now: datetime) -> float | None:
    fetched = parse_dt(payload.get('fetched_at'))
    if fetched is None:
        return None
    return round((now - fetched).total_seconds() / 3600, 2)


def client_portal_invalidated(portfolio: dict[str, Any], held: dict[str, Any]) -> bool:
    if held.get('data_status') != 'ibkr_unavailable':
        return False
    failed_at = parse_dt(held.get('updated_at'))
    fetched_at = parse_dt(portfolio.get('fetched_at'))
    if failed_at is None:
        return False
    if fetched_at is None:
        return True
    return failed_at >= fetched_at


def usable_client_portal(portfolio: dict[str, Any], held: dict[str, Any], now: datetime) -> bool:
    age = age_hours(portfolio, now)
    return (
        portfolio.get('source') == 'IBKR Client Portal API'
        and isinstance(portfolio.get('stocks'), list)
        and age is not None
        and age <= CLIENT_MAX_AGE_HOURS
        and not client_portal_invalidated(portfolio, held)
    )


def usable_flex(portfolio: dict[str, Any], now: datetime) -> bool:
    age = age_hours(portfolio, now)
    return (
        portfolio.get('source') == 'IBKR Flex Web Service'
        and portfolio.get('data_status') == 'fresh'
        and isinstance(portfolio.get('stocks'), list)
        and age is not None
        and age <= FLEX_MAX_AGE_HOURS
    )


def build_held_tickers(portfolio: dict[str, Any], source: str, now: datetime) -> dict[str, Any]:
    exposure: dict[str, Any] = {}
    for stock in portfolio.get('stocks', []):
        sym = stock.get('symbol')
        if not sym:
            continue
        exposure.setdefault(sym, {'stock_qty': 0, 'stock_value': 0, 'options': [], 'total_exposure': 0, 'direction': 'long'})
        exposure[sym]['stock_qty'] = stock.get('quantity', 0)
        exposure[sym]['stock_value'] = stock.get('mkt_value', 0)
        exposure[sym]['total_exposure'] += abs(stock.get('mkt_value', 0))
        if stock.get('quantity', 0) < 0:
            exposure[sym]['direction'] = 'short'
    for option in portfolio.get('options', []):
        sym = option.get('underlying') or option.get('symbol')
        if not sym:
            continue
        exposure.setdefault(sym, {'stock_qty': 0, 'stock_value': 0, 'options': [], 'total_exposure': 0, 'direction': 'long'})
        exposure[sym]['options'].append({
            'type': option.get('put_or_call'),
            'strike': option.get('strike'),
            'expiry': option.get('expiry'),
            'dte': option.get('dte'),
            'qty': option.get('quantity'),
            'value': option.get('mkt_value'),
            'pnl': option.get('unrealized_pnl'),
        })
        exposure[sym]['total_exposure'] += abs(option.get('mkt_value', 0))
    return {
        'updated_at': now.isoformat(),
        'data_status': 'fresh',
        'source': source,
        'tickers': exposure,
        'scanner_boost_note': 'Resolved portfolio holdings; scanner boosts held tickers only when data_status=fresh.',
    }


def enrichment_ref(
    name: str,
    payload: dict[str, Any],
    path: Path,
    selected_hash: str | None,
) -> dict[str, Any]:
    exists = bool(payload)
    data_status = payload.get('data_status') if exists else 'missing'
    quality = payload.get('quality') if exists else 'missing'
    source_hash = payload.get('source_redacted_sha256') if exists else None
    fresh_status = ENRICHMENT_ARTIFACTS[name]['fresh_status']
    reasons: list[str] = []
    if not exists:
        reasons.append('missing_artifact')
    if exists and data_status != fresh_status:
        reasons.append(f'data_status:{data_status}')
    if exists and not source_hash:
        reasons.append('missing_source_hash')
    if exists and source_hash and not selected_hash:
        reasons.append('selected_source_hash_missing')
    if exists and source_hash and selected_hash and source_hash != selected_hash:
        reasons.append('source_hash_mismatch')
    for reason in payload.get('blocking_reasons', []) if exists else []:
        reasons.append(str(reason))
    fresh = bool(exists and data_status == fresh_status and not reasons)
    return {
        'path': str(path),
        'exists': exists,
        'fresh': fresh,
        'data_status': data_status,
        'quality': quality,
        'confidence': payload.get('confidence') if exists else None,
        'generated_at': payload.get('generated_at') if exists else None,
        'source_redacted_sha256': source_hash,
        'source_statement_from': payload.get('source_statement_from') if exists else None,
        'source_statement_to': payload.get('source_statement_to') if exists else None,
        'blocking_reasons': sorted(set(reasons)),
    }


def build_enrichment_context(
    selected: dict[str, Any],
    enrichments: dict[str, dict[str, Any]],
    enrichment_paths: dict[str, Path],
) -> tuple[dict[str, bool], dict[str, dict[str, Any]]]:
    selected_hash = selected.get('source_redacted_sha256')
    refs = {
        name: enrichment_ref(name, payload, enrichment_paths[name], selected_hash)
        for name, payload in enrichments.items()
    }
    source_quality = {
        'positions_fresh': selected.get('data_status') == 'fresh',
        'performance_fresh': refs['performance']['fresh'],
        'cash_nav_fresh': refs['cash_nav']['fresh'],
        'option_risk_fresh': refs['option_risk']['fresh'],
    }
    return source_quality, refs


def attach_enrichment_context(
    selected: dict[str, Any],
    enrichments: dict[str, dict[str, Any]],
    enrichment_paths: dict[str, Path],
) -> dict[str, Any]:
    out = dict(selected)
    source_quality, refs = build_enrichment_context(out, enrichments, enrichment_paths)
    out['source_quality'] = source_quality
    out['enrichment_refs'] = refs
    return out


def unavailable(now: datetime, reasons: list[str], enrichment_paths: dict[str, Path]) -> tuple[dict[str, Any], dict[str, Any]]:
    portfolio = {
        'resolved_at': now.isoformat(),
        'source': None,
        'data_status': 'unavailable',
        'stale_reason': '; '.join(reasons),
        'summary': {
            'stock_positions': 0,
            'option_positions': 0,
            'total_stock_value': 0,
            'total_option_value': 0,
            'total_portfolio_value': 0,
            'total_unrealized_pnl': 0,
            'options_by_expiry': {},
        },
        'stocks': [],
        'options': [],
        'source_quality': {
            'positions_fresh': False,
            'performance_fresh': False,
            'cash_nav_fresh': False,
            'option_risk_fresh': False,
        },
        'enrichment_refs': {
            name: enrichment_ref(name, {}, enrichment_paths[name], None)
            for name in ENRICHMENT_ARTIFACTS
        },
    }
    held = {
        'updated_at': now.isoformat(),
        'data_status': 'portfolio_unavailable',
        'tickers': {},
        'scanner_boost_note': 'No fresh portfolio source; held-ticker boost disabled.',
        'stale_reason': '; '.join(reasons),
    }
    return portfolio, held


def resolve(
    client: dict[str, Any],
    held: dict[str, Any],
    flex: dict[str, Any],
    enrichments: dict[str, dict[str, Any]],
    enrichment_paths: dict[str, Path],
    now: datetime,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], int]:
    reasons = []
    if usable_client_portal(client, held, now):
        selected = dict(client)
        selected['resolved_at'] = now.isoformat()
        selected['data_status'] = 'fresh'
        selected['selected_source'] = 'client_portal'
        selected = attach_enrichment_context(selected, enrichments, enrichment_paths)
        resolved_held = build_held_tickers(selected, 'client_portal', now)
        return selected, resolved_held, status_payload(now, 'pass', 'client_portal', reasons, selected), 0
    reasons.append('client_portal_unavailable_or_stale')
    if usable_flex(flex, now):
        selected = dict(flex)
        selected['resolved_at'] = now.isoformat()
        selected['selected_source'] = 'flex'
        selected = attach_enrichment_context(selected, enrichments, enrichment_paths)
        resolved_held = build_held_tickers(selected, 'flex', now)
        return selected, resolved_held, status_payload(now, 'pass', 'flex', reasons, selected), 0
    reasons.append('flex_unavailable_or_stale')
    portfolio, resolved_held = unavailable(now, reasons, enrichment_paths)
    return portfolio, resolved_held, status_payload(now, 'fail', None, reasons, portfolio), 1


def status_payload(now: datetime, status: str, selected: str | None, reasons: list[str], portfolio: dict[str, Any]) -> dict[str, Any]:
    return {
        'generated_at': now.isoformat(),
        'status': status,
        'selected_source': selected,
        'blocking_reasons': reasons if status != 'pass' else [],
        'source_quality': portfolio.get('source_quality', {}),
        'enrichment_refs': portfolio.get('enrichment_refs', {}),
        'source_priority': ['client_portal', 'flex'],
        'portfolio_path': str(RESOLVED_PORTFOLIO),
        'held_tickers_path': str(RESOLVED_HELD),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Resolve finance portfolio source.')
    parser.add_argument('--client-portal', default=str(CLIENT_PORTAL))
    parser.add_argument('--client-held', default=str(CLIENT_HELD))
    parser.add_argument('--flex', default=str(FLEX_PORTFOLIO))
    parser.add_argument('--performance', default=str(PERFORMANCE))
    parser.add_argument('--cash-nav', default=str(CASH_NAV))
    parser.add_argument('--option-risk', default=str(OPTION_RISK))
    parser.add_argument('--portfolio-out', default=str(RESOLVED_PORTFOLIO))
    parser.add_argument('--held-out', default=str(RESOLVED_HELD))
    parser.add_argument('--status-out', default=str(SOURCE_STATUS))
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    enrichment_paths = {
        'performance': Path(args.performance),
        'cash_nav': Path(args.cash_nav),
        'option_risk': Path(args.option_risk),
    }
    portfolio, held, status, rc = resolve(
        load_json_safe(Path(args.client_portal), {}) or {},
        load_json_safe(Path(args.client_held), {}) or {},
        load_json_safe(Path(args.flex), {}) or {},
        {
            'performance': load_json_safe(enrichment_paths['performance'], {}) or {},
            'cash_nav': load_json_safe(enrichment_paths['cash_nav'], {}) or {},
            'option_risk': load_json_safe(enrichment_paths['option_risk'], {}) or {},
        },
        enrichment_paths,
        now,
    )
    atomic_write_json(Path(args.portfolio_out), portfolio)
    atomic_write_json(Path(args.held_out), held)
    status['portfolio_path'] = str(args.portfolio_out)
    status['held_tickers_path'] = str(args.held_out)
    atomic_write_json(Path(args.status_out), status)
    print(json.dumps({
        'status': status['status'],
        'selected_source': status['selected_source'],
        'blocking_reasons': status['blocking_reasons'],
        'portfolio_path': str(args.portfolio_out),
    }, ensure_ascii=False))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
