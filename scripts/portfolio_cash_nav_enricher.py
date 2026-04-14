#!/usr/bin/env python3
"""Build typed cash/NAV facts from the latest redacted IBKR Flex statement."""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe
from portfolio_flex_fetcher import as_float, attr, local_name, parse_flex_response, sha256_bytes

ROOT = Path('/Users/leofitz/.openclaw')
FINANCE = ROOT / 'workspace' / 'finance'
REDACTED_STATEMENT = FINANCE / 'state' / 'portfolio-flex-latest.redacted.xml'
STATEMENT_METADATA = FINANCE / 'state' / 'portfolio-flex-statement-metadata.json'
CASH_NAV_OUT = FINANCE / 'state' / 'portfolio-cash-nav.json'

CASH_FIELDS = {
    'starting_cash': 'startingCash',
    'ending_cash': 'endingCash',
    'ending_settled_cash': 'endingSettledCash',
    'deposits_ytd': 'depositsYTD',
    'withdrawals_ytd': 'withdrawalsYTD',
    'commissions_mtd': 'commissionsMTD',
    'commissions_ytd': 'commissionsYTD',
    'broker_interest_mtd': 'brokerInterestMTD',
    'broker_interest_ytd': 'brokerInterestYTD',
    'dividends_mtd': 'dividendsMTD',
    'dividends_ytd': 'dividendsYTD',
    'net_trades_sales_mtd': 'netTradesSalesMTD',
    'net_trades_purchases_mtd': 'netTradesPurchasesMTD',
}
EQUITY_FIELDS = {
    'cash': 'cash',
    'stock': 'stock',
    'stock_long': 'stockLong',
    'stock_short': 'stockShort',
    'options': 'options',
    'options_long': 'optionsLong',
    'options_short': 'optionsShort',
    'dividend_accruals': 'dividendAccruals',
    'interest_accruals': 'interestAccruals',
    'total': 'total',
    'total_long': 'totalLong',
    'total_short': 'totalShort',
}


class MissingMetricAttrs(Exception):
    def __init__(self, section: str, missing: list[str]):
        self.section = section
        self.missing = sorted(set(missing))
        super().__init__(f'{section} missing metric attrs: {", ".join(self.missing)}')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def required_float(row: ET.Element, name: str) -> float:
    value = attr(row, name)
    if str(value).strip() == '':
        raise MissingMetricAttrs(local_name(row.tag), [name])
    try:
        return float(str(value).replace(',', ''))
    except Exception as exc:
        raise MissingMetricAttrs(local_name(row.tag), [name]) from exc


def section_counts(root: ET.Element) -> dict[str, int]:
    counts = {
        'CashReportCurrency': 0,
        'EquitySummaryInBase': 0,
        'EquitySummaryByReportDateInBase': 0,
    }
    for elem in root.iter():
        tag = local_name(elem.tag)
        if tag in counts:
            counts[tag] += 1
    return counts


def base_payload(
    *,
    metadata_path: Path,
    redacted_path: Path,
    metadata: dict[str, Any] | None,
    source_hash: str | None,
    data_status: str,
    quality: str,
    confidence: str,
    blocking_reasons: list[str] | None = None,
) -> dict[str, Any]:
    return {
        'generated_at': now_iso(),
        'source': 'IBKR Flex Web Service',
        'data_status': data_status,
        'quality': quality,
        'confidence': confidence,
        'source_redacted_sha256': source_hash,
        'source_statement_from': (metadata or {}).get('statement_from'),
        'source_statement_to': (metadata or {}).get('statement_to'),
        'source_metadata_path': str(metadata_path),
        'redacted_statement_path': str(redacted_path),
        'sections': {
            'CashReportCurrency': 0,
            'EquitySummaryInBase': 0,
            'EquitySummaryByReportDateInBase': 0,
        },
        'cash': None,
        'nav': None,
        'exposure': None,
        'metric_sources': {},
        'blocking_reasons': blocking_reasons or [],
    }


def latest_equity_row(root: ET.Element) -> ET.Element | None:
    rows = [row for row in root.iter() if local_name(row.tag) == 'EquitySummaryByReportDateInBase']
    if not rows:
        return None
    return max(rows, key=lambda row: attr(row, 'reportDate'))


def cash_row(root: ET.Element) -> ET.Element | None:
    for row in root.iter():
        if local_name(row.tag) == 'CashReportCurrency':
            return row
    return None


def metric_source(section: str, attrs: list[str]) -> dict[str, Any]:
    return {
        'source_section': section,
        'source_attrs': attrs,
        'confidence': 'exact',
    }


def parse_cash(row: ET.Element) -> tuple[dict[str, Any], dict[str, Any]]:
    cash = {
        'currency': attr(row, 'currency') or 'UNKNOWN',
        'confidence': 'exact',
    }
    sources = {}
    for key, source_attr in CASH_FIELDS.items():
        cash[key] = round(required_float(row, source_attr), 2)
        sources[f'cash.{key}'] = metric_source('CashReportCurrency', [source_attr])
    return cash, sources


