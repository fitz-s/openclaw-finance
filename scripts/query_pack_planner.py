#!/usr/bin/env python3
"""Compile deterministic QueryPack candidates from the scanner context pack."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json

FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
STATE = FINANCE / 'state'
SCANNER_PACK = STATE / 'llm-job-context' / 'scanner.json'
OUT = STATE / 'query-packs' / 'scanner-planned.jsonl'
REPORT = STATE / 'query-packs' / 'scanner-planned-report.json'
CONTRACT = 'query-pack-planner-v1-shadow'
QUERY_PACK_CONTRACT = 'query-pack-v1'
LANE_NEWS = 'news_policy_narrative'
TICKER_RE = re.compile(r'\b[A-Z]{1,5}(?:/[A-Z]{3})?\b')
NON_TICKERS = {'API', 'CEO', 'CFO', 'CPI', 'ET', 'ETF', 'GDP', 'SEC', 'USD', 'WTI'}
FORBIDDEN = ['trade_recommendation', 'threshold_mutation', 'execution', 'wake_mutation', 'judgment_mutation']


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(part or '') for part in parts)
    return f'{prefix}:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp')
    tmp.write_text(''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows), encoding='utf-8')
    tmp.replace(path)


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def short(value: Any, limit: int = 120) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def extract_symbols(*values: Any) -> list[str]:
    symbols = set()
    for value in values:
        if isinstance(value, list):
            iterable = value
        else:
            iterable = [value]
        for item in iterable:
            for match in TICKER_RE.findall(str(item or '')):
                if match not in NON_TICKERS:
                    symbols.add(match.replace('/', '-').upper())
    return sorted(symbols)


def base_query_pack(
    *,
    scanner_pack: dict[str, Any],
    purpose: str,
    query: str,
    required_entities: list[str] | None = None,
    source_object_refs: list[str] | None = None,
    allowed_domains: list[str] | None = None,
    max_results: int = 10,
    discovery_lane: str = LANE_NEWS,
    authority_level: str = 'canonical_candidate',
    freshness: str = 'day',
    exclusion_symbols: list[str] | None = None,
) -> dict[str, Any]:
    identity = {
        'purpose': purpose,
        'query': ' '.join(query.lower().split()),
        'required_entities': sorted(required_entities or []),
        'source_object_refs': sorted(source_object_refs or []),
        'freshness': freshness,
        'authority_level': authority_level,
    }
    pack_id = 'query-pack:' + hashlib.sha1(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:20]
    return {
        'contract': QUERY_PACK_CONTRACT,
        'pack_id': pack_id,
        'campaign_id': None,
        'lane': discovery_lane,
        'purpose': purpose,
        'query': query,
        'freshness': freshness,
        'date_after': None,
        'date_before': None,
        'allowed_domains': allowed_domains or [],
        'required_entities': required_entities or [],
        'max_results': max(1, min(int(max_results), 50)),
        'authority_level': authority_level,
        'forbidden': FORBIDDEN,
        'source_object_refs': source_object_refs or [],
        'exclusion_symbols': sorted(set(exclusion_symbols or []))[:100],
        'planner_origin': {
            'scanner_pack_id': scanner_pack.get('pack_id'),
            'scanner_role': scanner_pack.get('scanner_canonical_role') or scanner_pack.get('job_role'),
            'generated_by': 'scripts/query_pack_planner.py',
        },
        'planner_not_evidence': True,
        'pack_is_not_authority': True,
        'no_execution': True,
    }


def invalidator_query(item: dict[str, Any]) -> str:
    target = item.get('target_id') or item.get('target_type') or ''
    desc = item.get('description') or item.get('attention_justification') or ''
    return short(f'{target} invalidator evidence update {desc}', 180)


def opportunity_query(item: dict[str, Any]) -> str:
    instrument = item.get('instrument') or ''
    theme = item.get('theme') or ''
    return short(f'{instrument} opportunity follow-up fresh source confirmation {theme}', 180)


def thesis_query(item: dict[str, Any]) -> str:
    instrument = item.get('instrument') or ''
    confirmations = ' '.join(str(v) for v in item.get('required_confirmations', [])[:3]) if isinstance(item.get('required_confirmations'), list) else ''
    return short(f'{instrument} thesis update confirmation {confirmations}', 180)


def unknown_discovery_queries(scanner_pack: dict[str, Any]) -> list[str]:
    seeds = [
        'fresh non-watchlist market dislocation sector rotation unusual options source confirmation',
        'fresh macro cross-asset dislocation gold bitcoin SPX oil rates source confirmation',
        'fresh company-specific opportunity outside watchlist with official filing or reputable news source',
    ]
    # Keep these generic: known symbols go into exclusions, not query satisfaction.
    return seeds[: max(1, int((scanner_pack.get('fixed_search_budget') or {}).get('unknown_discovery_minimum_attempts') or 1))]


def build_query_packs(scanner_pack: dict[str, Any], *, generated_at: str | None = None) -> dict[str, Any]:
    generated = generated_at or now_iso()
    known_symbols = scanner_pack.get('known_symbols_must_not_satisfy_unknown_discovery') if isinstance(scanner_pack.get('known_symbols_must_not_satisfy_unknown_discovery'), list) else []
    packs: list[dict[str, Any]] = []

    for item in scanner_pack.get('top_invalidators', []) if isinstance(scanner_pack.get('top_invalidators'), list) else []:
        if not isinstance(item, dict):
            continue
        query = invalidator_query(item)
        entities = extract_symbols(item.get('target_id'), item.get('description'), item.get('evidence_refs'))
        packs.append(base_query_pack(
            scanner_pack=scanner_pack,
            purpose='source_discovery',
            query=query,
            required_entities=entities,
            source_object_refs=[str(item.get('invalidator_id'))] if item.get('invalidator_id') else [],
            max_results=10,
        ))

    for item in scanner_pack.get('top_opportunity_candidates', []) if isinstance(scanner_pack.get('top_opportunity_candidates'), list) else []:
        if not isinstance(item, dict):
            continue
        instrument = str(item.get('instrument') or '')
        entities = extract_symbols(instrument, item.get('theme'))
        packs.append(base_query_pack(
            scanner_pack=scanner_pack,
            purpose='source_discovery',
            query=opportunity_query(item),
            required_entities=entities,
            source_object_refs=[str(item.get('candidate_id'))] if item.get('candidate_id') else [],
            max_results=10,
        ))

    for item in scanner_pack.get('top_thesis_deltas', []) if isinstance(scanner_pack.get('top_thesis_deltas'), list) else []:
        if not isinstance(item, dict):
            continue
        entities = extract_symbols(item.get('instrument'), item.get('required_confirmations'))
        packs.append(base_query_pack(
            scanner_pack=scanner_pack,
            purpose='claim_closure',
            query=thesis_query(item),
            required_entities=entities,
            source_object_refs=[str(item.get('thesis_id'))] if item.get('thesis_id') else [],
            max_results=8,
        ))

    for query in unknown_discovery_queries(scanner_pack):
        packs.append(base_query_pack(
            scanner_pack=scanner_pack,
            purpose='source_discovery',
            query=query,
            required_entities=[],
            source_object_refs=['unknown_discovery_lane'],
            max_results=12,
            exclusion_symbols=[str(item) for item in known_symbols],
        ))

    dedup: dict[str, dict[str, Any]] = {}
    for pack in packs:
        dedup[pack['pack_id']] = pack
    rows = sorted(dedup.values(), key=lambda item: (item['purpose'], item['pack_id']))
    return {
        'generated_at': generated,
        'status': 'pass',
        'contract': CONTRACT,
        'scanner_pack_id': scanner_pack.get('pack_id'),
        'query_pack_count': len(rows),
        'query_packs': rows,
        'planner_role': 'query_pack_planner_not_evidence',
        'free_form_web_search_canonical_ingestion': False,
        'shadow_only': True,
        'no_execution': True,
        'report_hash': canonical_hash(rows),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--scanner-pack', default=str(SCANNER_PACK))
    parser.add_argument('--out', default=str(OUT))
    parser.add_argument('--report', default=str(REPORT))
    args = parser.parse_args(argv)
    out = Path(args.out)
    report_path = Path(args.report)
    if not safe_state_path(out) or not safe_state_path(report_path):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_state_path']}, ensure_ascii=False))
        return 2
    scanner_pack = load_json(Path(args.scanner_pack), {}) or {}
    report = build_query_packs(scanner_pack)
    write_jsonl(out, report['query_packs'])
    atomic_write_json(report_path, report)
    print(json.dumps({'status': report['status'], 'query_pack_count': report['query_pack_count'], 'out': str(out), 'report': str(report_path)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
