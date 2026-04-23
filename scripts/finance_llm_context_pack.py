#!/usr/bin/env python3
"""Compile compact non-authoritative context packs for OpenClaw finance jobs."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from atomic_io import atomic_write_json, load_json_safe
from tradingagents_bridge_types import age_hours


ROOT = Path('/Users/leofitz/.openclaw')
WORKSPACE = ROOT / 'workspace'
FINANCE = WORKSPACE / 'finance'
STATE = FINANCE / 'state'
SERVICE_STATE = WORKSPACE / 'services' / 'market-ingest' / 'state'
OUT_DIR = STATE / 'llm-job-context'

PACKET = SERVICE_STATE / 'latest-context-packet.json'
WAKE = STATE / 'latest-wake-decision.json'
WATCHLIST = STATE / 'watchlist-resolved.json'
PORTFOLIO = STATE / 'portfolio-resolved.json'
WATCH_INTENT = STATE / 'watch-intent.json'
THESIS_REGISTRY = STATE / 'thesis-registry.json'
SCENARIO_CARDS = STATE / 'scenario-cards.json'
OPPORTUNITY_QUEUE = STATE / 'opportunity-queue.json'
INVALIDATOR_LEDGER = STATE / 'invalidator-ledger.json'
DECISION_LOG = STATE / 'finance-decision-log-report.json'
PRODUCT_VALIDATION = STATE / 'finance-report-product-validation.json'
DELIVERY_SAFETY = STATE / 'report-delivery-safety-check.json'
DISPATCH_ATTRIBUTION = STATE / 'dispatch-attribution.jsonl'
THESIS_OUTCOMES = STATE / 'thesis-outcomes.jsonl'
REPORT_USEFULNESS = STATE / 'report-usefulness-history.jsonl'
CAPITAL_GRAPH = STATE / 'capital-graph.json'
CAPITAL_AGENDA = STATE / 'capital-agenda.json'
DISPLACEMENT_CASES = STATE / 'displacement-cases.json'
SCENARIO_EXPOSURE = STATE / 'scenario-exposure-matrix.json'
OPTIONS_IV_SURFACE = STATE / 'options-iv-surface.json'

CANONICAL_AUTHORITY = 'ContextPacket/WakeDecision/JudgmentEnvelope/Thesis Spine state'
MAX_PACK_CHARS = 30000
REPORT_PACK = OUT_DIR / 'report-orchestrator.json'
SCANNER_PACK = OUT_DIR / 'scanner.json'
SIDECAR_PACK = OUT_DIR / 'thesis-sidecar.json'
TRADINGAGENTS_SIDECAR_PACK = OUT_DIR / 'tradingagents-sidecar.json'
WEEKLY_PACK = OUT_DIR / 'weekly-learning.json'
FOLLOWUP_PACK = OUT_DIR / 'report-followup.json'
READER_BUNDLE_DIR = STATE / 'report-reader'
CAMPAIGN_BOARD = STATE / 'campaign-board.json'
CAMPAIGN_CACHE = STATE / 'campaign-cache.json'
QUERY_PACK_OUT = STATE / 'query-packs' / 'scanner-planned.jsonl'
QUERY_PACK_REPORT = STATE / 'query-packs' / 'scanner-planned-report.json'
QUERY_PACK_CONTRACT = FINANCE / 'docs' / 'openclaw-runtime' / 'contracts' / 'query-pack-contract.md'
TRADINGAGENTS_CONTEXT_DIGEST = STATE / 'tradingagents' / 'latest-context-digest.json'
TRADINGAGENTS_STATUS = STATE / 'tradingagents' / 'status.json'
TRADINGAGENTS_DEFAULTS = FINANCE / 'ops' / 'tradingagents-sidecar.defaults.json'
TRADINGAGENTS_LOCK = FINANCE / 'ops' / 'tradingagents-upstream-lock.json'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def file_hash(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace('+00:00', 'Z')


def artifact(path: Path, *, required: bool = False) -> dict[str, Any]:
    return {
        'path': str(path),
        'exists': path.exists(),
        'mtime': mtime_iso(path),
        'hash': file_hash(path),
        'required': required,
    }


def stable_pack_id(role: str, source_artifacts: list[dict[str, Any]]) -> str:
    raw = json.dumps(
        {'role': role, 'sources': [(item.get('path'), item.get('hash')) for item in source_artifacts]},
        sort_keys=True,
        ensure_ascii=False,
    )
    return f'llm-job-context:{role}:' + hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def load(path: Path, default: Any) -> Any:
    return load_json_safe(path, default) if path.suffix != '.jsonl' else tail_jsonl(path, 5)


def tail_jsonl(path: Path, limit: int = 5) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows[-limit:]


def short(value: Any, limit: int = 220) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + '…'


def options_iv_surface_summary(surface: dict[str, Any]) -> dict[str, Any]:
    summary = surface.get('summary') if isinstance(surface.get('summary'), dict) else {}
    rows = surface.get('symbols') if isinstance(surface.get('symbols'), list) else []
    provider_set = sorted({provider for row in rows if isinstance(row, dict) for provider in row.get('provider_set', [])})
    return {
        'status': surface.get('status'),
        'surface_policy_version': surface.get('surface_policy_version') or surface.get('contract'),
        'generated_at': surface.get('generated_at'),
        'symbol_count': surface.get('symbol_count') or summary.get('symbol_count') or 0,
        'provider_set': provider_set[:8],
        'primary_source_status': surface.get('primary_source_status'),
        'primary_provider_set': surface.get('primary_provider_set', [])[:8] if isinstance(surface.get('primary_provider_set'), list) else [],
        'proxy_only_count': summary.get('proxy_only_count'),
        'missing_iv_count': summary.get('missing_iv_count'),
        'stale_or_unknown_chain_count': summary.get('stale_or_unknown_chain_count'),
        'provider_backed_count': summary.get('provider_backed_count'),
        'provider_confidence': {
            'min': summary.get('min_provider_confidence'),
            'max': summary.get('max_provider_confidence'),
        },
        'source_health_refs': surface.get('source_health_refs', [])[:12] if isinstance(surface.get('source_health_refs'), list) else [],
        'rights_policy': surface.get('rights_policy') or 'unknown',
        'derived_only': surface.get('derived_only') is True,
        'raw_payload_retained': surface.get('raw_payload_retained') is True,
        'no_execution': surface.get('no_execution') is True,
        'authority': 'source_context_only_not_judgment_wake_threshold_or_execution',
    }


def watch_symbols(watchlist: dict[str, Any], portfolio: dict[str, Any]) -> list[str]:
    out = set()
    for key in ['tickers', 'indexes', 'crypto']:
        for row in watchlist.get(key, []) if isinstance(watchlist.get(key), list) else []:
            if isinstance(row, dict) and row.get('symbol'):
                out.add(str(row['symbol']).replace('/', '-').upper())
    for key in ['stocks', 'options']:
        for row in portfolio.get(key, []) if isinstance(portfolio.get(key), list) else []:
            if isinstance(row, dict):
                symbol = row.get('underlying') or row.get('symbol')
                if symbol:
                    out.add(str(symbol).replace('/', '-').upper())
    return sorted(out)


def compact_evidence(packet: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    allowed = []
    forbidden = []
    for record in packet.get('accepted_evidence_records', []) if isinstance(packet.get('accepted_evidence_records'), list) else []:
        if not isinstance(record, dict) or not record.get('evidence_id'):
            continue
        row = {
            'evidence_id': record.get('evidence_id'),
            'layer': record.get('layer'),
            'source_kind': record.get('source_kind'),
            'instrument': record.get('instrument', []),
            'direction': record.get('direction'),
            'summary': short(record.get('normalized_summary'), 180),
            'source_artifact': str(PACKET),
            'source_ref': record.get('evidence_id'),
        }
        if record.get('quarantine', {}).get('allowed_for_judgment_support') is True:
            allowed.append(row)
        else:
            row['reason'] = record.get('quarantine', {}).get('disposition')
            forbidden.append(row)
    return allowed[:12], forbidden[:12]


def top_theses(thesis_registry: dict[str, Any], watch_intent: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    intents = {
        item.get('intent_id'): item
        for item in watch_intent.get('intents', [])
        if isinstance(item, dict) and item.get('intent_id')
    }
    rows = []
    for item in thesis_registry.get('theses', []) if isinstance(thesis_registry.get('theses'), list) else []:
        if not isinstance(item, dict) or not item.get('thesis_id'):
            continue
        if item.get('status') not in {'active', 'watch', 'candidate'}:
            continue
        intent = intents.get(item.get('linked_watch_intent'), {})
        rows.append({
            'thesis_id': item.get('thesis_id'),
            'instrument': item.get('instrument'),
            'status': item.get('status'),
            'maturity': item.get('maturity'),
            'roles': intent.get('roles', []),
            'required_confirmations': item.get('required_confirmations', [])[:3],
            'invalidators': item.get('invalidators', [])[:3],
            'evidence_refs': item.get('evidence_refs', [])[:5],
            'source_artifact': str(THESIS_REGISTRY),
            'source_ref': item.get('thesis_id'),
        })
    rows.sort(key=lambda row: (row['status'] == 'active', str(row.get('instrument') or '')), reverse=True)
    return rows[:limit]


def top_opportunities(queue: dict[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    rows = []
    for item in queue.get('candidates', []) if isinstance(queue.get('candidates'), list) else []:
        if not isinstance(item, dict) or not item.get('candidate_id'):
            continue
        if item.get('status') not in {'candidate', 'promoted'}:
            continue
        rows.append({
            'candidate_id': item.get('candidate_id'),
            'instrument': item.get('instrument'),
            'theme': short(item.get('theme'), 140),
            'status': item.get('status'),
            'score': item.get('score'),
            'source_refs': item.get('source_refs', [])[:4],
            'source_artifact': str(OPPORTUNITY_QUEUE),
            'source_ref': item.get('candidate_id'),
        })
    rows.sort(key=lambda row: float(row.get('score') or 0), reverse=True)
    return rows[:limit]


def top_invalidators(ledger: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    rows = []
    for item in ledger.get('invalidators', []) if isinstance(ledger.get('invalidators'), list) else []:
        if not isinstance(item, dict) or not item.get('invalidator_id'):
            continue
        if item.get('status') not in {'open', 'hit'}:
            continue
        rows.append({
            'invalidator_id': item.get('invalidator_id'),
            'target_type': item.get('target_type'),
            'target_id': item.get('target_id'),
            'status': item.get('status'),
            'description': short(item.get('description'), 140),
            'hit_count': item.get('hit_count'),
            'evidence_refs': item.get('evidence_refs', [])[:5],
            'source_artifact': str(INVALIDATOR_LEDGER),
            'source_ref': item.get('invalidator_id'),
        })
    rows.sort(key=lambda row: (int(row.get('hit_count') or 0), str(row.get('invalidator_id'))), reverse=True)
    return rows[:limit]


def recent_rows(path: Path, keys: set[str], limit: int = 5) -> list[dict[str, Any]]:
    out = []
    for row in tail_jsonl(path, limit):
        compact = {key: value for key, value in row.items() if key in keys}
        compact['source_artifact'] = str(path)
        compact['source_ref'] = row.get('event_id')
        out.append(compact)
    return out


def base_pack(role: str, source_artifacts: list[dict[str, Any]], *, job_goal: str, allowed_outputs: list[str], forbidden_actions: list[str]) -> dict[str, Any]:
    return {
        'pack_id': stable_pack_id(role, source_artifacts),
        'pack_role': role,
        'generated_at': now_iso(),
        'pack_is_not_authority': True,
        'canonical_authority': CANONICAL_AUTHORITY,
        'source_artifacts': source_artifacts,
        'job_role': role,
        'job_goal': job_goal,
        'allowed_outputs': allowed_outputs,
        'forbidden_actions': forbidden_actions,
    }


def validate_size(pack: dict[str, Any]) -> None:
    encoded = json.dumps(pack, ensure_ascii=False, sort_keys=True)
    if len(encoded) > MAX_PACK_CHARS:
        raise ValueError(f'{pack.get("pack_role")} pack too large: {len(encoded)} > {MAX_PACK_CHARS}')


def load_tradingagents_digest(path: Path | None = None) -> dict[str, Any] | None:
    path = path or TRADINGAGENTS_CONTEXT_DIGEST
    payload = load_json_safe(path, {}) or {}
    if not isinstance(payload, dict) or not payload:
        return None
    if payload.get('review_only') is not True or payload.get('no_execution') is not True:
        return None
    if payload.get('candidate_contract_exclusion') is not True:
        return None
    max_age = payload.get('max_age_hours')
    current_age = age_hours(str(payload.get('generated_at') or ''))
    if isinstance(max_age, (int, float)) and current_age is not None and current_age > float(max_age):
        return None
    return {
        key: payload.get(key)
        for key in [
            'generated_at',
            'run_id',
            'instrument',
            'analysis_date',
            'report_hash',
            'packet_hash',
            'safe_bullets',
            'invalidators_safe',
            'required_confirmations_safe',
            'source_gaps_safe',
            'risk_flags_safe',
            'authority_rule',
            'candidate_contract_exclusion',
            'validation_ref',
            'review_only',
            'no_execution',
            'max_age_hours',
        ]
    }


def build_packs() -> dict[str, dict[str, Any]]:
    packet = load_json_safe(PACKET, {}) or {}
    wake = load_json_safe(WAKE, {}) or {}
    watchlist = load_json_safe(WATCHLIST, {}) or {}
    portfolio = load_json_safe(PORTFOLIO, {}) or {}
    watch_intent = load_json_safe(WATCH_INTENT, {}) or {}
    thesis_registry = load_json_safe(THESIS_REGISTRY, {}) or {}
    opportunities = load_json_safe(OPPORTUNITY_QUEUE, {}) or {}
    invalidators = load_json_safe(INVALIDATOR_LEDGER, {}) or {}
    product_validation = load_json_safe(PRODUCT_VALIDATION, {}) or {}
    delivery_safety = load_json_safe(DELIVERY_SAFETY, {}) or {}
    allowed_evidence, forbidden_evidence = compact_evidence(packet)
    thesis_rows = top_theses(thesis_registry, watch_intent)
    opportunity_rows = top_opportunities(opportunities)
    invalidator_rows = top_invalidators(invalidators)
    known_symbols = watch_symbols(watchlist, portfolio)
    capital_graph = load_json_safe(CAPITAL_GRAPH, {}) or {}
    capital_agenda = load_json_safe(CAPITAL_AGENDA, {}) or {}
    displacement_cases_data = load_json_safe(DISPLACEMENT_CASES, {}) or {}
    scenario_exposure = load_json_safe(SCENARIO_EXPOSURE, {}) or {}
    options_iv_surface = load_json_safe(OPTIONS_IV_SURFACE, {}) or {}
    options_iv_summary = options_iv_surface_summary(options_iv_surface)

    report_sources = [artifact(PACKET, required=True), artifact(WAKE, required=True), artifact(THESIS_REGISTRY), artifact(OPPORTUNITY_QUEUE), artifact(INVALIDATOR_LEDGER), artifact(OPTIONS_IV_SURFACE)]
    report = base_pack(
        'report_orchestrator',
        report_sources,
        job_goal='Adjudicate Thesis Spine deltas into a bounded JudgmentEnvelope candidate, then run deterministic closure.',
        allowed_outputs=['judgment-envelope-candidate.json', 'safety-gated product markdown only after closure'],
        forbidden_actions=['invent_facts', 'use_forbidden_evidence', 'write_report_prose_before_safety', 'execution', 'threshold_mutation'],
    )
    report.update({
        'wake': {key: wake.get(key) for key in ['wake_class', 'wake_reason', 'packet_id', 'packet_hash', 'policy_version']},
        'packet': {key: packet.get(key) for key in ['packet_id', 'packet_hash', 'instrument', 'as_of', 'policy_version']},
        'top_thesis_deltas': thesis_rows,
        'top_opportunity_candidates': opportunity_rows,
        'top_invalidators': invalidator_rows,
        'allowed_evidence_refs': allowed_evidence,
        'forbidden_evidence_refs': forbidden_evidence,
        'candidate_contract': {
            'path': str(STATE / 'judgment-envelope-candidate.json'),
            'required_fields': ['packet_id', 'packet_hash', 'thesis_state', 'actionability', 'why_now', 'why_not', 'invalidators', 'required_confirmations', 'evidence_refs', 'thesis_refs', 'scenario_refs', 'opportunity_candidate_refs', 'invalidator_refs', 'policy_version', 'model_id'],
            'scheduled_context_allowed_thesis_states': ['no_trade', 'watch'],
            'event_wake_allowed_thesis_states': ['watch', 'lean_long', 'lean_short', 'no_trade', 'reduce', 'exit'],
            'evidence_rule': 'candidate evidence_refs must be subset of allowed_evidence_refs',
        },
        'required_commands': [
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_llm_context_pack.py',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/judgment_envelope_gate.py --allow-fallback --adjudication-mode scheduled_context',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_decision_report_render.py',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_report_product_validator.py',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_decision_log_compiler.py',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_report_delivery_safety.py',
        ],
        'final_output_rule': 'Only output finance-decision-report-envelope.markdown after delivery safety status=pass; otherwise health-only markdown.',
        'capital_agenda_items': [
            {
                'agenda_id': item.get('agenda_id'),
                'agenda_type': item.get('agenda_type'),
                'priority_score': item.get('priority_score'),
                'attention_justification': item.get('attention_justification'),
                'linked_thesis_ids': item.get('linked_thesis_ids', [])[:5],
                'displacement_case_refs': item.get('displacement_case_refs', [])[:3],
                'required_questions': item.get('required_questions', [])[:3],
            }
            for item in (capital_agenda.get('agenda_items', []) if isinstance(capital_agenda.get('agenda_items'), list) else [])[:5]
        ],
        'displacement_cases': [
            {
                'case_id': c.get('case_id'),
                'candidate_instrument': c.get('candidate_instrument'),
                'displaced_instrument': c.get('displaced_instrument'),
                'overlap_type': c.get('overlap_type'),
                'justification': c.get('justification'),
            }
            for c in (displacement_cases_data.get('cases', []) if isinstance(displacement_cases_data.get('cases'), list) else [])[:5]
        ],
        'capital_graph_summary': {
            'graph_hash': capital_graph.get('graph_hash'),
            'node_count': capital_graph.get('node_count', 0),
            'edge_count': capital_graph.get('edge_count', 0),
            'hedge_coverage': capital_graph.get('hedge_coverage', {}),
            'bucket_utilization': capital_graph.get('bucket_utilization', {}),
        } if capital_graph.get('graph_hash') else None,
        'options_iv_surface_summary': options_iv_summary,
        'options_iv_authority_rule': 'source_context_only; excluded from candidate_contract.required_fields and JudgmentEnvelope evidence authority',
    })
    ta_digest = load_tradingagents_digest()
    if ta_digest:
        report['tradingagents_sidecar'] = ta_digest

    scanner_sources = [artifact(WATCHLIST), artifact(PORTFOLIO), artifact(THESIS_REGISTRY), artifact(OPPORTUNITY_QUEUE), artifact(INVALIDATOR_LEDGER)]
    scanner = base_pack(
        'scanner',
        scanner_sources,
        job_goal='Plan bounded QueryPack candidates for deterministic source acquisition; preserve legacy observation output only as a compatibility bridge.',
        allowed_outputs=[str(QUERY_PACK_OUT), str(QUERY_PACK_REPORT), 'finance/buffer/{YYYY-MM-DD}-scan-{HHMM}.json legacy fallback', 'machine summary only'],
        forbidden_actions=['user_message', 'delivery', 'held_or_watchlist_as_unknown', 'free_form_web_search_as_canonical_ingestion', 'execution', 'threshold_mutation'],
    )
    scanner.update({
        'scanner_canonical_role': 'planner_first_legacy_observation_bridge',
        'planner_prompt_version': 'query-planner-v1',
        'free_form_web_search_canonical_ingestion': False,
        'planner_is_not_evidence': True,
        'planner_output_path': str(QUERY_PACK_OUT),
        'planner_report_path': str(QUERY_PACK_REPORT),
        'query_pack_contract_ref': str(QUERY_PACK_CONTRACT),
        'query_pack_contract': {
            'contract': 'query-pack-v1',
            'additional_properties_allowed': False,
            'required_fields': [
                'pack_id', 'lane', 'purpose', 'query', 'freshness', 'allowed_domains',
                'required_entities', 'max_results', 'authority_level', 'forbidden',
                'planner_not_evidence', 'pack_is_not_authority', 'no_execution',
            ],
            'allowed_lanes': ['market_structure', 'corp_filing_ir', 'news_policy_narrative', 'real_economy_alt', 'human_field_private', 'internal_private'],
            'allowed_purposes': ['source_discovery', 'source_reading', 'claim_closure', 'followup_slice', 'sidecar_synthesis'],
            'authority_rule': 'QueryPack may request deterministic fetches but cannot satisfy evidence, wake, judgment, delivery, or execution authority.',
        },
        'tool_policy': {
            'planning_only': True,
            'parallel_tool_calls': False,
            'allowed_tools': ['read_context_pack', 'emit_query_pack_json'],
            'forbidden_tools': ['free_form_web_search_as_evidence', 'write_canonical_state', 'mutate_thresholds', 'deliver_discord'],
            'tool_output_trust': 'untrusted_until_validated_by_deterministic_fetcher',
        },
        'known_symbols_must_not_satisfy_unknown_discovery': known_symbols[:80],
        'fixed_search_budget': {
            'market_hours': ['invalidator_check', 'opportunity_followup', 'unknown_discovery'],
            'offhours': ['macro_scenario', 'opportunity_followup', 'unknown_discovery'],
            'unknown_discovery_minimum_attempts': 1,
        },
        'observation_schema_extension': {
            'candidate_type': 'unknown_discovery|thesis_update|invalidator_check|scenario_update',
            'object_links': {'thesis_refs': [], 'scenario_refs': [], 'opportunity_candidate_refs': [], 'invalidator_refs': []},
            'supports': [],
            'conflicts_with': [],
            'confirmation_needed': [],
            'unknown_discovery_exhausted_reason': 'required when no unknown candidate is found',
        },
        'top_thesis_deltas': thesis_rows[:6],
        'top_opportunity_candidates': opportunity_rows[:6],
        'top_invalidators': invalidator_rows[:6],
        'required_commands': [
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/query_pack_planner.py',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_worker.py',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/gate_evaluator.py',
        ],
        'legacy_observation_bridge': {
            'enabled': True,
            'status': 'compatibility_only_until_finance_worker_reducer_migration',
            'observations_are_not_canonical_ingestion': True,
        },
        'final_output_rule': 'Return empty string or one machine summary line only.',
    })

    sidecar_sources = [artifact(OPPORTUNITY_QUEUE), artifact(INVALIDATOR_LEDGER), artifact(THESIS_REGISTRY), artifact(STATE / 'thesis-research-packet.json')]
    sidecar = base_pack(
        'thesis_sidecar',
        sidecar_sources,
        job_goal='Run bounded research artifact flow using existing sidecar scripts.',
        allowed_outputs=['thesis-dossiers/*.json', 'custom-metrics/*.json', 'scenario-cards.json', 'thesis-research-sidecar-report.json'],
        forbidden_actions=['user_delivery', 'discord', 'execution', 'threshold_mutation', 'market_recommendation'],
    )
    sidecar.update({
        'reuse_existing_scripts': [
            str(FINANCE / 'scripts' / 'thesis_research_packet.py'),
            str(FINANCE / 'scripts' / 'custom_metric_compiler.py'),
            str(FINANCE / 'scripts' / 'scenario_card_builder.py'),
            str(FINANCE / 'scripts' / 'thesis_research_sidecar.py'),
        ],
        'top_opportunity_candidates': opportunity_rows[:6],
        'top_invalidators': invalidator_rows[:6],
        'required_commands': [
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_llm_context_pack.py',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/thesis_research_sidecar.py',
        ],
        'final_output_rule': 'No Discord/user output; write artifacts only.',
    })

    tradingagents_sources = [
        artifact(OPPORTUNITY_QUEUE),
        artifact(INVALIDATOR_LEDGER),
        artifact(THESIS_REGISTRY),
        artifact(STATE / 'thesis-research-packet.json'),
        artifact(TRADINGAGENTS_STATUS),
        artifact(TRADINGAGENTS_DEFAULTS),
        artifact(TRADINGAGENTS_LOCK),
    ]
    tradingagents_sidecar = base_pack(
        'tradingagents_sidecar',
        tradingagents_sources,
        job_goal='Run TradingAgents as a review-only research sidecar and publish only validator-gated advisory artifacts.',
        allowed_outputs=[
            'state/tradingagents/runs/**',
            str(TRADINGAGENTS_CONTEXT_DIGEST),
            'state/tradingagents/latest-reader-augmentation.json',
            'machine summary only',
        ],
        forbidden_actions=['user_delivery', 'discord', 'execution', 'threshold_mutation', 'wake_mutation', 'canonical_report_write', 'evidence_promotion'],
    )
    tradingagents_sidecar.update({
        'reuse_existing_scripts': [
            str(FINANCE / 'scripts' / 'finance_llm_context_pack.py'),
            str(FINANCE / 'scripts' / 'thesis_research_packet.py'),
            str(FINANCE / 'scripts' / 'tradingagents_sidecar_job.py'),
        ],
        'required_commands': [
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_llm_context_pack.py',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/thesis_research_packet.py',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/tradingagents_sidecar_job.py --mode offhours',
        ],
        'context_digest_path': str(TRADINGAGENTS_CONTEXT_DIGEST),
        'status_path': str(TRADINGAGENTS_STATUS),
        'defaults_path': str(TRADINGAGENTS_DEFAULTS),
        'lock_path': str(TRADINGAGENTS_LOCK),
        'final_output_rule': 'No Discord/user output; write TradingAgents sidecar artifacts only.',
    })

    telemetry_keys = {
        'event_id', 'logged_at', 'wake_class', 'threshold_should_send', 'threshold_report_type',
        'execution_decision', 'operator_action', 'thesis_id', 'instrument', 'thesis_status',
        'product_validation_status', 'report_renderer', 'product_status', 'delivery_safety_status',
        'usefulness_score', 'noise_tokens', 'delta_density', 'thesis_ref_count',
        'opportunity_ref_count', 'invalidator_ref_count',
    }
    weekly_sources = [artifact(DECISION_LOG), artifact(PRODUCT_VALIDATION), artifact(DELIVERY_SAFETY), artifact(DISPATCH_ATTRIBUTION), artifact(THESIS_OUTCOMES), artifact(REPORT_USEFULNESS)]
    weekly = base_pack(
        'weekly_learning',
        weekly_sources,
        job_goal='Review finance pipeline telemetry and recommend safe system improvements.',
        allowed_outputs=['finance-weekly-learning-review.json', 'Fact/Interpretation/Recommendation discord summary'],
        forbidden_actions=['market_advice', 'automatic_threshold_mutation', 'execution', 'raw_flex_memory_write'],
    )
    weekly.update({
        'current_quality': {
            'product_validation_status': product_validation.get('status'),
            'delivery_safety_status': delivery_safety.get('status'),
        },
        'dispatch_attribution_recent': recent_rows(DISPATCH_ATTRIBUTION, telemetry_keys),
        'thesis_outcomes_recent': recent_rows(THESIS_OUTCOMES, telemetry_keys),
        'report_usefulness_recent': recent_rows(REPORT_USEFULNESS, telemetry_keys),
        'recommendation_targets_allowed': ['policy', 'schema', 'tests', 'prompt', 'model_routing'],
        'required_commands': [
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/signal_learner.py',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/calibration_loop.py',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_learning_review_packet.py',
            '/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/finance/scripts/finance_learning_review_packet_audit.py --markdown',
        ],
        'final_output_rule': 'Output weekly learning review only; no market advice or automatic threshold mutation.',
    })

    # report_followup: rehydration pack for review room deep-dive
    latest_bundle = None
    if READER_BUNDLE_DIR.is_dir():
        bundles = sorted(READER_BUNDLE_DIR.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        if bundles:
            latest_bundle = load_json_safe(bundles[0], {}) or {}
    bundle_summary = {}
    if isinstance(latest_bundle, dict) and latest_bundle:
        handles = latest_bundle.get('handles', {}) if isinstance(latest_bundle.get('handles'), dict) else {}
        first_handles = dict(list(handles.items())[:12])
        bundle_summary = {
            'bundle_id': latest_bundle.get('bundle_id'),
            'report_handle': latest_bundle.get('report_handle'),
            'handles': first_handles,
            'object_alias_map': latest_bundle.get('object_alias_map', {}),
            'campaign_alias_map': latest_bundle.get('campaign_alias_map', {}),
            'followup_digest': latest_bundle.get('followup_digest', []),
            'starter_queries': latest_bundle.get('starter_queries', []),
        }
    followup_sources = [artifact(READER_BUNDLE_DIR / 'latest.json')]
    followup = base_pack(
        'report_followup',
        followup_sources,
        job_goal='Answer follow-up questions about a specific object from the latest finance report. Rehydrate from the reader bundle, not from thread history.',
        allowed_outputs=['structured_answer_only'],
        forbidden_actions=['execution', 'threshold_mutation', 'new_unsourced_market_call', 'raw_state_dump', 'thread_history_as_context', 'autonomous_judgment'],
    )
    followup.update({
        'reader_bundle_summary': bundle_summary,
        'followup_bundle_path': str(READER_BUNDLE_DIR / 'latest.json'),
        'campaign_board_path': str(CAMPAIGN_BOARD),
        'campaign_cache_path': str(CAMPAIGN_CACHE),
        'answer_format': {
            'required_sections': ['Fact', 'Interpretation', 'Unknown / To Verify', 'What Would Change My Mind'],
            'interrogation_verbs': ['why', 'challenge', 'compare', 'scenario', 'sources', 'expand'],
        },
        'starter_queries': latest_bundle.get('starter_queries', []) if isinstance(latest_bundle, dict) else [],
        'rehydration_rule': 'Always reconstruct context from the immutable bundle + selected handle. Thread history is UI, bundle is memory.',
        'final_output_rule': 'Structured answer only. No new report, no new judgment, no Discord delivery.',
    })

    packs = {
        'report-orchestrator': report,
        'scanner': scanner,
        'thesis-sidecar': sidecar,
        'tradingagents-sidecar': tradingagents_sidecar,
        'weekly-learning': weekly,
        'report-followup': followup,
    }
    for pack in packs.values():
        validate_size(pack)
    return packs


def write_packs(packs: dict[str, dict[str, Any]], out_dir: Path = OUT_DIR) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        'report-orchestrator': out_dir / 'report-orchestrator.json',
        'scanner': out_dir / 'scanner.json',
        'thesis-sidecar': out_dir / 'thesis-sidecar.json',
        'tradingagents-sidecar': out_dir / 'tradingagents-sidecar.json',
        'weekly-learning': out_dir / 'weekly-learning.json',
        'report-followup': out_dir / 'report-followup.json',
    }
    for name, pack in packs.items():
        atomic_write_json(paths[name], pack)
    return {name: str(path) for name, path in paths.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--out-dir', default=str(OUT_DIR))
    args = parser.parse_args(argv)
    packs = build_packs()
    paths = write_packs(packs, Path(args.out_dir))
    print(json.dumps({'status': 'pass', 'pack_count': len(paths), 'out_dir': str(args.out_dir), 'packs': paths}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