def parse_nav(row: ET.Element) -> tuple[dict[str, Any], dict[str, Any]]:
    nav = {
        'currency': attr(row, 'currency') or 'UNKNOWN',
        'report_date': attr(row, 'reportDate') or None,
        'confidence': 'exact',
    }
    sources = {}
    for key, source_attr in EQUITY_FIELDS.items():
        nav[key] = round(required_float(row, source_attr), 2)
        sources[f'nav.{key}'] = metric_source('EquitySummaryByReportDateInBase', [source_attr])
    return nav, sources


def build_exposure(nav: dict[str, Any]) -> dict[str, Any]:
    total = nav.get('total') or 0
    stock_long = abs(nav.get('stock_long') or 0)
    stock_short = abs(nav.get('stock_short') or 0)
    options_long = abs(nav.get('options_long') or 0)
    options_short = abs(nav.get('options_short') or 0)
    gross = round(stock_long + stock_short + options_long + options_short, 2)
    return {
        'gross_exposure': gross,
        'net_liquidation_value': round(total, 2),
        'cash': nav.get('cash'),
        'stock_exposure': nav.get('stock'),
        'option_exposure': nav.get('options'),
        'cash_ratio': round((nav.get('cash') or 0) / total, 4) if total else None,
        'gross_exposure_ratio': round(gross / total, 4) if total else None,
        'confidence': 'exact',
    }


def build_cash_nav(
    *,
    redacted_path: Path = REDACTED_STATEMENT,
    metadata_path: Path = STATEMENT_METADATA,
) -> tuple[dict[str, Any], int]:
    metadata = load_json_safe(metadata_path, {}) or {}
    if not redacted_path.exists():
        return base_payload(
            metadata_path=metadata_path,
            redacted_path=redacted_path,
            metadata=metadata,
            source_hash=metadata.get('redacted_sha256'),
            data_status='error',
            quality='error',
            confidence='not_available',
            blocking_reasons=['missing_redacted_statement'],
        ), 1
    raw = redacted_path.read_bytes()
    actual_hash = sha256_bytes(raw)
    expected_hash = metadata.get('redacted_sha256')
    if expected_hash and expected_hash != actual_hash:
        return base_payload(
            metadata_path=metadata_path,
            redacted_path=redacted_path,
            metadata=metadata,
            source_hash=actual_hash,
            data_status='stale_source',
            quality='stale',
            confidence='not_available',
            blocking_reasons=['source_hash_mismatch'],
        ), 1
    root = parse_flex_response(raw)
    counts = section_counts(root)
    c_row = cash_row(root)
    e_row = latest_equity_row(root)
    if c_row is None or e_row is None:
        payload = base_payload(
            metadata_path=metadata_path,
            redacted_path=redacted_path,
            metadata=metadata,
            source_hash=actual_hash,
            data_status='cash_nav_unavailable',
            quality='unavailable',
            confidence='section_missing',
        )
        payload['sections'] = counts
        return payload, 0
    payload = base_payload(
        metadata_path=metadata_path,
        redacted_path=redacted_path,
        metadata=metadata,
        source_hash=actual_hash,
        data_status='fresh',
        quality='fresh',
        confidence='exact',
    )
    payload['sections'] = counts
    try:
        cash, cash_sources = parse_cash(c_row)
        nav, nav_sources = parse_nav(e_row)
        payload['cash'] = cash
        payload['nav'] = nav
        payload['exposure'] = build_exposure(nav)
        payload['metric_sources'] = {**cash_sources, **nav_sources}
    except MissingMetricAttrs as exc:
        payload = base_payload(
            metadata_path=metadata_path,
            redacted_path=redacted_path,
            metadata=metadata,
            source_hash=actual_hash,
            data_status='cash_nav_unavailable',
            quality='unavailable',
            confidence='not_available',
            blocking_reasons=[f'missing_metric_attrs:{exc.section}:{",".join(exc.missing)}'],
        )
        payload['sections'] = counts
    return payload, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build typed Flex cash/NAV facts.')
    parser.add_argument('--redacted-xml', default=str(REDACTED_STATEMENT))
    parser.add_argument('--metadata', default=str(STATEMENT_METADATA))
    parser.add_argument('--out', default=str(CASH_NAV_OUT))
    args = parser.parse_args(argv)
    payload, rc = build_cash_nav(
        redacted_path=Path(args.redacted_xml),
        metadata_path=Path(args.metadata),
    )
    atomic_write_json(Path(args.out), payload)
    print(json.dumps({
        'status': 'pass' if rc == 0 else 'fail',
        'data_status': payload['data_status'],
        'quality': payload['quality'],
        'blocking_reasons': payload['blocking_reasons'],
        'out': str(args.out),
    }, ensure_ascii=False))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
