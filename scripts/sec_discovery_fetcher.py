#!/usr/bin/env python3
"""Fetch broad-market SEC/EDGAR discovery candidates.

This is a deterministic feeder. It produces source candidates only; it does
not render reports, trigger wakes, or make trading judgments.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_io import atomic_write_json


ROOT = Path('/Users/leofitz/.openclaw')
WORKSPACE = ROOT / 'workspace'
FINANCE = WORKSPACE / 'finance'
STATE = FINANCE / 'state'
DEFAULT_OUT = STATE / 'sec-discovery.json'
SEC_CURRENT_ATOM = 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&CIK=&type={form_type}&company=&dateb=&owner=include&start=0&count={count}&output=atom'
DEFAULT_FORMS = ['8-K', '4', 'SC 13D', 'SC 13G']
USER_AGENT = 'openclaw-finance-discovery/1.0 leofitz@example.invalid'


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


def local_name(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def child_text(element: ET.Element, name: str) -> str | None:
    for child in element.iter():
        if local_name(child.tag) == name and child.text:
            return child.text.strip()
    return None


def link_href(entry: ET.Element) -> str | None:
    for child in entry:
        if local_name(child.tag) == 'link':
            href = child.attrib.get('href')
            if href:
                return href
    return None


def category_term(entry: ET.Element) -> str | None:
    for child in entry:
        if local_name(child.tag) == 'category':
            term = child.attrib.get('term')
            if term:
                return term
    return None


def normalize_filed_at(value: str | None) -> str:
    if not value:
        return now_iso()
    value = value.strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        return f'{value}T00:00:00Z'
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    except Exception:
        return now_iso()


def parse_feed(xml_text: str, *, requested_form: str, fetched_at: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    entries = [item for item in root.iter() if local_name(item.tag) == 'entry']
    out: list[dict[str, Any]] = []
    for entry in entries:
        title = child_text(entry, 'title') or ''
        updated = child_text(entry, 'updated') or fetched_at
        form_type = category_term(entry) or child_text(entry, 'form-type') or requested_form
        company = child_text(entry, 'company-name') or child_text(entry, 'company-info') or title
        cik = child_text(entry, 'cik') or child_text(entry, 'cik-number') or cik_from_title(title)
        accession = child_text(entry, 'accession-number')
        filing_date = child_text(entry, 'filing-date') or updated
        url = link_href(entry)
        filed_at = normalize_filed_at(filing_date)
        discovery_id = stable_id('sec-disc', form_type, company, cik, accession, url, filed_at)
        out.append({
            'discovery_id': discovery_id,
            'candidate_type': 'unknown_discovery',
            'discovery_scope': 'non_watchlist',
            'source': 'sec.gov',
            'source_kind': 'sec_current_filing',
            'form_type': form_type,
            'company_name': company,
            'cik': cik,
            'accession_number': accession,
            'title': title or f'{company} {form_type}',
            'summary': f'{company} filed {form_type}' + (f' ({accession})' if accession else ''),
            'url': url,
            'published_at': filed_at,
            'observed_at': filed_at,
            'detected_at': fetched_at,
            'raw_ref': url or f'sec:{form_type}:{cik}:{accession}',
            'layer': 'L4_actor_intent',
            'direction': direction_for_form(form_type, title),
            'novelty_score': novelty_for_form(form_type),
        })
    return out


def cik_from_title(title: str) -> str | None:
    match = re.search(r'\((0{0,6}\d{4,10})\)', title)
    if not match:
        return None
    return match.group(1)


def direction_for_form(form_type: str, title: str) -> str:
    lowered = f'{form_type} {title}'.lower()
    if '13d' in lowered or '13g' in lowered:
        return 'bullish'
    if 'form 4' in lowered or form_type.strip() == '4':
        return 'ambiguous'
    return 'ambiguous'


def novelty_for_form(form_type: str) -> float:
    lowered = form_type.lower()
    if '13d' in lowered or '13g' in lowered:
        return 8.0
    if lowered.strip() == '4':
        return 6.5
    if '8-k' in lowered:
        return 6.0
    return 5.5


def fetch_atom(form_type: str, count: int, timeout: int) -> str:
    url = SEC_CURRENT_ATOM.format(form_type=urllib.request.quote(form_type), count=count)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/atom+xml, application/xml;q=0.9, */*;q=0.8'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode('utf-8', errors='replace')


def build_report(*, forms: list[str], count: int, timeout: int, fixture_xml: Path | None = None) -> dict[str, Any]:
    fetched_at = now_iso()
    discoveries: list[dict[str, Any]] = []
    fetch_errors: list[dict[str, Any]] = []
    if fixture_xml:
        xml_text = fixture_xml.read_text(encoding='utf-8')
        discoveries.extend(parse_feed(xml_text, requested_form=forms[0] if forms else '8-K', fetched_at=fetched_at))
    else:
        for form in forms:
            try:
                discoveries.extend(parse_feed(fetch_atom(form, count, timeout), requested_form=form, fetched_at=fetched_at))
            except Exception as exc:
                fetch_errors.append({'form_type': form, 'error': str(exc)[:300]})
    deduped = {}
    for item in discoveries:
        deduped[item['discovery_id']] = item
    rows = sorted(deduped.values(), key=lambda item: (item.get('published_at') or '', item.get('discovery_id') or ''), reverse=True)
    return {
        'generated_at': fetched_at,
        'status': 'pass' if rows or not fetch_errors else 'degraded',
        'source': 'sec.gov current filings atom',
        'forms': forms,
        'count_per_form': count,
        'discovery_count': len(rows),
        'discoveries': rows[: count * max(1, len(forms))],
        'fetch_errors': fetch_errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--forms', default=','.join(DEFAULT_FORMS), help='Comma-separated SEC forms')
    parser.add_argument('--count', type=int, default=25)
    parser.add_argument('--timeout', type=int, default=15)
    parser.add_argument('--fixture-xml')
    parser.add_argument('--out', default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_out_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    forms = [item.strip() for item in args.forms.split(',') if item.strip()]
    report = build_report(forms=forms, count=args.count, timeout=args.timeout, fixture_xml=Path(args.fixture_xml) if args.fixture_xml else None)
    atomic_write_json(out, report)
    print(json.dumps({'status': report['status'], 'discovery_count': report['discovery_count'], 'fetch_errors': len(report['fetch_errors']), 'out': str(out)}, ensure_ascii=False))
    return 0 if report['status'] in {'pass', 'degraded'} else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
