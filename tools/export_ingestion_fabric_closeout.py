#!/usr/bin/env python3
"""Export reviewer-visible ingestion fabric closeout evidence."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FINANCE = Path(__file__).resolve().parents[1]
DOCS = FINANCE / 'docs' / 'openclaw-runtime'
STATE = FINANCE / 'state'
LEDGER = DOCS / 'ingestion-fabric-phase-ledger.json'
CLOSEOUT = DOCS / 'ingestion-fabric-closeout.json'

ARTIFACTS = {
    'query_pack_planner': FINANCE / 'scripts' / 'query_pack_planner.py',
    'brave_web_fetcher': FINANCE / 'scripts' / 'brave_web_search_fetcher.py',
    'brave_news_fetcher': FINANCE / 'scripts' / 'brave_news_search_fetcher.py',
    'brave_llm_context_reader': FINANCE / 'scripts' / 'brave_llm_context_fetcher.py',
    'brave_answers_sidecar': FINANCE / 'scripts' / 'brave_answers_sidecar.py',
    'source_health_monitor': FINANCE / 'scripts' / 'source_health_monitor.py',
    'source_memory_index': FINANCE / 'scripts' / 'source_memory_index.py',
    'reader_bundle': FINANCE / 'scripts' / 'finance_report_reader_bundle.py',
    'followup_router': FINANCE / 'scripts' / 'finance_followup_context_router.py',
    'parent_handoff': DOCS / 'parent-ingestion-handoff.md',
    'parent_handoff_contract': DOCS / 'parent-ingestion-handoff-contract.json',
    'source_health': STATE / 'source-health.json',
    'latest_reader_bundle': STATE / 'report-reader' / 'latest.json',
}

MONITORING = {
    'source_health_status': STATE / 'source-health.json',
    'source_health_history': STATE / 'source-health-history.jsonl',
    'query_registry': STATE / 'query-registry.jsonl',
    'source_memory_index': STATE / 'source-memory-index.json',
    'lane_watermarks': STATE / 'lane-watermarks.json',
    'reader_bundle_latest': STATE / 'report-reader' / 'latest.json',
    'undercurrents': STATE / 'undercurrents.json',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding='utf-8', errors='replace').splitlines() if line.strip())


def phase_summary(ledger: dict[str, Any]) -> dict[str, Any]:
    phases = ledger.get('phases', []) if isinstance(ledger.get('phases'), list) else []
    statuses: dict[str, int] = {}
    for phase in phases:
        status = str(phase.get('status') or 'unknown')
        statuses[status] = statuses.get(status, 0) + 1
    return {
        'phase_count': len(phases),
        'statuses': statuses,
        'completed_phases': [phase.get('phase') for phase in phases if phase.get('status') == 'completed'],
        'pending_phases': [phase.get('phase') for phase in phases if phase.get('status') != 'completed'],
        'all_completed': bool(phases) and all(phase.get('status') == 'completed' for phase in phases),
    }


def artifact_matrix() -> dict[str, dict[str, Any]]:
    return {
        name: {
            'path': str(path),
            'exists': path.exists(),
            'size': path.stat().st_size if path.exists() and path.is_file() else None,
        }
        for name, path in ARTIFACTS.items()
    }


def monitoring_status() -> dict[str, Any]:
    source_health = load_json(STATE / 'source-health.json', {}) or {}
    bundle = load_json(STATE / 'report-reader' / 'latest.json', {}) or {}
    return {
        'source_health_status': source_health.get('status'),
        'source_count': source_health.get('source_count', 0),
        'stale_reuse_guard': (source_health.get('stale_reuse_guard') or {}).get('status'),
        'source_health_history_count': jsonl_count(STATE / 'source-health-history.jsonl'),
        'query_registry_count': jsonl_count(STATE / 'query-registry.jsonl'),
        'reader_bundle_has_slice_index': bool(bundle.get('followup_slice_index')),
        'reader_bundle_slice_handles': len(bundle.get('followup_slice_index', {}) if isinstance(bundle.get('followup_slice_index'), dict) else {}),
        'monitoring_artifacts': {
            name: {'path': str(path), 'exists': path.exists()}
            for name, path in MONITORING.items()
        },
    }


def build_closeout() -> dict[str, Any]:
    ledger = load_json(LEDGER, {}) or {}
    phases = phase_summary(ledger)
    return {
        'generated_at': now_iso(),
        'contract': 'ingestion-fabric-closeout-v1',
        'status': 'complete' if phases['all_completed'] else 'incomplete',
        'north_star': ledger.get('north_star'),
        'design_rule': ledger.get('design_rule'),
        'phase_summary': phases,
        'artifact_matrix': artifact_matrix(),
        'monitoring': monitoring_status(),
        'orr_readiness_checklist': {
            'launch_criteria_defined': True,
            'security_governance_review_required_before_parent_cutover': True,
            'runbook_required_before_parent_cutover': True,
            'go_no_go_owner': 'parent_runtime_owner',
            'status': 'finance_local_ready_parent_cutover_pending',
        },
        'rollout_monitoring': {
            'strategy': 'feature_flagged_shadow_then_canary_then_parent_activation',
            'control_population': 'legacy scanner/report path',
            'canary_population': 'parent runtime with finance ingestion flags enabled',
            'go_no_go_metrics': [
                'source_health_status',
                'stale_reuse_guard',
                'query_pack_count',
                'fetch_failure_rate',
                'followup_slice_coverage',
                'discord_primary_route_card_only_count',
            ],
            'actionable_alerts_required': True,
        },
        'rollback': {
            'disable_flags': [
                'FINANCE_QUERY_PACK_PLANNER_ENABLED',
                'FINANCE_DETERMINISTIC_BRAVE_FETCHERS_ENABLED',
                'FINANCE_SOURCE_HEALTH_PARENT_CANONICAL_ENABLED',
                'FINANCE_CLAIM_GRAPH_PACKET_ENABLED',
                'FINANCE_UNDERCURRENT_BOARD_MUTATION_ENABLED',
                'FINANCE_FOLLOWUP_SLICE_REHYDRATION_ENABLED',
            ],
            'fallback_primary': 'complete_readable_discord_primary_report',
            'forbidden_fallback': 'route_card_only_primary',
            'parent_runtime_rollback_required_for_active_cutover': True,
        },
        'residual_risks': [
            'Parent market-ingest runtime is not mutated in this finance-local campaign.',
            'Live Brave API calls remain untested in this branch because local quota was degraded and phases used dry-run/mocked tests.',
            'Active Discord thread listener/follow-up routing still requires parent runtime cutover.',
            'Claim/entity matching remains heuristic until parent semantic normalizer adopts claim graph contracts.',
        ],
        'operational_handoff': {
            'owner': 'parent_openclaw_runtime_owner',
            'finance_artifact_owner': 'finance_repo',
            'escalation_channel': 'current OpenClaw/Codex thread plus parent runtime review',
            'runbook_required': True,
            'incident_state_notes_required': True,
        },
        'verification_evidence': [
            'python3 -m pytest -q tests',
            'python3 -m compileall -q scripts tools tests',
            'python3 tools/audit_operating_model.py',
            'python3 tools/audit_benchmark_boundary.py',
            'phase-specific tests recorded in commit trailers',
        ],
        'no_execution': True,
    }


def main() -> int:
    report = build_closeout()
    CLOSEOUT.parent.mkdir(parents=True, exist_ok=True)
    CLOSEOUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'out': str(CLOSEOUT), 'all_completed': report['phase_summary']['all_completed']}, ensure_ascii=False))
    return 0 if report['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
