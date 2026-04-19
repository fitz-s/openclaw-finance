#!/usr/bin/env python3
"""Export reviewer-visible source-to-campaign campaign closeout metrics."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

FINANCE = Path(__file__).resolve().parents[1]
STATE = FINANCE / 'state'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'source-to-campaign-closeout.json'
REVIEWER = FINANCE / 'docs' / 'openclaw-runtime' / 'reviewer-packets'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def raw_snippet_export_count(reviewer_dir: Path = REVIEWER) -> int:
    count = 0
    for path in reviewer_dir.glob('*.json'):
        text = path.read_text(encoding='utf-8', errors='replace')
        count += text.count('"raw_snippet":')
    return count


def source_metrics(source_health: dict[str, Any]) -> dict[str, Any]:
    sources = [row for row in source_health.get('sources', []) if isinstance(row, dict)]
    stale_or_unknown = [row for row in sources if row.get('freshness_status') in {'stale', 'unknown'}]
    return {
        'source_count': source_health.get('source_count') or len(sources),
        'freshness_sla_breach_rate': round(len(stale_or_unknown) / len(sources), 4) if sources else None,
        'source_health_status': source_health.get('status'),
    }


def campaign_metrics(campaign_board: dict[str, Any]) -> dict[str, Any]:
    campaigns = [row for row in campaign_board.get('campaigns', []) if isinstance(row, dict)]
    diversities = [float(row.get('source_diversity') or 0) for row in campaigns]
    gaps = [len(row.get('known_unknowns', []) if isinstance(row.get('known_unknowns'), list) else []) for row in campaigns]
    return {
        'campaign_count': len(campaigns),
        'source_diversity_per_campaign': round(sum(diversities) / len(diversities), 4) if diversities else None,
        'context_gap_rate': round(sum(1 for value in gaps if value > 0) / len(gaps), 4) if gaps else None,
    }


def followup_metrics(route: dict[str, Any]) -> dict[str, Any]:
    return {
        'followup_grounding_failure_rate': 1.0 if route.get('insufficient_data') else 0.0 if route else None,
        'latest_route_status': route.get('status'),
        'latest_route_has_coverage': isinstance(route.get('evidence_slice_coverage'), dict),
    }


def iv_metrics(options_iv: dict[str, Any]) -> dict[str, Any]:
    summary = options_iv.get('summary') if isinstance(options_iv.get('summary'), dict) else {}
    symbols = summary.get('symbol_count') or 0
    stale = summary.get('stale_or_unknown_chain_count') or 0
    return {
        'iv_signal_staleness_rate': round(stale / symbols, 4) if symbols else None,
        'options_iv_status': options_iv.get('status'),
        'options_iv_proxy_only_count': summary.get('proxy_only_count'),
    }


def phase_summary(ledger: dict[str, Any]) -> dict[str, Any]:
    phases = [row for row in ledger.get('phases', []) if isinstance(row, dict)]
    return {
        'phase_count': len(phases),
        'completed_count': sum(1 for row in phases if row.get('status') == 'completed'),
        'pending': [row.get('phase') for row in phases if row.get('status') != 'completed'],
    }


def build_closeout(state: Path = STATE, reviewer_dir: Path = REVIEWER) -> dict[str, Any]:
    source_health = load_json(FINANCE.parent / 'services' / 'market-ingest' / 'state' / 'source-health.json', {}) or {}
    campaign_board = load_json(state / 'campaign-board.json', {}) or {}
    route = load_json(state / 'followup-context-route.json', {}) or {}
    options_iv = load_json(state / 'options-iv-surface.json', {}) or {}
    gate = load_json(state / 'source-to-campaign-cutover-gate.json', {}) or {}
    ledger = load_json(FINANCE / 'docs' / 'openclaw-runtime' / 'source-to-campaign-phase-ledger.json', {}) or {}
    return {
        'generated_at': now_iso(),
        'contract': 'source-to-campaign-closeout-v1',
        'phase_summary': phase_summary(ledger),
        'cutover_gate': {
            'status': gate.get('status'),
            'blocking_reasons': gate.get('blocking_reasons') or [],
            'readiness_is_authority': gate.get('readiness_is_authority') is True,
        },
        'metrics': {
            **source_metrics(source_health),
            **campaign_metrics(campaign_board),
            **followup_metrics(route),
            **iv_metrics(options_iv),
            'raw_snippet_export_count': raw_snippet_export_count(reviewer_dir),
            'inactive_thread_pruned_count': None,
        },
        'rollback': [
            'Ignore source-to-campaign cutover gate output; current report path remains intact.',
            'Disable optional report archive / cutover gate / IV surface calls without affecting primary report generation.',
            'Use existing discord_primary_markdown fallback if board/package surfaces degrade.',
        ],
        'no_execution': True,
        'no_wake_mutation': True,
        'no_delivery_mutation': True,
        'no_threshold_mutation': True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Export source-to-campaign closeout metrics.')
    parser.add_argument('--out', default=str(OUT))
    args = parser.parse_args(argv)
    report = build_closeout()
    write_json(Path(args.out), report)
    print(json.dumps({'status': 'pass', 'out': args.out, 'cutover_status': report['cutover_gate']['status']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
