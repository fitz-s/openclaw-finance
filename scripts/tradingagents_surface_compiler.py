#!/usr/bin/env python3
"""Compile validated TradingAgents surfaces for reader/context consumption."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tradingagents_bridge_types import (
    TRADINGAGENTS_CONTEXT_DIGEST,
    TRADINGAGENTS_LATEST,
    TRADINGAGENTS_READER_AUGMENTATION,
    TRADINGAGENTS_STATUS,
    age_hours,
    canonical_hash,
    load_json,
    now_iso,
    write_json,
)


def build_context_digest(request: dict[str, Any], advisory: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    source_bindings = request.get('source_bindings', {}) if isinstance(request.get('source_bindings'), dict) else {}
    return {
        'generated_at': now_iso(),
        'run_id': request.get('run_id'),
        'instrument': request.get('instrument'),
        'analysis_date': request.get('analysis_date'),
        'report_hash': (source_bindings.get('report_envelope') or {}).get('report_hash'),
        'packet_hash': (source_bindings.get('context_packet') or {}).get('packet_hash'),
        'safe_bullets': (advisory.get('why_now_safe', []) + advisory.get('why_not_now_safe', []))[:6],
        'invalidators_safe': advisory.get('invalidators_safe', [])[:4],
        'required_confirmations_safe': advisory.get('required_confirmations_safe', [])[:4],
        'source_gaps_safe': advisory.get('source_gaps_safe', [])[:4],
        'risk_flags_safe': advisory.get('risk_flags_safe', [])[:4],
        'authority_rule': 'non_authoritative_context_only_not_evidence_wake_threshold_or_execution',
        'candidate_contract_exclusion': True,
        'validation_ref': str(Path(request['request_path']).parent / 'validation.json'),
        'review_only': True,
        'no_execution': True,
        'max_age_hours': validation.get('context_digest_max_age_hours', 24),
    }


def build_reader_augmentation(request: dict[str, Any], advisory: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    report_hash = validation.get('report_hash')
    label = advisory.get('summary_title_safe') or f"TradingAgents sidecar | {request.get('instrument')}"
    handle = 'TA1'
    slices = {}
    for verb in ['why', 'challenge', 'sources', 'expand', 'trace']:
        missing_fields = ['deterministic_source_promotion', 'claim_lineage'] if verb in {'sources', 'trace'} else []
        slices[verb] = {
            'handle': handle,
            'card_type': 'tradingagents_research',
            'source_id': f"tradingagents:{request.get('run_id')}:{verb}",
            'source_name': 'tradingagents_sidecar',
            'version': 'tradingagents-followup-slice-v1',
            'evidence_slice_id': f"slice:{request.get('run_id')}:{handle}:{verb}",
            'linked_claims': [],
            'linked_atoms': [],
            'linked_context_gaps': [],
            'lane_coverage': {},
            'source_health_summary': {},
            'retrieval_score': 0.0,
            'permission_metadata': {
                'review_only': True,
                'raw_thread_history_allowed': False,
                'raw_source_dump_allowed': False,
            },
            'missing_fields': missing_fields,
            'content_hash': canonical_hash({'handle': handle, 'verb': verb, 'missing_fields': missing_fields}),
            'no_execution': True,
        }
    card = {
        'handle': handle,
        'type': 'tradingagents_research',
        'label': label,
        'instrument': request.get('instrument'),
        'run_id': request.get('run_id'),
        'summary': (advisory.get('why_now_safe') or [''])[0],
        'why_now': advisory.get('why_now_safe', [])[:3],
        'why_not_now': advisory.get('why_not_now_safe', [])[:3],
        'invalidators': advisory.get('invalidators_safe', [])[:3],
        'required_confirmations': advisory.get('required_confirmations_safe', [])[:3],
        'source_gaps': advisory.get('source_gaps_safe', [])[:3],
        'risk_flags': advisory.get('risk_flags_safe', [])[:3],
        'linked_claims': [],
        'linked_atoms': [],
        'linked_context_gaps': [],
        'lane_coverage': {},
        'source_health_summary': {},
        'no_execution': True,
    }
    starter_questions = [
        {'verb': 'why', 'handle': handle, 'question': f'Why {handle}?'},
        {'verb': 'challenge', 'handle': handle, 'question': f'Challenge {handle}'},
        {'verb': 'sources', 'handle': handle, 'question': f'Sources for {handle}'},
    ]
    return {
        'generated_at': now_iso(),
        'run_id': request.get('run_id'),
        'report_hash': report_hash,
        'decision_id': ((request.get('source_bindings') or {}).get('decision_log') or {}).get('decision_id'),
        'handles': {
            handle: {
                'type': 'tradingagents_research',
                'ref': request.get('run_id'),
                'instrument': request.get('instrument'),
                'label': label,
            }
        },
        'object_cards': [card],
        'starter_questions': starter_questions,
        'starter_queries': [f"why {handle}", f"challenge {handle}", f"sources {handle}"],
        'object_alias_map': {handle: label},
        'followup_digest': [
            f"{handle}: review-only TradingAgents sidecar summary; no execution.",
            *advisory.get('why_now_safe', [])[:2],
        ],
        'followup_slice_index': {handle: slices},
        'review_only': True,
        'no_execution': True,
        'max_age_hours': validation.get('reader_augmentation_max_age_hours', 72),
    }


def compile_surfaces(run_root: Path) -> dict[str, str]:
    request = load_json(run_root / 'request.json', {}) or {}
    advisory = load_json(run_root / 'normalized' / 'advisory-decision.json', {}) or {}
    validation = load_json(run_root / 'validation.json', {}) or {}
    surface_dir = run_root / 'surface'
    surface_dir.mkdir(parents=True, exist_ok=True)

    context_digest = build_context_digest(request, advisory, validation)
    reader_augmentation = build_reader_augmentation(request, advisory, validation)

    context_path = surface_dir / 'context-digest.json'
    reader_path = surface_dir / 'reader-augmentation.json'
    write_json(context_path, context_digest)
    write_json(reader_path, reader_augmentation)
    bridge_record = {
        'generated_at': now_iso(),
        'run_id': request.get('run_id'),
        'request_path': str(run_root / 'request.json'),
        'advisory_path': str(run_root / 'normalized' / 'advisory-decision.json'),
        'validation_path': str(run_root / 'validation.json'),
        'context_digest_path': str(context_path),
        'reader_augmentation_path': str(reader_path),
        'status': validation.get('status'),
        'report_hash': validation.get('report_hash'),
        'packet_hash': validation.get('packet_hash'),
        'review_only': True,
        'no_execution': True,
    }
    bridge_record_path = run_root / 'bridge-record.json'
    write_json(bridge_record_path, bridge_record)

    latest = {
        'generated_at': now_iso(),
        'status': validation.get('status'),
        'run_id': request.get('run_id'),
        'bridge_record_path': str(bridge_record_path),
        'context_digest_path': str(context_path),
        'reader_augmentation_path': str(reader_path),
        'validation_path': str(run_root / 'validation.json'),
        'review_only': True,
        'no_execution': True,
    }
    status = {
        'generated_at': now_iso(),
        'status': validation.get('status'),
        'latest_run_id': request.get('run_id'),
        'latest_validation_status': validation.get('status'),
        'latest_reader_eligible': validation.get('reader_eligible') is True,
        'latest_context_pack_eligible': validation.get('context_pack_eligible') is True,
        'freshness_age_hours': age_hours(context_digest.get('generated_at')),
        'review_only': True,
        'no_execution': True,
    }
    write_json(TRADINGAGENTS_STATUS, status)
    if validation.get('status') == 'pass' and validation.get('context_pack_eligible') is True:
        write_json(TRADINGAGENTS_CONTEXT_DIGEST, context_digest)
    if validation.get('status') == 'pass' and validation.get('reader_eligible') is True:
        write_json(TRADINGAGENTS_READER_AUGMENTATION, reader_augmentation)
    if validation.get('status') == 'pass':
        write_json(TRADINGAGENTS_LATEST, latest)

    return {
        'bridge_record_path': str(bridge_record_path),
        'context_path': str(context_path),
        'reader_path': str(reader_path),
        'latest_path': str(TRADINGAGENTS_LATEST),
        'status_path': str(TRADINGAGENTS_STATUS),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Compile TradingAgents surfaces.')
    parser.add_argument('--run-root', required=True)
    args = parser.parse_args(argv)
    payload = compile_surfaces(Path(args.run_root))
    print(json.dumps({'status': 'pass', **payload}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
