#!/usr/bin/env python3
"""Build typed option-risk facts from the latest redacted IBKR Flex statement."""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe
from portfolio_flex_fetcher import as_float, attr, days_to_expiry, local_name, parse_expiry, parse_flex_response, sha256_bytes

ROOT = Path('/Users/leofitz/.openclaw')
FINANCE = ROOT / 'workspace' / 'finance'
REDACTED_STATEMENT = FINANCE / 'state' / 'portfolio-flex-latest.redacted.xml'
STATEMENT_METADATA = FINANCE / 'state' / 'portfolio-flex-statement-metadata.json'
PORTFOLIO_FLEX = FINANCE / 'state' / 'portfolio-flex.json'
OPTION_RISK_OUT = FINANCE / 'state' / 'portfolio-option-risk.json'

OPTION_SECTION_TAGS = {'OptionEAE'}
PENDING_SECTION_TAGS = {'PendingExercises', 'PendingExcercises'}
DTE_BUCKETS = [
    ('expired', lambda dte: dte < 0),
    ('0_7', lambda dte: 0 <= dte <= 7),
    ('8_14', lambda dte: 8 <= dte <= 14),
    ('15_30', lambda dte: 15 <= dte <= 30),
    ('31_60', lambda dte: 31 <= dte <= 60),
    ('61_180', lambda dte: 61 <= dte <= 180),
    ('181_plus', lambda dte: dte >= 181),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def section_counts(root: ET.Element) -> dict[str, int]:
    counts = {
        'OpenPosition': 0,
        'SecurityInfo': 0,
        'OptionEAE': 0,
        'PendingExercises': 0,
        'PendingExcercises': 0,
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
            'OpenPosition': 0,
            'SecurityInfo': 0,
            'OptionEAE': 0,
            'PendingExercises': 0,
            'PendingExcercises': 0,
        },
        'option_count': 0,
        'dte_buckets': empty_dte_buckets(),
        'options': [],
        'near_expiry_options': [],
        'large_decay_risk': [],
        'exercise_assignment': {
            'status': 'unknown_section_missing',
            'option_eae_section_present': False,
            'pending_exercises_section_present': False,
            'option_eae_event_count': None,
            'pending_exercise_event_count': None,
            'events': [],
            'source_sections': [],
            'claim': 'Exercise/assignment risk unavailable because source sections are absent.',
        },
        'quality_notes': [],
        'blocking_reasons': blocking_reasons or [],
    }


class MissingOptionAttrs(Exception):
    def __init__(self, missing: list[str]):
        self.missing = sorted(set(missing))
        super().__init__(f'OpenPosition option missing attrs: {", ".join(self.missing)}')


def empty_dte_buckets() -> dict[str, int]:
    return {
        'expired': 0,
        '0_7': 0,
        '8_14': 0,
        '15_30': 0,
        '31_60': 0,
        '61_180': 0,
        '181_plus': 0,
        'unknown': 0,
    }


def option_open_positions(root: ET.Element) -> list[ET.Element]:
    rows = []
    for row in root.iter():
        if local_name(row.tag) != 'OpenPosition':
            continue
        if 'OPT' not in attr(row, 'assetCategory').upper() and not attr(row, 'putCall'):
            continue
        position_raw = attr(row, 'position')
        if str(position_raw).strip() == '':
            rows.append(row)
            continue
        try:
            position = float(str(position_raw).replace(',', ''))
        except Exception:
            rows.append(row)
            continue
        if position != 0:
            rows.append(row)
    return rows


def required_option_float(row: ET.Element, name: str) -> float:
    value = attr(row, name)
    if str(value).strip() == '':
        raise MissingOptionAttrs([name])
    try:
        return float(str(value).replace(',', ''))
    except Exception as exc:
        raise MissingOptionAttrs([name]) from exc


def stock_prices(root: ET.Element) -> dict[str, float]:
    prices: dict[str, float] = {}
    for row in root.iter():
        if local_name(row.tag) != 'OpenPosition':
            continue
        if 'OPT' in attr(row, 'assetCategory').upper():
            continue
        symbol = attr(row, 'symbol')
        price = as_float(attr(row, 'markPrice'))
        if symbol and price:
            prices[symbol] = price
    return prices


def security_info_by_conid(root: ET.Element) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in root.iter():
        if local_name(row.tag) != 'SecurityInfo':
            continue
        conid = attr(row, 'conid')
        if not conid:
            continue
        out[conid] = {
            'source_section': 'SecurityInfo',
            'settlement_policy_method': attr(row, 'settlementPolicyMethod') or None,
            'underlying_category': attr(row, 'underlyingCategory') or None,
            'listing_exchange': attr(row, 'listingExchange') or None,
        }
    return out


def dte_bucket(dte: int | None) -> str:
    if dte is None:
        return 'unknown'
    for name, predicate in DTE_BUCKETS:
        if predicate(dte):
            return name
    return 'unknown'


