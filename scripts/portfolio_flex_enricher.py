#!/usr/bin/env python3
"""Build typed performance facts from the latest redacted IBKR Flex statement."""
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
PORTFOLIO_FLEX = FINANCE / 'state' / 'portfolio-flex.json'
PERFORMANCE_OUT = FINANCE / 'state' / 'portfolio-performance.json'

MTM_FIELDS = {
    'transaction_mtm': 'transactionMtm',
    'prior_open_mtm': 'priorOpenMtm',
    'commissions': 'commissions',
    'other': 'other',
    'total': 'total',
    'total_with_accruals': 'totalWithAccruals',
}
CHANGE_FIELDS = {
    'prior_period_value': 'priorPeriodValue',
    'transactions': 'transactions',
    'mtm_prior_period_positions': 'mtmPriorPeriodPositions',
    'mtm_transactions': 'mtmTransactions',
    'end_of_period_value': 'endOfPeriodValue',
}


class MissingMetricAttrs(Exception):
    """Raised when a present performance section omits required numeric attrs."""

    def __init__(self, section: str, missing: list[str]):
        self.section = section
        self.missing = sorted(set(missing))
        super().__init__(f'{section} missing metric attrs: {", ".join(self.missing)}')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_summary(confidence: str) -> dict[str, Any]:
    return {
        'transaction_mtm': None,
        'prior_open_mtm': None,
        'commissions': None,
        'other': None,
        'total': None,
        'total_with_accruals': None,
        'confidence': confidence,
        'metric_sources': {
            key: {
                'source_section': None,
                'source_attrs': [],
                'confidence': confidence,
            }
            for key in MTM_FIELDS
        },
    }


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
            'MTMPerformanceSummaryUnderlying': 0,
            'FIFOPerformanceSummaryInBase': 0,
            'MTMPerformanceSummaryInBase': 0,
            'ChangeInPositionValue': 0,
        },
        'portfolio_summary': empty_summary(confidence),
        'underlyings': {},
        'change_in_position_value': [],
        'pnl_policy': {
            'open_position_unrealized_pnl_ignored': True,
            'reason': 'Performance facts use Flex performance sections only; OpenPosition unrealized P&L is not treated as authoritative.',
        },
        'blocking_reasons': blocking_reasons or [],
    }


def section_counts(root: ET.Element) -> dict[str, int]:
    counts = {
        'MTMPerformanceSummaryUnderlying': 0,
        'FIFOPerformanceSummaryInBase': 0,
        'MTMPerformanceSummaryInBase': 0,
        'ChangeInPositionValue': 0,
    }
    for elem in root.iter():
        tag = local_name(elem.tag)
        if tag in counts:
            counts[tag] += 1
    return counts


def metric_source(section: str, attrs: list[str], confidence: str = 'exact') -> dict[str, Any]:
    return {
        'source_section': section,
        'source_attrs': attrs,
        'confidence': confidence,
    }


def missing_attrs(row: ET.Element, names: list[str]) -> list[str]:
    lower = {key.lower(): value for key, value in row.attrib.items()}
    return [
        name for name in names
        if name.lower() not in lower or str(lower[name.lower()]).strip() == ''
    ]


def required_float(row: ET.Element, name: str) -> float:
    value = attr(row, name)
    if str(value).strip() == '':
        raise MissingMetricAttrs(local_name(row.tag), [name])
    return as_float(value)


def symbol_for(row: ET.Element) -> str:
    return (
        attr(row, 'underlyingSymbol')
        or attr(row, 'symbol')
        or attr(row, 'description')
        or 'UNKNOWN'
    )


def is_aggregate_total_row(row: ET.Element) -> bool:
    description = attr(row, 'description').strip().lower()
    symbol = attr(row, 'symbol').strip()
    underlying = attr(row, 'underlyingSymbol').strip()
    asset_class = attr(row, 'assetCategory').strip()
    return description in {'total p/l', 'total pnl', 'total p&l'} and not symbol and not underlying and not asset_class


def parse_mtm_underlyings(root: ET.Element) -> tuple[dict[str, Any], dict[str, float], dict[str, float] | None]:
    underlyings: dict[str, dict[str, Any]] = {}
    summary = {key: 0.0 for key in MTM_FIELDS}
    aggregate_summary: dict[str, float] | None = None
    for row in root.iter():
        if local_name(row.tag) != 'MTMPerformanceSummaryUnderlying':
            continue
        missing = missing_attrs(row, list(MTM_FIELDS.values()))
        if missing:
            raise MissingMetricAttrs('MTMPerformanceSummaryUnderlying', missing)
        if is_aggregate_total_row(row):
            aggregate_summary = {
                key: round(required_float(row, source_attr), 2)
                for key, source_attr in MTM_FIELDS.items()
            }
            continue
        symbol = symbol_for(row)
        item = underlyings.setdefault(symbol, {
            'symbol': symbol,
            'asset_classes': [],
            'row_count': 0,
            'transaction_mtm': 0.0,
            'prior_open_mtm': 0.0,
            'commissions': 0.0,
            'other': 0.0,
            'total': 0.0,
            'total_with_accruals': 0.0,
            'report_dates': [],
            'confidence': 'exact',
            'source_rows': [],
        })
        asset_class = attr(row, 'assetCategory')
        if asset_class and asset_class not in item['asset_classes']:
            item['asset_classes'].append(asset_class)
        report_date = attr(row, 'reportDate')
        if report_date and report_date not in item['report_dates']:
            item['report_dates'].append(report_date)
        item['row_count'] += 1
        for out_key, source_attr in MTM_FIELDS.items():
            value = round(required_float(row, source_attr), 2)
            item[out_key] = round(item[out_key] + value, 2)
            summary[out_key] = round(summary[out_key] + value, 2)
        item['source_rows'].append({
            'source_section': 'MTMPerformanceSummaryUnderlying',
            'source_attrs': sorted(row.attrib),
        })
    for item in underlyings.values():
        item['asset_classes'] = sorted(item['asset_classes'])
        item['report_dates'] = sorted(item['report_dates'])
    return dict(sorted(underlyings.items())), summary, aggregate_summary


