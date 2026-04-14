#!/usr/bin/env python3
"""IBKR Flex Web Service portfolio fetcher.

This is the unattended holdings baseline path. It does not depend on the
Client Portal localhost brokerage session.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from atomic_io import atomic_write_json, load_json_safe

ROOT = Path('/Users/leofitz/.openclaw')
FINANCE = ROOT / 'workspace' / 'finance'
CONFIG = FINANCE / 'state' / 'ibkr-flex-config.json'
PORTFOLIO_FLEX = FINANCE / 'state' / 'portfolio-flex.json'
SOURCE_STATUS = FINANCE / 'state' / 'portfolio-source-status.json'
REDACTED_STATEMENT = FINANCE / 'state' / 'portfolio-flex-latest.redacted.xml'
STATEMENT_METADATA = FINANCE / 'state' / 'portfolio-flex-statement-metadata.json'
STATEMENT_INVENTORY = FINANCE / 'state' / 'portfolio-flex-inventory.json'
KEYCHAIN_RESOLVER = ROOT / 'bin' / 'keychain_resolver.py'
TZ_CHI = ZoneInfo('America/Chicago')
BASE_URL = 'https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService'
TOKEN_ID = 'ibkr_flex_web_token'
PII_ATTRS = {
    'accountId',
    'acctId',
    'acctAlias',
    'name',
    'primaryEmail',
    'street',
    'street2',
    'city',
    'state',
    'country',
    'postalCode',
    'streetResidentialAddress',
    'street2ResidentialAddress',
    'cityResidentialAddress',
    'stateResidentialAddress',
    'countryResidentialAddress',
    'postalCodeResidentialAddress',
    'accountRepName',
    'accountRepPhone',
}
PII_ATTRS_NORMALIZED = {key.lower() for key in PII_ATTRS}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def unavailable(reason: str, mode: str = 'flex') -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        'fetched_at': now.isoformat(),
        'fetched_at_chicago': now.astimezone(TZ_CHI).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'source': 'IBKR Flex Web Service',
        'data_status': 'flex_unavailable',
        'ibkr_session_mode': mode,
        'stale_reason': reason,
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
    }


def read_keychain_token() -> str | None:
    if not KEYCHAIN_RESOLVER.exists():
        return None
    req = {'protocolVersion': 1, 'ids': [TOKEN_ID]}
    try:
        proc = subprocess.run(
            [sys.executable, str(KEYCHAIN_RESOLVER)],
            input=json.dumps(req),
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        payload = json.loads(proc.stdout)
    except Exception:
        return None
    token = payload.get('values', {}).get(TOKEN_ID)
    return token if isinstance(token, str) and token else None


def load_config(path: Path = CONFIG) -> dict[str, Any]:
    return load_json_safe(path, {}) or {}


def resolve_credentials(config: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    token = os.environ.get('IBKR_FLEX_TOKEN') or read_keychain_token()
    query_id = os.environ.get('IBKR_FLEX_ACTIVITY_QUERY_ID') or str(config.get('activity_query_id') or '').strip()
    if not token:
        return None, query_id or None, 'missing_flex_token'
    if not query_id:
        return token, None, 'missing_activity_query_id'
    return token, query_id, None


def fetch_url(url: str, timeout: int = 30) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read()


def sha256_bytes(raw: bytes) -> str:
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def attr(row: ET.Element, *names: str, default: str = '') -> str:
    lower = {k.lower(): v for k, v in row.attrib.items()}
    for name in names:
        if name in row.attrib:
            return row.attrib[name]
        value = lower.get(name.lower())
        if value is not None:
            return value
    return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in {None, ''}:
            return default
        return float(str(value).replace(',', ''))
    except Exception:
        return default


def as_int(value: Any, default: int = 0) -> int:
    return int(round(as_float(value, float(default))))


def parse_flex_response(raw: bytes) -> ET.Element:
    return ET.fromstring(raw)


def section_counts(root: ET.Element) -> dict[str, int]:
    counts: dict[str, int] = {}
    for elem in root.iter():
        tag = local_name(elem.tag)
        counts[tag] = counts.get(tag, 0) + 1
    return dict(sorted(counts.items()))


def attr_keys(root: ET.Element) -> dict[str, list[str]]:
    keys: dict[str, set[str]] = {}
    for elem in root.iter():
        if elem.attrib:
            keys.setdefault(local_name(elem.tag), set()).update(elem.attrib)
    return {tag: sorted(values) for tag, values in sorted(keys.items())}


def statement_dates(root: ET.Element) -> dict[str, str | None]:
    for elem in root.iter():
        if local_name(elem.tag) == 'FlexStatement':
            return {
                'from': attr(elem, 'fromDate') or None,
                'to': attr(elem, 'toDate') or None,
                'when_generated': attr(elem, 'whenGenerated') or None,
            }
    return {'from': None, 'to': None, 'when_generated': None}


def account_id_present(root: ET.Element) -> bool:
    for elem in root.iter():
        for key in ('accountId', 'acctId'):
            if elem.attrib.get(key):
                return True
    return False


def redact_root(root: ET.Element) -> ET.Element:
    for elem in root.iter():
        for key in list(elem.attrib):
            if key.lower() in PII_ATTRS_NORMALIZED:
                elem.attrib[key] = 'REDACTED'
    return root


def redacted_statement(raw: bytes) -> bytes:
    root = redact_root(parse_flex_response(raw))
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp')
    tmp.write_text(text, encoding='utf-8')
    tmp.replace(path)


def write_flex_artifacts(
    raw: bytes,
    query_id: str | None,
    redacted_path: Path = REDACTED_STATEMENT,
    metadata_path: Path = STATEMENT_METADATA,
    inventory_path: Path = STATEMENT_INVENTORY,
    fetched_at: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current = fetched_at or datetime.now(timezone.utc)
    raw_root = parse_flex_response(raw)
    redacted = redacted_statement(raw)
    redacted_root = parse_flex_response(redacted)
    dates = statement_dates(raw_root)
    metadata = {
        'generated_at': current.isoformat(),
        'fetched_at': current.isoformat(),
        'query_id': str(query_id) if query_id else None,
        'statement_from': dates['from'],
        'statement_to': dates['to'],
        'statement_when_generated': dates['when_generated'],
        'raw_sha256': sha256_bytes(raw),
        'redacted_sha256': sha256_bytes(redacted),
        'redacted_statement_path': str(redacted_path),
        'account_id_present': account_id_present(raw_root),
        'token_persisted': False,
    }
    inventory = {
        'generated_at': current.isoformat(),
        'source_redacted_sha256': metadata['redacted_sha256'],
        'section_counts': section_counts(redacted_root),
        'attribute_keys': attr_keys(redacted_root),
        'required_sections': {
            'OpenPositions': (section_counts(redacted_root).get('OpenPositions', 0) > 0),
        },
        'quality': {
            'base_positions_available': section_counts(redacted_root).get('OpenPositions', 0) > 0,
            'security_info_available': section_counts(redacted_root).get('SecurityInfo', 0) > 0,
            'cash_nav_available': section_counts(redacted_root).get('CashReportCurrency', 0) > 0,
            'performance_available': (
                section_counts(redacted_root).get('MTMPerformanceSummaryUnderlying', 0) > 0
                or section_counts(redacted_root).get('FIFOPerformanceSummaryInBase', 0) > 0
            ),
            'option_exercise_available': (
                section_counts(redacted_root).get('OptionEAE', 0) > 0
                or section_counts(redacted_root).get('PendingExercises', 0) > 0
                or section_counts(redacted_root).get('PendingExcercises', 0) > 0
            ),
        },
        'spelling_notes': {
            'pending_exercises_tags_seen': [
                tag for tag in ('PendingExercises', 'PendingExcercises')
                if section_counts(redacted_root).get(tag, 0) > 0
            ],
        },
        'metadata_path': str(metadata_path),
        'redacted_statement_path': str(redacted_path),
    }
    write_text_atomic(redacted_path, redacted.decode('utf-8'))
    atomic_write_json(metadata_path, metadata)
    atomic_write_json(inventory_path, inventory)
    return metadata, inventory


def flex_status(root: ET.Element) -> str:
    attr_status = root.attrib.get('Status') or root.attrib.get('status')
    if attr_status:
        return attr_status
    return first_text(root, 'Status') or first_text(root, 'code') or ''


def first_text(root: ET.Element, name: str) -> str | None:
    for elem in root.iter():
        if local_name(elem.tag).lower() == name.lower() and elem.text:
            return elem.text.strip()
    return None


def request_statement(token: str, query_id: str, version: str = '3', retries: int = 5) -> bytes:
    params = urllib.parse.urlencode({'t': token, 'q': query_id, 'v': version})
    send_raw = fetch_url(f'{BASE_URL}/SendRequest?{params}')
    send_root = parse_flex_response(send_raw)
    status = flex_status(send_root).lower()
    if status and status != 'success':
        message = first_text(send_root, 'ErrorMessage') or first_text(send_root, 'Message') or status
        raise RuntimeError(f'flex SendRequest failed: {message}')
    reference = first_text(send_root, 'ReferenceCode')
    if not reference:
        raise RuntimeError('flex SendRequest missing ReferenceCode')
    statement_params = urllib.parse.urlencode({'t': token, 'q': reference, 'v': version})
    last_raw = b''
    for attempt in range(retries):
        last_raw = fetch_url(f'{BASE_URL}/GetStatement?{statement_params}')
        root = parse_flex_response(last_raw)
        status = flex_status(root).lower()
        if not status or status == 'success':
            return last_raw
        if status == 'warn':
            time.sleep(min(2 + attempt, 5))
            continue
        message = first_text(root, 'ErrorMessage') or first_text(root, 'Message') or status
        raise RuntimeError(f'flex GetStatement failed: {message}')
    raise RuntimeError(f'flex GetStatement did not become ready after {retries} attempts: {last_raw[:200]!r}')


def parse_expiry(value: str | None) -> str | None:
    if not value:
        return None
    digits = ''.join(ch for ch in str(value) if ch.isdigit())
    if len(digits) >= 8:
        return f'{digits[:4]}-{digits[4:6]}-{digits[6:8]}'
    return str(value)


def days_to_expiry(expiry: str | None, now: datetime) -> int | None:
    if not expiry:
        return None
    try:
        expiry_date = datetime.fromisoformat(expiry).date()
    except Exception:
        return None
    as_of = now
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    return (expiry_date - as_of.astimezone(TZ_CHI).date()).days


def classify_open_position(row: ET.Element, now: datetime) -> dict[str, Any] | None:
    symbol = attr(row, 'symbol', 'underlyingSymbol')
    desc = attr(row, 'description', 'assetDescription', 'contractDesc', default=symbol)
    qty = as_float(attr(row, 'position', 'quantity', 'qty'))
    if qty == 0:
        return None
    asset_raw = attr(row, 'assetCategory', 'assetClass', 'secType', default='STK').upper()
    is_option = 'OPT' in asset_raw or attr(row, 'putCall', 'right')
    asset_class = 'OPT' if is_option else 'STK'
    mkt_value = as_float(attr(row, 'positionValue', 'marketValue', 'mktValue'))
    mkt_price = as_float(attr(row, 'markPrice', 'marketPrice', 'mktPrice'))
    cost_basis = abs(as_float(attr(row, 'costBasisMoney', 'costBasis', 'costBasisBasis')))
    avg_price = as_float(attr(row, 'costBasisPrice', 'avgPrice', 'avgCost'))
    pnl = as_float(attr(row, 'fifoPnlUnrealized', 'unrealizedPnl', 'unrealizedPNL'))
    pnl_pct = round((pnl / cost_basis) * 100, 2) if cost_basis else 0
    out = {
        'symbol': symbol or '?',
        'description': desc or symbol or '?',
        'asset_class': asset_class,
        'quantity': qty,
        'direction': 'long' if qty > 0 else 'short',
        'mkt_price': round(mkt_price, 2),
        'mkt_value': round(mkt_value, 2),
        'avg_price': round(avg_price, 2),
        'cost_basis': round(cost_basis, 2),
        'unrealized_pnl': round(pnl, 2),
        'pnl_pct': pnl_pct,
    }
    if asset_class == 'OPT':
        expiry = parse_expiry(attr(row, 'expiry', 'expirationDate'))
        right = attr(row, 'putCall', 'right').lower()
        out.update({
            'underlying': attr(row, 'underlyingSymbol', default=symbol) or symbol,
            'strike': as_float(attr(row, 'strike')),
            'expiry': expiry,
            'dte': days_to_expiry(expiry, now),
            'put_or_call': 'call' if right.startswith('c') else 'put' if right.startswith('p') else None,
            'multiplier': as_int(attr(row, 'multiplier'), 100),
        })
    return out


def parse_statement(raw: bytes, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    root = parse_flex_response(raw)
    account_id_present_flag = False
    open_positions = []
    saw_positions_section = False
    for elem in root.iter():
        tag = local_name(elem.tag)
        if tag == 'FlexStatement':
            account_id_present_flag = bool(attr(elem, 'accountId', 'accountId'))
        if tag in {'OpenPositions', 'Positions'}:
            saw_positions_section = True
        if tag in {'OpenPosition', 'Position'}:
            saw_positions_section = True
            parsed = classify_open_position(elem, current)
            if parsed:
                open_positions.append(parsed)
    if not saw_positions_section:
        raise RuntimeError('flex statement missing OpenPositions section; update Activity Flex Query to include open positions')
    stocks = [item for item in open_positions if item['asset_class'] == 'STK']
    options = [item for item in open_positions if item['asset_class'] == 'OPT']
    total_stock_value = sum(item['mkt_value'] for item in stocks)
    total_option_value = sum(item['mkt_value'] for item in options)
    total_unrealized = sum(item['unrealized_pnl'] for item in open_positions)
    expiry_buckets: dict[str, int] = {}
    for option in options:
        expiry = option.get('expiry') or 'unknown'
        expiry_buckets[expiry] = expiry_buckets.get(expiry, 0) + 1
    return {
        'fetched_at': current.isoformat(),
        'fetched_at_chicago': current.astimezone(TZ_CHI).strftime('%Y-%m-%d %H:%M:%S %Z'),
        'account_id_present': account_id_present_flag,
        'source': 'IBKR Flex Web Service',
        'data_status': 'fresh',
        'ibkr_session_mode': 'flex',
        'summary': {
            'stock_positions': len(stocks),
            'option_positions': len(options),
            'total_stock_value': round(total_stock_value, 2),
            'total_option_value': round(total_option_value, 2),
            'total_portfolio_value': round(total_stock_value + total_option_value, 2),
            'total_unrealized_pnl': round(total_unrealized, 2),
            'options_by_expiry': dict(sorted(expiry_buckets.items())),
        },
        'stocks': sorted(stocks, key=lambda item: abs(item['mkt_value']), reverse=True),
        'options': sorted(options, key=lambda item: item.get('dte') if item.get('dte') is not None else 9999),
    }


def write_outputs(portfolio: dict[str, Any], status: dict[str, Any], portfolio_path: Path, status_path: Path) -> None:
    atomic_write_json(portfolio_path, portfolio)
    atomic_write_json(status_path, status)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Fetch IBKR Flex holdings baseline.')
    parser.add_argument('--config', default=str(CONFIG))
    parser.add_argument('--xml-fixture', help='Parse a local Flex XML file instead of calling the service.')
    parser.add_argument('--portfolio-out', default=str(PORTFOLIO_FLEX))
    parser.add_argument('--status-out', default=str(SOURCE_STATUS))
    parser.add_argument('--redacted-xml-out', default=str(REDACTED_STATEMENT))
    parser.add_argument('--metadata-out', default=str(STATEMENT_METADATA))
    parser.add_argument('--inventory-out', default=str(STATEMENT_INVENTORY))
    args = parser.parse_args(argv)

    portfolio_path = Path(args.portfolio_out)
    status_path = Path(args.status_out)
    redacted_path = Path(args.redacted_xml_out)
    metadata_path = Path(args.metadata_out)
    inventory_path = Path(args.inventory_out)

    try:
        if args.xml_fixture:
            raw = Path(args.xml_fixture).read_bytes()
        else:
            config = load_config(Path(args.config))
            token, query_id, error = resolve_credentials(config)
            if error:
                portfolio = unavailable(error)
                write_outputs(portfolio, {
                    'generated_at': now_iso(),
                    'status': 'fail',
                    'selected_source': None,
                    'flex_status': 'unavailable',
                    'blocking_reasons': [error],
                }, portfolio_path, status_path)
                print(json.dumps({'status': 'fail', 'blocking_reasons': [error], 'portfolio_path': str(portfolio_path)}, ensure_ascii=False))
                return 1
            raw = request_statement(token, query_id)
        metadata, inventory = write_flex_artifacts(raw, query_id if not args.xml_fixture else 'fixture', redacted_path, metadata_path, inventory_path)
        portfolio = parse_statement(raw)
        portfolio['source_redacted_sha256'] = metadata['redacted_sha256']
        portfolio['statement_metadata_path'] = str(metadata_path)
        portfolio['section_inventory_path'] = str(inventory_path)
        write_outputs(portfolio, {
            'generated_at': now_iso(),
            'status': 'pass',
            'selected_source': 'flex',
            'flex_status': 'fresh',
            'blocking_reasons': [],
            'portfolio_path': str(portfolio_path),
            'statement_metadata_path': str(metadata_path),
            'section_inventory_path': str(inventory_path),
            'source_redacted_sha256': metadata['redacted_sha256'],
        }, portfolio_path, status_path)
        print(json.dumps({
            'status': 'pass',
            'stock_positions': portfolio['summary']['stock_positions'],
            'option_positions': portfolio['summary']['option_positions'],
            'portfolio_path': str(portfolio_path),
        }, ensure_ascii=False))
        return 0
    except Exception as exc:
        portfolio = unavailable(str(exc)[:500])
        write_outputs(portfolio, {
            'generated_at': now_iso(),
            'status': 'fail',
            'selected_source': None,
            'flex_status': 'error',
            'blocking_reasons': ['flex_fetch_failed'],
            'error': str(exc)[:500],
        }, portfolio_path, status_path)
        print(json.dumps({'status': 'fail', 'blocking_reasons': ['flex_fetch_failed'], 'portfolio_path': str(portfolio_path)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
