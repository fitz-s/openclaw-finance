#!/usr/bin/env python3
"""Compile deterministic TradingAgents sidecar run requests."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from tradingagents_bridge_types import (
    DECISION_LOG,
    DEFAULT_FORBIDDEN_ACTIONS,
    PACKET,
    REPORT_ENVELOPE,
    THESIS_RESEARCH_PACKET,
    TRADINGAGENTS_RUNS,
    clean_instrument,
    ensure_dir,
    load_defaults,
    load_json,
    make_run_id,
    now_iso,
    path_artifact,
    write_json,
)
from tradingagents_model_resolution import resolve_tradingagents_role

THESIS_REGISTRY = Path('/Users/leofitz/.openclaw/workspace/finance/state/thesis-registry.json')


def _pick_target(
    manual_instrument: str | None,
    research_packet: dict[str, Any],
    thesis_registry: dict[str, Any] | None = None,
    packet: dict[str, Any] | None = None,
) -> tuple[str | None, str, dict[str, Any]]:
    if manual_instrument:
        instrument = clean_instrument(manual_instrument)
        return instrument, 'manual_instrument', {}

    selected_opportunities = research_packet.get('selected_opportunities', []) if isinstance(research_packet.get('selected_opportunities'), list) else []
    for row in selected_opportunities:
        if isinstance(row, dict):
            instrument = clean_instrument(row.get('instrument'))
            if instrument:
                return instrument, 'selected_opportunity', {
                    'selected_opportunity_id': row.get('candidate_id'),
                    'selected_opportunity_theme': row.get('theme'),
                }

    selected_theses = research_packet.get('selected_theses', []) if isinstance(research_packet.get('selected_theses'), list) else []
    for row in selected_theses:
        if isinstance(row, dict):
            instrument = clean_instrument(row.get('instrument'))
            if instrument:
                return instrument, 'selected_thesis', {
                    'selected_thesis_id': row.get('thesis_id'),
                }

    theses = thesis_registry.get('theses', []) if isinstance(thesis_registry, dict) and isinstance(thesis_registry.get('theses'), list) else []
    ranked_theses = sorted(
        [row for row in theses if isinstance(row, dict)],
        key=lambda row: (
            2 if row.get('status') == 'active' else 1 if row.get('status') == 'watch' else 0,
            str(row.get('instrument') or ''),
        ),
        reverse=True,
    )
    for row in ranked_theses:
        instrument = clean_instrument(row.get('instrument'))
        if instrument:
            return instrument, 'thesis_registry', {
                'selected_thesis_id': row.get('thesis_id'),
                'selected_thesis_status': row.get('status'),
            }

    packet_instrument = clean_instrument((packet or {}).get('instrument'))
    if packet_instrument:
        return packet_instrument, 'context_packet', {
            'packet_id': (packet or {}).get('packet_id'),
        }

    return None, 'no_target', {}


def build_request(
    *,
    mode: str = 'manual',
    instrument: str | None = None,
    analysis_date: str | None = None,
    research_packet: dict[str, Any] | None = None,
    report_envelope: dict[str, Any] | None = None,
    decision_log: dict[str, Any] | None = None,
    packet: dict[str, Any] | None = None,
    thesis_registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    defaults = load_defaults()
    model_resolution = resolve_tradingagents_role(job_name='finance-tradingagents-sidecar')
    if model_resolution.get('status') != 'supported':
        raise ValueError(f"TradingAgents model resolution failed: {model_resolution.get('unsupported_reason')}")
    research_packet = research_packet if isinstance(research_packet, dict) else (load_json(THESIS_RESEARCH_PACKET, {}) or {})
    report_envelope = report_envelope if isinstance(report_envelope, dict) else (load_json(REPORT_ENVELOPE, {}) or {})
    decision_log = decision_log if isinstance(decision_log, dict) else (load_json(DECISION_LOG, {}) or {})
    packet = packet if isinstance(packet, dict) else (load_json(PACKET, {}) or {})
    thesis_registry = thesis_registry if isinstance(thesis_registry, dict) else (load_json(THESIS_REGISTRY, {}) or {})

    selected_instrument, request_source, source_meta = _pick_target(
        instrument,
        research_packet,
        thesis_registry,
        packet,
    )
    if not selected_instrument:
        raise ValueError('no TradingAgents target instrument available')

    selected_date = analysis_date or str(report_envelope.get('as_of') or report_envelope.get('generated_at') or packet.get('as_of') or date.today().isoformat())[:10]
    run_id = make_run_id(selected_instrument, selected_date, mode)
    run_root = ensure_dir(TRADINGAGENTS_RUNS / run_id)

    request = {
        'generated_at': now_iso(),
        'run_id': run_id,
        'job_id': f'finance-tradingagents-sidecar:{mode}',
        'mode': mode,
        'instrument': selected_instrument,
        'analysis_date': selected_date,
        'request_source': request_source,
        'request_source_meta': source_meta,
        'selected_analysts': defaults.get('selected_analysts', ['market', 'social', 'news', 'fundamentals']),
        'config': {
            'llm_provider': model_resolution['provider'],
            'deep_think_llm': model_resolution['deep_model'],
            'quick_think_llm': model_resolution['quick_model'],
            'backend_url': model_resolution.get('base_url'),
            'output_language': defaults.get('output_language', 'English'),
            'max_debate_rounds': defaults.get('max_debate_rounds', 1),
            'max_risk_discuss_rounds': defaults.get('max_risk_discuss_rounds', 1),
            'max_recur_limit': defaults.get('max_recur_limit', 100),
            'timeout_seconds': defaults.get('timeout_seconds', 900),
            'data_vendors': defaults.get('data_vendors', {}),
            'tool_vendors': defaults.get('tool_vendors', {}),
            **(model_resolution.get('provider_options', {}) if isinstance(model_resolution.get('provider_options'), dict) else {}),
        },
        'model_resolution': model_resolution,
        'source_bindings': {
            'thesis_research_packet': path_artifact(THESIS_RESEARCH_PACKET),
            'report_envelope': {
                **path_artifact(REPORT_ENVELOPE),
                'report_hash': report_envelope.get('report_hash'),
                'packet_hash': report_envelope.get('packet_hash'),
            },
            'decision_log': {
                **path_artifact(DECISION_LOG),
                'decision_id': ((decision_log.get('entry') or {}).get('decision_id') if isinstance(decision_log.get('entry'), dict) else None),
            },
            'context_packet': {
                **path_artifact(PACKET),
                'packet_id': packet.get('packet_id'),
                'packet_hash': packet.get('packet_hash'),
            },
        },
        'surface_policy': {
            'context_digest_max_age_hours': defaults.get('context_digest_max_age_hours', 24),
            'reader_augmentation_max_age_hours': defaults.get('reader_augmentation_max_age_hours', 72),
            'candidate_contract_exclusion': True,
            'announce_card_input': False,
        },
        'forbidden_actions': DEFAULT_FORBIDDEN_ACTIONS,
        'review_only': True,
        'no_execution': True,
        'request_path': str(run_root / 'request.json'),
    }
    return request


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compile TradingAgents sidecar request packet.')
    parser.add_argument('--mode', default='manual')
    parser.add_argument('--instrument', default=None)
    parser.add_argument('--analysis-date', default=None)
    parser.add_argument('--out', default=None)
    args = parser.parse_args(argv)

    request = build_request(mode=args.mode, instrument=args.instrument, analysis_date=args.analysis_date)
    out = Path(args.out) if args.out else Path(request['request_path'])
    ensure_dir(out.parent)
    write_json(out, request)
    print(json.dumps({
        'status': 'pass',
        'run_id': request['run_id'],
        'instrument': request['instrument'],
        'out': str(out),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