def parse_change_in_position(root: ET.Element) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in root.iter():
        if local_name(row.tag) != 'ChangeInPositionValue':
            continue
        missing = missing_attrs(row, list(CHANGE_FIELDS.values()))
        if missing:
            raise MissingMetricAttrs('ChangeInPositionValue', missing)
        out = {
            'asset_category': attr(row, 'assetCategory') or 'UNKNOWN',
            'currency': attr(row, 'currency') or 'UNKNOWN',
            'source_section': 'ChangeInPositionValue',
            'source_attrs': sorted(row.attrib),
        }
        for out_key, source_attr in CHANGE_FIELDS.items():
            out[out_key] = round(required_float(row, source_attr), 2)
        rows.append(out)
    return rows


def build_performance(
    *,
    redacted_path: Path = REDACTED_STATEMENT,
    metadata_path: Path = STATEMENT_METADATA,
    portfolio_path: Path = PORTFOLIO_FLEX,
) -> tuple[dict[str, Any], int]:
    metadata = load_json_safe(metadata_path, {}) or {}
    portfolio = load_json_safe(portfolio_path, {}) or {}
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
    expected_hashes = [
        value for value in (
            metadata.get('redacted_sha256'),
            portfolio.get('source_redacted_sha256'),
        )
        if value
    ]
    if expected_hashes and any(value != actual_hash for value in expected_hashes):
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
    if counts['MTMPerformanceSummaryUnderlying'] == 0 and counts['FIFOPerformanceSummaryInBase'] == 0 and counts['MTMPerformanceSummaryInBase'] == 0:
        payload = base_payload(
            metadata_path=metadata_path,
            redacted_path=redacted_path,
            metadata=metadata,
            source_hash=actual_hash,
            data_status='performance_unavailable',
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
        underlyings, row_sum_values, aggregate_values = parse_mtm_underlyings(root)
        summary_values = dict(row_sum_values)
        aggregate_diff: dict[str, float] | None = None
        if aggregate_values:
            aggregate_diff = {
                key: round(aggregate_values[key] - row_sum_values[key], 2)
                for key in MTM_FIELDS
            }
            for key in ('total', 'total_with_accruals'):
                summary_values[key] = aggregate_values[key]
        summary = empty_summary('exact')
        for key, value in summary_values.items():
            summary[key] = round(value, 2)
            summary['metric_sources'][key] = metric_source('MTMPerformanceSummaryUnderlying', [MTM_FIELDS[key]])
        if aggregate_diff is not None:
            summary['aggregate_total_row_diff'] = aggregate_diff
        payload['portfolio_summary'] = summary
        payload['underlyings'] = underlyings
        payload['change_in_position_value'] = parse_change_in_position(root)
    except MissingMetricAttrs as exc:
        payload = base_payload(
            metadata_path=metadata_path,
            redacted_path=redacted_path,
            metadata=metadata,
            source_hash=actual_hash,
            data_status='performance_unavailable',
            quality='unavailable',
            confidence='not_available',
            blocking_reasons=[f'missing_metric_attrs:{exc.section}:{",".join(exc.missing)}'],
        )
        payload['sections'] = counts
    return payload, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build typed Flex portfolio performance facts.')
    parser.add_argument('--redacted-xml', default=str(REDACTED_STATEMENT))
    parser.add_argument('--metadata', default=str(STATEMENT_METADATA))
    parser.add_argument('--portfolio', default=str(PORTFOLIO_FLEX))
    parser.add_argument('--out', default=str(PERFORMANCE_OUT))
    args = parser.parse_args(argv)
    payload, rc = build_performance(
        redacted_path=Path(args.redacted_xml),
        metadata_path=Path(args.metadata),
        portfolio_path=Path(args.portfolio),
    )
    atomic_write_json(Path(args.out), payload)
    print(json.dumps({
        'status': 'pass' if rc == 0 else 'fail',
        'data_status': payload['data_status'],
        'quality': payload['quality'],
        'underlying_count': len(payload['underlyings']),
        'blocking_reasons': payload['blocking_reasons'],
        'out': str(args.out),
    }, ensure_ascii=False))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
