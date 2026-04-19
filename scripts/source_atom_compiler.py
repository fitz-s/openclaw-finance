#!/usr/bin/env python3
"""Compile shadow EvidenceAtom rows from finance scanner state.

EvidenceAtom is a preservation substrate. It is not wake, judgment, delivery,
or execution authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe


WORKSPACE = Path('/Users/leofitz/.openclaw/workspace')
FINANCE = WORKSPACE / 'finance'
STATE = FINANCE / 'state'
SCAN_STATE = STATE / 'intraday-open-scan-state.json'
SOURCE_ATOMS_DIR = STATE / 'source-atoms'
SOURCE_ATOMS_LATEST = SOURCE_ATOMS_DIR / 'latest.jsonl'
SOURCE_REGISTRY = WORKSPACE / 'services' / 'market-ingest' / 'config' / 'source-registry.json'
CONTRACT = 'evidence-atom-v1-shadow'
MAX_SNIPPET_CHARS = 280
TICKER_RE = re.compile(r'\b[A-Z]{1,5}(?:/[A-Z]{3})?\b')
KNOWN_NON_TICKERS = {'AI', 'API', 'CEO', 'CFO', 'CPI', 'ETF', 'ET', 'GDP', 'SEC', 'USD', 'WTI'}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = '|'.join(str(part or '') for part in parts)
    return f'{prefix}:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:20]


def short_text(value: Any, limit: int = MAX_SNIPPET_CHARS) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def parse_ts(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    except Exception:
        return None


def load_source_registry(path: Path = SOURCE_REGISTRY) -> dict[str, Any]:
    return load_json_safe(path, {}) or {}


def registry_sources(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in registry.get('sources', []) if isinstance(item, dict)]


def infer_source_id(observation: dict[str, Any], registry: dict[str, Any]) -> str:
    text = ' '.join(str(src) for src in observation.get('sources', []) if src) if isinstance(observation.get('sources'), list) else str(observation.get('source') or '')
    text = f"{text} {observation.get('summary') or ''} {observation.get('theme') or ''}".lower()
    wildcard = 'source:unknown_web'
    for source in registry_sources(registry):
        patterns = source.get('domain_patterns', []) if isinstance(source.get('domain_patterns'), list) else []
        if '*' in patterns:
            wildcard = str(source.get('source_id') or wildcard)
            continue
        for pattern in patterns:
            if str(pattern).lower() in text:
                return str(source.get('source_id') or wildcard)
    if 'sec.gov' in text or '8-k' in text or 'form 4' in text:
        return 'source:sec_edgar'
    if 'yfinance' in text or 'quote' in text:
        return 'source:yfinance'
    return wildcard


def source_meta(source_id: str, registry: dict[str, Any]) -> dict[str, Any]:
    for source in registry_sources(registry):
        if source.get('source_id') == source_id:
            return source
    return {
        'source_id': source_id,
        'source_class': 'untrusted_web',
        'source_lane': 'news_policy_narrative',
        'modality': 'text',
        'freshness_budget_seconds': 0,
        'reliability_prior': 0.2,
        'uniqueness_prior': 0.1,
        'compliance_class': 'unknown',
        'redistribution_policy': 'unknown',
    }


def source_sublane(source: dict[str, Any]) -> str:
    sublane = str(source.get('source_sublane') or '').strip()
    if sublane:
        return sublane
    lane = str(source.get('source_lane') or 'news_policy_narrative')
    source_class = str(source.get('source_class') or '')
    if lane == 'market_structure' and 'option' in source_class:
        return 'market_structure.options_flow_proxy'
    if lane == 'market_structure':
        return 'market_structure.price_volume'
    if lane == 'corp_filing_ir' or source_class in {'official_filing', 'filings_ir'}:
        return 'corp_filing_ir.sec_filings'
    if lane == 'internal_private':
        return 'internal_private.watch_intent'
    if lane == 'human_field_private':
        return 'human_field_private.expert_transcript'
    if lane == 'real_economy_alt':
        return 'real_economy_alt.unknown'
    return f'{lane}.entity_event' if lane == 'news_policy_narrative' else lane


def export_policy_for(source: dict[str, Any]) -> tuple[str, bool]:
    redistribution = str(source.get('redistribution_policy') or 'unknown')
    compliance = str(source.get('compliance_class') or 'unknown')
    if redistribution == 'raw_ok' and compliance in {'public', 'official', 'allowed'}:
        return 'raw_ok', False
    if redistribution in {'derived_only', 'summary_only'}:
        return 'derived_only', True
    return 'metadata_only', True


def extract_symbols(*values: Any) -> list[str]:
    symbols: set[str] = set()
    for value in values:
        for match in TICKER_RE.findall(str(value or '')):
            if match not in KNOWN_NON_TICKERS:
                symbols.add(match.replace('/', '-').upper())
    return sorted(symbols)


def atom_from_observation(
    observation: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    scan_file: str | None = None,
    fallback_ingested_at: str | None = None,
) -> dict[str, Any]:
    registry = registry or {}
    obs_id = str(observation.get('id') or observation.get('ts') or observation.get('theme') or 'unknown')
    source_id = infer_source_id(observation, registry)
    source = source_meta(source_id, registry)
    sublane = source_sublane(source)
    export_policy, redact_required = export_policy_for(source)
    observed_at = parse_ts(observation.get('observed_at')) or parse_ts(observation.get('ts')) or parse_ts(observation.get('scan_time')) or parse_ts(fallback_ingested_at)
    published_at = parse_ts(observation.get('published_at')) or observed_at
    ingested_at = parse_ts(observation.get('detected_at')) or parse_ts(fallback_ingested_at) or observed_at or now_iso()
    event_time = parse_ts(observation.get('event_time')) or observed_at or published_at or ingested_at
    snippet = short_text(observation.get('summary') or observation.get('description') or observation.get('theme') or obs_id)
    symbols = extract_symbols(observation.get('theme'), observation.get('summary'), observation.get('tickers'))
    if isinstance(observation.get('tickers'), list):
        symbols = sorted(set(symbols) | {str(item).replace('/', '-').upper() for item in observation['tickers'] if item})
    raw_ref = str(observation.get('raw_ref') or f'finance-scan:{obs_id}')
    atom = {
        'atom_id': stable_id('atom', raw_ref, event_time, snippet),
        'source_id': source_id,
        'source_class': source.get('source_class') or 'untrusted_web',
        'source_lane': source.get('source_lane') or 'news_policy_narrative',
        'lane': source.get('source_lane') or 'news_policy_narrative',
        'source_sublane': sublane,
        'published_at': published_at,
        'observed_at': observed_at,
        'ingested_at': ingested_at,
        'event_time': event_time,
        'timezone': 'UTC',
        'entity_ids': [str(item) for item in observation.get('entity_ids', [])] if isinstance(observation.get('entity_ids'), list) else [],
        'symbol_candidates': symbols,
        'region': observation.get('region'),
        'sector': observation.get('sector'),
        'supply_chain_nodes': [str(item) for item in observation.get('supply_chain_nodes', [])] if isinstance(observation.get('supply_chain_nodes'), list) else [],
        'modality': source.get('modality') or 'text',
        'raw_ref': raw_ref,
        'raw_snippet': snippet,
        'raw_snippet_ref': raw_ref,
        'safe_excerpt': snippet if not redact_required else None,
        'raw_snippet_redaction_required': redact_required,
        'export_policy': export_policy,
        'raw_uri': observation.get('url') if isinstance(observation.get('url'), str) else None,
        'raw_table_ref': observation.get('raw_table_ref') if isinstance(observation.get('raw_table_ref'), str) else None,
        'language': str(observation.get('language') or 'unknown'),
        'freshness_budget_seconds': int(source.get('freshness_budget_seconds') or 0),
        'reliability_score': float(source.get('reliability_prior') or 0.0),
        'uniqueness_score': float(source.get('uniqueness_prior') or 0.0),
        'compliance_class': source.get('compliance_class') or 'unknown',
        'redistribution_policy': source.get('redistribution_policy') or 'unknown',
        'lineage_chain': [ref for ref in [scan_file, raw_ref] if ref],
        'point_in_time_hash': 'sha256:pending',
        'source_refs': [str(item) for item in observation.get('sources', [])] if isinstance(observation.get('sources'), list) else ([str(observation.get('source'))] if observation.get('source') else []),
        'candidate_type': observation.get('candidate_type'),
        'discovery_scope': observation.get('discovery_scope'),
        'no_execution': True,
    }
    hash_input = dict(atom)
    hash_input['point_in_time_hash'] = 'sha256:pending'
    atom['point_in_time_hash'] = canonical_hash(hash_input)
    return atom


def observations_from_scan_state(scan_state: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in scan_state.get('accumulated', []) if isinstance(item, dict)]


def compile_atoms(
    scan_state: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
    generated_at: str | None = None,
    scan_file: str | None = None,
) -> dict[str, Any]:
    registry = registry or load_source_registry()
    generated = parse_ts(generated_at) or now_iso()
    atoms = [
        atom_from_observation(item, registry=registry, scan_file=scan_file, fallback_ingested_at=scan_state.get('last_updated') or generated)
        for item in observations_from_scan_state(scan_state)
    ]
    atoms.sort(key=lambda item: item['atom_id'])
    return {
        'generated_at': generated,
        'status': 'pass',
        'contract': CONTRACT,
        'atom_count': len(atoms),
        'atoms': atoms,
        'atom_hash': canonical_hash(atoms),
        'shadow_only': True,
        'no_execution': True,
    }


def write_atoms_jsonl(path: Path, atoms: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'{path.name}.tmp')
    tmp.write_text(''.join(json.dumps(atom, ensure_ascii=False, sort_keys=True) + '\n' for atom in atoms), encoding='utf-8')
    tmp.replace(path)


def safe_state_path(path: Path) -> bool:
    if not path.is_absolute():
        return False
    try:
        path.resolve(strict=False).relative_to(STATE.resolve(strict=False))
        return True
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--scan-state', default=str(SCAN_STATE))
    parser.add_argument('--registry', default=str(SOURCE_REGISTRY))
    parser.add_argument('--out', default=str(SOURCE_ATOMS_LATEST))
    parser.add_argument('--report', default=None)
    args = parser.parse_args(argv)
    out = Path(args.out)
    if not safe_state_path(out):
        print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_out_path']}, ensure_ascii=False))
        return 2
    scan_state = load_json_safe(Path(args.scan_state), {}) or {}
    registry = load_json_safe(Path(args.registry), {}) or {}
    report = compile_atoms(scan_state, registry=registry, scan_file=str(args.scan_state))
    write_atoms_jsonl(out, report['atoms'])
    if args.report:
        report_path = Path(args.report)
        if not safe_state_path(report_path):
            print(json.dumps({'status': 'blocked', 'blocking_reasons': ['unsafe_report_path']}, ensure_ascii=False))
            return 2
        atomic_write_json(report_path, report)
    print(json.dumps({'status': report['status'], 'atom_count': report['atom_count'], 'out': str(out)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
