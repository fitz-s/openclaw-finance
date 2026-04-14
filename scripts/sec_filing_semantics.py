#!/usr/bin/env python3
"""Classify SEC discovery records into conservative filing semantics."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_io import atomic_write_json, load_json_safe


ROOT = Path('/Users/leofitz/.openclaw')
WORKSPACE = ROOT / 'workspace'
FINANCE = WORKSPACE / 'finance'
STATE = FINANCE / 'state'
DEFAULT_DISCOVERY = STATE / 'sec-discovery.json'
DEFAULT_OUT = STATE / 'sec-filing-semantics.json'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(part or '') for part in parts)
    return f"{prefix}:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def safe_out_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def normalized_form(value: Any) -> str:
    return str(value or '').strip().upper().replace('SCHEDULE ', '').replace('FORM ', '')


def semantic_type_for(form_type: str, detail: dict[str, Any]) -> str:
    form = normalized_form(form_type)
    if form == '4':
        direction = detail.get('transaction_direction')
        return f"form4_{direction}" if direction in {'buy', 'sell'} else 'form4_metadata_only'
    if '13D' in form:
        return 'beneficial_ownership_13d'
    if '13G' in form:
        return 'beneficial_ownership_13g'
    if '8-K' in form or form == '8K':
        return 'current_report_8k_material' if detail.get('material_event_hint') else 'current_report_8k_metadata_only'
    return 'sec_filing_metadata_only'


def direction_for(form_type: str, detail: dict[str, Any]) -> str:
    form = normalized_form(form_type)
    if form == '4':
        direction = detail.get('transaction_direction')
        if direction == 'buy':
            return 'bullish'
        if direction == 'sell':
            return 'bearish'
    if '13D' in form and detail.get('activist_or_control_signal'):
        return 'bullish'
    return 'ambiguous'


def wake_candidate_for(form_type: str, semantic_type: str, detail: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    form = normalized_form(form_type)
    if form == '4':
        value = detail.get('transaction_value_estimate')
        if detail.get('transaction_direction') in {'buy', 'sell'} and isinstance(value, (int, float)) and value >= 250_000:
            reasons.append('large_form4_transaction')
            return True, reasons
        reasons.append('ordinary_form4_support_only')
        return False, reasons
    if '13D' in form:
        if detail.get('ownership_percent') or detail.get('activist_or_control_signal'):
            reasons.append('13d_ownership_or_control_signal')
            return True, reasons
        reasons.append('13d_metadata_support_only')
        return False, reasons
    if '13G' in form:
        reasons.append('13g_passive_ownership_support_only')
        return False, reasons
    if '8-K' in form or form == '8K':
        if detail.get('material_event_hint'):
            reasons.append('material_8k_hint')
            return True, reasons
        reasons.append('generic_8k_support_only')
        return False, reasons
    reasons.append('metadata_support_only')
    return False, reasons


def text_value(root: ET.Element, path: str) -> str | None:
    node = root.find('.//' + path)
    return node.text.strip() if node is not None and node.text else None


def parse_form4_xml(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    issuer_name = text_value(root, 'issuerName')
    issuer_cik = text_value(root, 'issuerCik')
    issuer_symbol = text_value(root, 'issuerTradingSymbol')
    owner_name = text_value(root, 'rptOwnerName')
    owner_role = 'director' if text_value(root, 'isDirector') == '1' else 'officer' if text_value(root, 'isOfficer') == '1' else None
    code = text_value(root, 'transactionAcquiredDisposedCode/value')
    shares = number(text_value(root, 'transactionShares/value'))
    price = number(text_value(root, 'transactionPricePerShare/value'))
    direction = 'buy' if code == 'A' else 'sell' if code == 'D' else None
    value = round(shares * price, 2) if shares is not None and price is not None else None
    return {
        'issuer_name': issuer_name,
        'issuer_cik': issuer_cik,
        'issuer_symbol': issuer_symbol,
        'reporting_owner': owner_name,
        'owner_role': owner_role,
        'transaction_direction': direction,
        'transaction_shares': shares,
        'transaction_price': price,
        'transaction_value_estimate': value,
    }


def number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(',', '').strip())
    except ValueError:
        return None


def parse_text_detail(text: str) -> dict[str, Any]:
    lower = text.lower()
    ownership = None
    pct = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
    if pct:
        ownership = number(pct.group(1))
    activist = any(token in lower for token in ['control', 'activist', 'influence', 'board', 'proxy', 'change in control'])
    material = None
    for token in ['merger', 'acquisition', 'bankruptcy', 'financing', 'offering', 'guidance', 'restatement', 'termination', 'material agreement']:
        if token in lower:
            material = token
            break
    return {
        'ownership_percent': ownership,
        'activist_or_control_signal': activist,
        'material_event_hint': material,
    }


def detail_for(discovery: dict[str, Any], fixture_details: dict[str, str]) -> dict[str, Any]:
    key_candidates = [
        str(discovery.get('discovery_id') or ''),
        str(discovery.get('accession_number') or ''),
        str(discovery.get('url') or ''),
        str(discovery.get('form_type') or ''),
    ]
    detail_text = ''
    for key in key_candidates:
        if key and key in fixture_details:
            detail_text = fixture_details[key]
            break
    if not detail_text:
        return {}
    if '<ownershipDocument' in detail_text or '<nonDerivativeTable' in detail_text:
        try:
            return parse_form4_xml(detail_text)
        except Exception:
            return {'detail_parse_error': 'form4_xml_parse_failed'}
    return parse_text_detail(detail_text)


def semantics_for(discovery: dict[str, Any], fixture_details: dict[str, str]) -> dict[str, Any]:
    detail = detail_for(discovery, fixture_details)
    form_type = str(discovery.get('form_type') or '')
    semantic_type = semantic_type_for(form_type, detail)
    wake_candidate, reasons = wake_candidate_for(form_type, semantic_type, detail)
    direction = direction_for(form_type, detail)
    return {
        'semantic_id': stable_id('sec-sem', discovery.get('discovery_id'), semantic_type, detail.get('transaction_direction'), detail.get('ownership_percent'), detail.get('material_event_hint')),
        'discovery_id': discovery.get('discovery_id'),
        'source': 'sec.gov',
        'url': discovery.get('url'),
        'form_type': form_type,
        'filing_semantic_type': semantic_type,
        'issuer_name': detail.get('issuer_name') or discovery.get('company_name'),
        'issuer_cik': detail.get('issuer_cik') or discovery.get('cik'),
        'issuer_symbol': detail.get('issuer_symbol'),
        'reporting_owner': detail.get('reporting_owner'),
        'owner_role': detail.get('owner_role'),
        'transaction_direction': detail.get('transaction_direction'),
        'transaction_shares': detail.get('transaction_shares'),
        'transaction_price': detail.get('transaction_price'),
        'transaction_value_estimate': detail.get('transaction_value_estimate'),
        'ownership_percent': detail.get('ownership_percent'),
        'activist_or_control_signal': bool(detail.get('activist_or_control_signal')),
        'material_event_hint': detail.get('material_event_hint'),
        'direction': direction,
        'semantic_wake_candidate': wake_candidate,
        'support_only': not wake_candidate,
        'confidence': 'detail_parsed' if detail else 'metadata_only',
        'classification_reasons': reasons,
        'published_at': discovery.get('published_at'),
        'observed_at': discovery.get('observed_at'),
        'detected_at': discovery.get('detected_at'),
        'raw_ref': discovery.get('raw_ref') or discovery.get('url') or f"sec:{discovery.get('form_type')}:{discovery.get('cik')}",
    }


def load_fixture_details(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    payload = load_json_safe(path, {}) or {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items()}


def build_report(discovery: dict[str, Any], fixture_details: dict[str, str] | None = None) -> dict[str, Any]:
    fixture_details = fixture_details or {}
    rows = [
        semantics_for(item, fixture_details)
        for item in discovery.get('discoveries', [])
        if isinstance(item, dict)
    ]
    return {
        'generated_at': now_iso(),
        'status': 'pass' if rows else 'degraded',
        'source_discovery_generated_at': discovery.get('generated_at'),
        'semantic_count': len(rows),
        'wake_candidate_count': sum(1 for item in rows if item.get('semantic_wake_candidate') is True),
        'support_only_count': sum(1 for item in rows if item.get('support_only') is True),
        'semantics': rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--discovery', default=str(DEFAULT_DISCOVERY))
    parser.add_argument('--fixture-details')
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_out_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    report = build_report(load_json_safe(Path(args.discovery), {}) or {}, load_fixture_details(Path(args.fixture_details)) if args.fixture_details else {})
    atomic_write_json(out, report)
    print(json.dumps({'status': report['status'], 'semantic_count': report['semantic_count'], 'wake_candidate_count': report['wake_candidate_count'], 'out': str(out)}, ensure_ascii=False))
    return 0 if report['status'] in {'pass', 'degraded'} else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