def option_moneyness(row: ET.Element, prices: dict[str, float]) -> dict[str, Any]:
    underlying = attr(row, 'underlyingSymbol') or attr(row, 'symbol')
    underlying_price = prices.get(underlying)
    strike = as_float(attr(row, 'strike'))
    right = attr(row, 'putCall').lower()
    if not underlying_price or not strike or not right:
        return {
            'moneyness_status': 'unknown',
            'underlying_price': None,
            'moneyness_pct': None,
            'source': 'underlying_price_unavailable',
        }
    if right.startswith('c'):
        distance = (underlying_price - strike) / strike
        status = 'itm' if underlying_price > strike else 'otm' if underlying_price < strike else 'atm'
    elif right.startswith('p'):
        distance = (strike - underlying_price) / strike
        status = 'itm' if underlying_price < strike else 'otm' if underlying_price > strike else 'atm'
    else:
        return {
            'moneyness_status': 'unknown',
            'underlying_price': underlying_price,
            'moneyness_pct': None,
            'source': 'option_right_unavailable',
        }
    return {
        'moneyness_status': status,
        'underlying_price': round(underlying_price, 4),
        'moneyness_pct': round(distance, 4),
        'source': 'held_underlying_open_position_mark_price',
    }


def parse_option(row: ET.Element, *, now: datetime, prices: dict[str, float], security_info: dict[str, dict[str, Any]]) -> dict[str, Any]:
    expiry_raw = attr(row, 'expiry', 'expirationDate')
    expiry = parse_expiry(expiry_raw)
    missing = [
        name for name in ('position', 'positionValue', 'markPrice', 'strike', 'multiplier')
        if str(attr(row, name)).strip() == ''
    ]
    if str(expiry_raw).strip() == '':
        missing.append('expiry')
    if str(attr(row, 'putCall')).strip() == '':
        missing.append('putCall')
    if missing:
        raise MissingOptionAttrs(missing)
    dte = days_to_expiry(expiry, now)
    if dte is None:
        raise MissingOptionAttrs(['expiry'])
    quantity = required_option_float(row, 'position')
    market_value = required_option_float(row, 'positionValue')
    right = attr(row, 'putCall').lower()
    conid = attr(row, 'conid')
    item = {
        'symbol': attr(row, 'symbol') or '?',
        'description': attr(row, 'description') or attr(row, 'symbol') or '?',
        'conid': conid or None,
        'underlying': attr(row, 'underlyingSymbol') or attr(row, 'symbol') or '?',
        'quantity': quantity,
        'direction': 'long' if quantity > 0 else 'short',
        'expiry': expiry,
        'dte': dte,
        'dte_bucket': dte_bucket(dte),
        'strike': round(required_option_float(row, 'strike'), 4),
        'put_or_call': 'call' if right.startswith('c') else 'put' if right.startswith('p') else None,
        'multiplier': int(round(required_option_float(row, 'multiplier'))),
        'mark_price': round(required_option_float(row, 'markPrice'), 4),
        'market_value': round(market_value, 2),
        'percent_of_nav': round(as_float(attr(row, 'percentOfNAV')), 4),
        'risk_flags': [],
        'source_section': 'OpenPosition',
        'source_attrs': sorted(row.attrib),
    }
    item.update(option_moneyness(row, prices))
    sec = security_info.get(conid)
    if sec:
        item['security_info'] = sec
    else:
        item['security_info'] = None
    if dte is not None and dte <= 14:
        item['risk_flags'].append('near_expiry_14d')
    if quantity < 0:
        item['risk_flags'].append('short_option_assignment_exposure')
    if quantity > 0 and ((dte is not None and dte <= 14) or (dte is not None and dte <= 45 and abs(market_value) >= 100)):
        item['risk_flags'].append('large_decay_watch')
    return item


def child_event_rows(root: ET.Element, section_tags: set[str]) -> list[ET.Element]:
    rows: list[ET.Element] = []
    for section in root.iter():
        if local_name(section.tag) not in section_tags:
            continue
        for child in list(section):
            rows.append(child)
    return rows


def parse_exercise_assignment(root: ET.Element) -> dict[str, Any]:
    counts = section_counts(root)
    option_eae_present = counts['OptionEAE'] > 0
    pending_present = counts['PendingExercises'] > 0 or counts['PendingExcercises'] > 0
    source_sections = []
    if option_eae_present:
        source_sections.append('OptionEAE')
    if counts['PendingExercises'] > 0:
        source_sections.append('PendingExercises')
    if counts['PendingExcercises'] > 0:
        source_sections.append('PendingExcercises')
    events = []
    for row in child_event_rows(root, OPTION_SECTION_TAGS | PENDING_SECTION_TAGS):
        events.append({
            'source_section': local_name(row.tag),
            'symbol': attr(row, 'symbol', 'underlyingSymbol') or None,
            'description': attr(row, 'description') or None,
            'source_attrs': sorted(row.attrib),
        })
    if option_eae_present or pending_present:
        return {
            'status': 'available_events_present' if events else 'available_no_events',
            'option_eae_section_present': option_eae_present,
            'pending_exercises_section_present': pending_present,
            'option_eae_event_count': len(child_event_rows(root, OPTION_SECTION_TAGS)) if option_eae_present else None,
            'pending_exercise_event_count': len(child_event_rows(root, PENDING_SECTION_TAGS)) if pending_present else None,
            'events': events,
            'source_sections': source_sections,
            'claim': 'Exercise/assignment sections are present; no events were found.' if not events else 'Exercise/assignment events found in source sections.',
        }
    return {
        'status': 'unknown_section_missing',
        'option_eae_section_present': False,
        'pending_exercises_section_present': False,
        'option_eae_event_count': None,
        'pending_exercise_event_count': None,
        'events': [],
        'source_sections': [],
        'claim': 'Exercise/assignment risk unavailable because source sections are absent.',
    }


def build_option_risk(
    *,
    redacted_path: Path = REDACTED_STATEMENT,
    metadata_path: Path = STATEMENT_METADATA,
    portfolio_path: Path = PORTFOLIO_FLEX,
    now: datetime | None = None,
) -> tuple[dict[str, Any], int]:
    metadata = load_json_safe(metadata_path, {}) or {}
    portfolio = load_json_safe(portfolio_path, {}) or {}
    portfolio_status = str(portfolio.get('data_status') or '').strip()
    if portfolio_status != 'fresh':
        return base_payload(
            metadata_path=metadata_path,
            redacted_path=redacted_path,
            metadata=metadata,
            source_hash=metadata.get('redacted_sha256') or portfolio.get('source_redacted_sha256'),
            data_status='stale_source',
            quality='stale',
            confidence='not_available',
            blocking_reasons=[f'portfolio_source_not_fresh:{portfolio_status or "missing"}'],
        ), 1
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
    if not expected_hashes:
        return base_payload(
            metadata_path=metadata_path,
            redacted_path=redacted_path,
            metadata=metadata,
            source_hash=actual_hash,
            data_status='stale_source',
            quality='stale',
            confidence='not_available',
            blocking_reasons=['missing_source_hash'],
        ), 1
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
    rows = option_open_positions(root)
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
    if counts['OpenPosition'] == 0:
        payload.update({
            'data_status': 'option_risk_unavailable',
            'quality': 'unavailable',
            'confidence': 'section_missing',
            'blocking_reasons': ['missing_open_position_section'],
        })
        return payload, 0
    current = now or datetime.now(timezone.utc)
    prices = stock_prices(root)
    sec_info = security_info_by_conid(root)
    try:
        options = [
            parse_option(row, now=current, prices=prices, security_info=sec_info)
            for row in rows
        ]
    except MissingOptionAttrs as exc:
        payload.update({
            'data_status': 'option_risk_unavailable',
            'quality': 'unavailable',
            'confidence': 'not_available',
            'blocking_reasons': [f'missing_option_attrs:{",".join(exc.missing)}'],
        })
        return payload, 0
    options.sort(key=lambda item: (item['dte'] if item['dte'] is not None else 99999, item['symbol']))
    buckets = empty_dte_buckets()
    for item in options:
        buckets[item['dte_bucket']] += 1
    payload['option_count'] = len(options)
    payload['dte_buckets'] = buckets
    payload['options'] = options
    payload['near_expiry_options'] = [
        item for item in options
        if item['dte'] is not None and item['dte'] <= 14
    ]
    payload['large_decay_risk'] = [
        item for item in options
        if 'large_decay_watch' in item['risk_flags']
    ]
    payload['exercise_assignment'] = parse_exercise_assignment(root)
    notes = []
    if counts['SecurityInfo'] == 0:
        notes.append('security_info_unavailable')
    if payload['exercise_assignment']['status'] == 'unknown_section_missing':
        notes.append('exercise_assignment_sections_missing')
    if any(item['moneyness_status'] == 'unknown' for item in options):
        notes.append('some_underlying_prices_unavailable_for_moneyness')
    payload['quality_notes'] = notes
    return payload, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build typed Flex option-risk facts.')
    parser.add_argument('--redacted-xml', default=str(REDACTED_STATEMENT))
    parser.add_argument('--metadata', default=str(STATEMENT_METADATA))
    parser.add_argument('--portfolio', default=str(PORTFOLIO_FLEX))
    parser.add_argument('--out', default=str(OPTION_RISK_OUT))
    parser.add_argument('--as-of', help='ISO timestamp for replayable DTE calculations. Defaults to current UTC time.')
    args = parser.parse_args(argv)
    as_of = datetime.fromisoformat(args.as_of) if args.as_of else None
    if as_of and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    payload, rc = build_option_risk(
        redacted_path=Path(args.redacted_xml),
        metadata_path=Path(args.metadata),
        portfolio_path=Path(args.portfolio),
        now=as_of,
    )
    atomic_write_json(Path(args.out), payload)
    print(json.dumps({
        'status': 'pass' if rc == 0 else 'fail',
        'data_status': payload['data_status'],
        'quality': payload['quality'],
        'option_count': payload['option_count'],
        'near_expiry_count': len(payload['near_expiry_options']),
        'large_decay_count': len(payload['large_decay_risk']),
        'exercise_assignment_status': payload['exercise_assignment']['status'],
        'blocking_reasons': payload['blocking_reasons'],
        'out': str(args.out),
    }, ensure_ascii=False))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
