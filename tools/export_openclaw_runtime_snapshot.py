#!/usr/bin/env python3
"""Export sanitized OpenClaw runtime context for GitHub reviewers."""
from __future__ import annotations

import json
import shutil
import subprocess
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FINANCE = Path(__file__).resolve().parents[1]
OPENCLAW_HOME = FINANCE.parents[1]
WORKSPACE = OPENCLAW_HOME / 'workspace'
OUT = FINANCE / 'docs' / 'openclaw-runtime'
CONTRACTS_OUT = OUT / 'contracts'
CRON_JOBS = OPENCLAW_HOME / 'cron' / 'jobs.json'
MODEL_ROLES = WORKSPACE / 'ops' / 'model-roles.json'
STATE = FINANCE / 'state'
REVIEW_2026_04_18 = '/Users/leofitz/Downloads/review 2026-04-18.md'

FINANCE_JOB_NAMES = {
    'finance-subagent-scanner',
    'finance-subagent-scanner-offhours',
    'finance-immediate-alert',
    'finance-premarket-brief',
    'finance-premarket-delivery-watchdog',
    'finance-midday-operator-review',
    'finance-weekly-learning-review',
    'finance-thesis-sidecar',
    'finance-tradingagents-sidecar',
    'finance-report-renderer',
    'finance-watcher-update',
}

CONTRACT_DOCS = [
    WORKSPACE / 'systems' / 'finance-openclaw-runtime-contract.md',
    WORKSPACE / 'systems' / 'finance-report-contract.md',
    WORKSPACE / 'systems' / 'finance-gate-taxonomy.md',
    WORKSPACE / 'systems' / 'thesis-spine-contract.md',
    WORKSPACE / 'systems' / 'thesis-card-contract.md',
    WORKSPACE / 'systems' / 'scenario-card-contract.md',
    WORKSPACE / 'systems' / 'opportunity-queue-contract.md',
    WORKSPACE / 'systems' / 'invalidator-ledger-contract.md',
    WORKSPACE / 'systems' / 'judgment-contract.md',
    WORKSPACE / 'systems' / 'wake-policy.md',
    WORKSPACE / 'systems' / 'risk-gates.md',
    WORKSPACE / 'systems' / 'tradingagents-bridge-contract.md',
    WORKSPACE / 'systems' / 'openclaw-tradingagents-model-resolution-contract.md',
]

SCHEMA_DOCS = [
    WORKSPACE / 'schemas' / 'watch-intent.schema.json',
    WORKSPACE / 'schemas' / 'thesis-card.schema.json',
    WORKSPACE / 'schemas' / 'scenario-card.schema.json',
    WORKSPACE / 'schemas' / 'opportunity-queue.schema.json',
    WORKSPACE / 'schemas' / 'invalidator-ledger.schema.json',
    WORKSPACE / 'schemas' / 'packet.schema.json',
    WORKSPACE / 'schemas' / 'wake-decision.schema.json',
    WORKSPACE / 'schemas' / 'judgment-envelope.schema.json',
    WORKSPACE / 'schemas' / 'decision-log.schema.json',
    WORKSPACE / 'schemas' / 'source-registry-record.schema.json',
    WORKSPACE / 'schemas' / 'source-health.schema.json',
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def refresh_tradingagents_audits() -> None:
    """Refresh reviewer-visible TradingAgents lock/audit outputs when the source lock exists."""
    lock = FINANCE / 'ops' / 'tradingagents-upstream-lock.json'
    submodule = FINANCE / 'third_party' / 'tradingagents'
    if not lock.exists() or not submodule.exists():
        return
    tools = [
        FINANCE / 'tools' / 'check_tradingagents_upstream_lock.py',
        FINANCE / 'tools' / 'audit_tradingagents_upstream_authority.py',
    ]
    for tool in tools:
        proc = subprocess.run(
            ['python3', str(tool)],
            cwd=str(FINANCE),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f'{tool.name} failed during snapshot export: '
                f'{proc.stderr.strip() or proc.stdout.strip() or proc.returncode}'
            )


def finance_jobs() -> list[dict[str, Any]]:
    jobs = load_json(CRON_JOBS, {}).get('jobs', [])
    out = []
    for job in jobs if isinstance(jobs, list) else []:
        if not isinstance(job, dict) or job.get('name') not in FINANCE_JOB_NAMES:
            continue
        payload = job.get('payload') if isinstance(job.get('payload'), dict) else {}
        out.append({
            'id': job.get('id'),
            'name': job.get('name'),
            'enabled': job.get('enabled'),
            'schedule': job.get('schedule'),
            'sessionTarget': job.get('sessionTarget'),
            'wakeMode': job.get('wakeMode'),
            'delivery': job.get('delivery'),
            'payload': {
                'kind': payload.get('kind'),
                'model': payload.get('model'),
                'timeoutSeconds': payload.get('timeoutSeconds'),
                'lightContext': payload.get('lightContext'),
                'message': payload.get('message'),
            },
            'state': job.get('state'),
        })
    return sorted(out, key=lambda item: item.get('name') or '')


def finance_job_prompt_contract(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    contract = {
        'generated_at': now_iso(),
        'source': str(CRON_JOBS),
        'note': 'Prompt hashes let GitHub reviewers see live OpenClaw job prompt drift without exposing secrets.',
        'jobs': {},
    }
    for job in jobs:
        payload = job.get('payload') if isinstance(job.get('payload'), dict) else {}
        message = str(payload.get('message') or '')
        contract['jobs'][job.get('name')] = {
            'enabled': job.get('enabled'),
            'schedule': job.get('schedule'),
            'delivery': job.get('delivery'),
            'prompt_sha256': 'sha256:' + hashlib.sha256(message.encode('utf-8')).hexdigest(),
            'contains_deterministic_report_job': 'OpenClaw Finance Deterministic Report Job' in message,
            'runs_finance_discord_report_job': 'finance_discord_report_job.py' in message,
            'forbids_progress_text': 'Do not emit progress text' in message or 'Do not summarize' in message,
            'contains_context_pack': 'llm-job-context' in message,
            'contains_non_authority_boundary': (
                'pack_is_not_authority' in message
                or ('view cache' in message and 'canonical state' in message)
                or ('view cache' in message and 'canonical authority' in message)
            ),
            'contains_candidate_path': 'judgment-envelope-candidate.json' in message,
            'contains_unknown_discovery_contract': 'unknown_discovery_exhausted_reason' in message,
            'contains_threshold_mutation_ban': '禁止自动改 thresholds' in message,
            'message_preview': message[:260],
        }
    return contract


def finance_model_roles() -> dict[str, Any]:
    roles = load_json(MODEL_ROLES, {})
    assignments = roles.get('job_assignments', {}) if isinstance(roles.get('job_assignments'), dict) else {}
    role_defs = roles.get('roles', {}) if isinstance(roles.get('roles'), dict) else {}
    finance_assignments = {
        job: role
        for job, role in assignments.items()
        if str(job).startswith('finance-')
    }
    used_roles = sorted(set(finance_assignments.values()))
    return {
        'source': str(MODEL_ROLES),
        'job_assignments': finance_assignments,
        'roles': {role: role_defs.get(role) for role in used_roles},
    }


def finance_crontab_lines() -> list[str]:
    try:
        proc = subprocess.run(['crontab', '-l'], capture_output=True, text=True, timeout=10)
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    return [
        line
        for line in proc.stdout.splitlines()
        if 'finance' in line.lower() or 'portfolio_' in line or 'watchlist_sync.py' in line
    ]


def tail_jsonl(path: Path, limit: int = 5) -> tuple[int, list[dict[str, Any]]]:
    if not path.exists():
        return 0, []
    rows = []
    total = 0
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            total += 1
            rows.append(payload)
    return total, rows[-limit:]


def telemetry_summary() -> dict[str, Any]:
    files = {
        'dispatch_attribution': STATE / 'dispatch-attribution.jsonl',
        'thesis_outcomes': STATE / 'thesis-outcomes.jsonl',
        'report_usefulness_history': STATE / 'report-usefulness-history.jsonl',
    }
    summary: dict[str, Any] = {
        'generated_at': now_iso(),
        'state_boundary': 'sanitized_summary_only',
        'note': 'Full finance/state JSONL files remain local runtime state. This summary exposes counts and bounded latest rows for GitHub review.',
        'files': {},
    }
    for name, path in files.items():
        total, rows = tail_jsonl(path)
        sanitized_rows = []
        for row in rows:
            sanitized_rows.append({
                key: value for key, value in row.items()
                if key in {
                    'event_id',
                    'logged_at',
                    'wake_class',
                    'threshold_should_send',
                    'threshold_report_type',
                    'execution_decision',
                    'operator_action',
                    'thesis_id',
                    'instrument',
                    'thesis_status',
                    'product_validation_status',
                    'report_renderer',
                    'product_status',
                    'delivery_safety_status',
                    'usefulness_score',
                    'noise_tokens',
                    'delta_density',
                    'thesis_ref_count',
                    'opportunity_ref_count',
                    'invalidator_ref_count',
                }
            })
        summary['files'][name] = {
            'path': str(path),
            'exists': path.exists(),
            'row_count': total,
            'latest': sanitized_rows,
        }
    return summary


def runtime_control_state_snapshots() -> list[str]:
    snapshots = {
        'session-aperture-state.json': STATE / 'session-aperture-state.json',
        'brave-budget-state.json': STATE / 'brave-budget-state.json',
        'offhours-source-router-state.json': STATE / 'offhours-source-router-state.json',
        'brave-compression-activation-report.json': STATE / 'brave-compression-activation-report.json',
        'offhours-cadence-governor-state.json': STATE / 'offhours-cadence-governor-state.json',
        'marketday-core-review-policy.json': STATE / 'marketday-core-review-policy.json',
        'marketday-report-calendar-guard.json': STATE / 'marketday-report-calendar-guard.json',
        'exchange-calendar-provider-report.json': STATE / 'exchange-calendar-provider-report.json',
        'finance-delivery-observed-audit.json': STATE / 'finance-delivery-observed-audit.json',
        'brave-source-recovery-policy.json': STATE / 'brave-source-recovery-policy.json',
        'sec-fallback-activation-report.json': STATE / 'sec-fallback-activation-report.json',
    }
    copied: list[str] = []
    for target_name, source in snapshots.items():
        payload = load_json(source, None)
        write_json(OUT / target_name, {
            'generated_at': now_iso(),
            'state_boundary': 'sanitized_runtime_control_state',
            'review_source': REVIEW_2026_04_18,
            'source': str(source),
            'exists': source.exists(),
            'payload': payload if isinstance(payload, dict) else None,
        })
        copied.append(str((OUT / target_name).relative_to(FINANCE)))
    return copied


def copy_contracts() -> list[str]:
    CONTRACTS_OUT.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for path in CONTRACT_DOCS:
        if not path.exists():
            continue
        target = CONTRACTS_OUT / path.name
        shutil.copy2(path, target)
        copied.append(str(target.relative_to(FINANCE)))
    return copied


def copy_schemas() -> list[str]:
    schema_out = OUT / 'schemas'
    schema_out.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for path in SCHEMA_DOCS:
        if not path.exists():
            continue
        target = schema_out / path.name
        shutil.copy2(path, target)
        copied.append(str(target.relative_to(FINANCE)))
    return copied


def copy_parent_runtime_mirror() -> list[str]:
    mirror_out = OUT / 'parent-runtime'
    files = [
        WORKSPACE / 'services' / 'market-ingest' / 'adapters' / 'live_finance_adapter.py',
        WORKSPACE / 'services' / 'market-ingest' / 'source_health' / 'compiler.py',
        WORKSPACE / 'services' / 'market-ingest' / 'packet_compiler' / 'compiler.py',
        WORKSPACE / 'services' / 'market-ingest' / 'wake_policy' / 'policy.py',
    ]
    copied: list[str] = []
    for source in files:
        if not source.exists():
            continue
        rel = source.relative_to(WORKSPACE)
        target = mirror_out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(str(target.relative_to(FINANCE)))
    return copied


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    refresh_tradingagents_audits()
    contracts = copy_contracts()
    schemas = copy_schemas()
    parent_runtime = copy_parent_runtime_mirror()
    runtime_control_state = runtime_control_state_snapshots()
    jobs = finance_jobs()
    write_json(OUT / 'finance-cron-jobs.json', {
        'generated_at': now_iso(),
        'source': str(CRON_JOBS),
        'jobs': jobs,
    })
    write_json(OUT / 'finance-job-prompt-contract.json', finance_job_prompt_contract(jobs))
    write_json(OUT / 'thesis-spine-telemetry-summary.json', telemetry_summary())
    (OUT / 'finance-crontab.txt').write_text('\n'.join(finance_crontab_lines()) + '\n', encoding='utf-8')
    write_json(OUT / 'finance-model-roles.json', finance_model_roles())
    write_json(OUT / 'snapshot-manifest.json', {
        'generated_at': now_iso(),
        'subsystem': 'finance',
        'openclaw_home': str(OPENCLAW_HOME),
        'finance_repo': str(FINANCE),
        'snapshot_files': [
            'docs/openclaw-runtime/information-dominance-stack-plan.md',
            'docs/openclaw-runtime/information-dominance-stack-map.json',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-00-review2-intake-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-01-contracts-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-02-brave-api-audit-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-03-query-memory-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-04-brave-web-news-fetchers-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-05-brave-llm-context-reader-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-06-brave-answers-sidecar-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-07-query-planner-pack-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-08-finance-worker-reducer-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-09-source-health-quota-monitor-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-10-claim-aware-undercurrents-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-11-reader-bundle-followup-slices-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-12-parent-handoff-ralplan.md',
            'docs/openclaw-runtime/ralplan/ingestion-fabric-phase-13-closeout-ralplan.md',
            'docs/openclaw-runtime/ingestion-fabric-phase-ledger.json',
            'docs/openclaw-runtime/ingestion-fabric-closeout.json',
            'docs/openclaw-runtime/parent-ingestion-handoff.md',
            'docs/openclaw-runtime/parent-ingestion-handoff-contract.json',
            'docs/openclaw-runtime/brave-api-capability-audit.json',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-00-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-01-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-02-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-03-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-04-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-05-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-06-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-07-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-08-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-09-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-10-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-11-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-12-implementation-critic.md',
            'docs/openclaw-runtime/critics/ingestion-fabric-phase-13-implementation-critic.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-00-review-intake-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-01-source-office-scout-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-02-evidence-claim-canonicalization-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-03-options-iv-sensitivity-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-04-context-gap-first-class-unknowns-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-05-report-time-archive-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-06-undercurrent-engine-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-07-campaign-os-board-upgrade-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-08-verb-specific-followup-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-09-deep-dive-cache-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-10-thread-lifecycle-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-11-reviewer-exact-replay-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-12-source-roi-learning-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-13-active-cutover-gate-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-to-campaign-phase-14-monitoring-closeout-ralplan.md',
            'docs/openclaw-runtime/ralplan/source-freshness-hotfix-2026-04-17-ralplan.md',
            'docs/openclaw-runtime/ralplan/offhours-intelligence-p0-ralplan.md',
            'docs/openclaw-runtime/ralplan/offhours-intelligence-p1-ralplan.md',
            'docs/openclaw-runtime/ralplan/offhours-intelligence-p2-ralplan.md',
            'docs/openclaw-runtime/ralplan/offhours-intelligence-p3-ralplan.md',
            'docs/openclaw-runtime/ralplan/marketday-core-review-p4-ralplan.md',
            'docs/openclaw-runtime/ralplan/marketday-report-calendar-p5-ralplan.md',
            'docs/openclaw-runtime/ralplan/exchange-calendar-provider-p6-ralplan.md',
            'docs/openclaw-runtime/ralplan/delivery-observed-audit-p7-ralplan.md',
            'docs/openclaw-runtime/ralplan/watchdog-delivery-proof-hardening-p7-followup-ralplan.md',
            'docs/openclaw-runtime/ralplan/brave-source-recovery-p8-ralplan.md',
            'docs/openclaw-runtime/ralplan/sec-fallback-activation-p9-ralplan.md',
            'docs/openclaw-runtime/scouts/offhours-intelligence-p1-internal-explorer.md',
            'docs/openclaw-runtime/scouts/offhours-intelligence-p1-external-scout.md',
            'docs/openclaw-runtime/scouts/offhours-intelligence-p2-internal-explorer.md',
            'docs/openclaw-runtime/scouts/offhours-intelligence-p2-external-scout.md',
            'docs/openclaw-runtime/scouts/offhours-intelligence-p3-internal-explorer.md',
            'docs/openclaw-runtime/scouts/offhours-intelligence-p3-external-scout.md',
            'docs/openclaw-runtime/scouts/marketday-core-review-p4-internal-explorer.md',
            'docs/openclaw-runtime/scouts/marketday-core-review-p4-external-scout.md',
            'docs/openclaw-runtime/scouts/marketday-report-calendar-p5-internal-explorer.md',
            'docs/openclaw-runtime/scouts/marketday-report-calendar-p5-external-scout.md',
            'docs/openclaw-runtime/scouts/exchange-calendar-provider-p6-internal-explorer.md',
            'docs/openclaw-runtime/scouts/exchange-calendar-provider-p6-external-scout.md',
            'docs/openclaw-runtime/scouts/delivery-observed-audit-p7-internal-explorer.md',
            'docs/openclaw-runtime/scouts/delivery-observed-audit-p7-external-scout.md',
            'docs/openclaw-runtime/scouts/brave-source-recovery-p8-internal-explorer.md',
            'docs/openclaw-runtime/scouts/brave-source-recovery-p8-external-scout.md',
            'docs/openclaw-runtime/scouts/sec-fallback-activation-p9-internal-explorer.md',
            'docs/openclaw-runtime/scouts/sec-fallback-activation-p9-external-scout.md',
            'docs/openclaw-runtime/source-to-campaign-phase-ledger.json',
            'docs/openclaw-runtime/source-to-campaign-closeout.json',
            'docs/openclaw-runtime/source-scout-candidates.json',
            'docs/openclaw-runtime/finance-cron-jobs.json',
            'docs/openclaw-runtime/finance-crontab.txt',
            'docs/openclaw-runtime/finance-model-roles.json',
            'docs/openclaw-runtime/finance-job-prompt-contract.json',
            'ops/tradingagents-upstream-lock.json',
            'docs/openclaw-runtime/tradingagents-upstream-lock-check.json',
            'docs/openclaw-runtime/tradingagents-upstream-authority-audit.json',
            'docs/openclaw-runtime/contracts/tradingagents-bridge-contract.md',
            'docs/openclaw-runtime/examples/tradingagents-run-request.example.json',
            'docs/openclaw-runtime/examples/tradingagents-advisory-decision.example.json',
            'docs/openclaw-runtime/examples/tradingagents-validation.example.json',
            'docs/openclaw-runtime/examples/tradingagents-context-digest.example.json',
            'docs/openclaw-runtime/examples/tradingagents-reader-augmentation.example.json',
            'docs/openclaw-runtime/examples/tradingagents-bridge-record.example.json',
            'docs/openclaw-runtime/schemas/tradingagents-run-request.schema.json',
            'docs/openclaw-runtime/schemas/tradingagents-advisory-decision.schema.json',
            'docs/openclaw-runtime/schemas/tradingagents-validation.schema.json',
            'docs/openclaw-runtime/schemas/tradingagents-context-digest.schema.json',
            'docs/openclaw-runtime/schemas/tradingagents-reader-augmentation.schema.json',
            'docs/openclaw-runtime/schemas/tradingagents-bridge-record.schema.json',
            'docs/openclaw-runtime/operating-model-audit.json',
            'docs/openclaw-runtime/parent-dependency-inventory.json',
            'docs/openclaw-runtime/parent-dependency-drift.json',
            'docs/openclaw-runtime/parent-runtime/manifest.json',
            'docs/openclaw-runtime/parent-runtime/cron/finance-jobs-slice.json',
            'docs/openclaw-runtime/wake-threshold-attribution.json',
            'docs/openclaw-runtime/report-usefulness-score.json',
            'docs/openclaw-runtime/reviewer-packets/index.json',
            'docs/openclaw-runtime/reviewer-packets/README.md',
            'docs/openclaw-runtime/context-coverage-audit.json',
            'docs/openclaw-runtime/active-campaign-board-cutover.json',
            'docs/openclaw-runtime/thesis-spine-telemetry-summary.json',
            'docs/openclaw-runtime/session-aperture-state.json',
            'docs/openclaw-runtime/brave-budget-state.json',
            'docs/openclaw-runtime/offhours-source-router-state.json',
            'docs/openclaw-runtime/brave-compression-activation-report.json',
            'docs/openclaw-runtime/offhours-cadence-governor-state.json',
            'docs/openclaw-runtime/marketday-core-review-policy.json',
            'docs/openclaw-runtime/marketday-report-calendar-guard.json',
            'docs/openclaw-runtime/exchange-calendar-provider-report.json',
            'docs/openclaw-runtime/finance-delivery-observed-audit.json',
            'docs/openclaw-runtime/brave-source-recovery-policy.json',
            'docs/openclaw-runtime/sec-fallback-activation-report.json',
            'docs/openclaw-runtime/ibkr-watchlist-freshness-drill.json',
            'docs/openclaw-runtime/benchmark-boundary-audit.json',
            'docs/openclaw-runtime/runtime-gap-review.json',
            'docs/openclaw-runtime/contracts/campaign-projection-contract.md',
            'docs/openclaw-runtime/contracts/undercurrent-card-contract.md',
            'docs/openclaw-runtime/contracts/source-registry-v2-contract.md',
            'docs/openclaw-runtime/contracts/source-health-contract.md',
            'docs/openclaw-runtime/contracts/source-scout-contract.md',
            'docs/openclaw-runtime/contracts/options-iv-surface-contract.md',
            'docs/openclaw-runtime/contracts/report-time-archive-contract.md',
            'docs/openclaw-runtime/contracts/followup-context-slice-contract.md',
            'docs/openclaw-runtime/contracts/finance-thread-lifecycle-contract.md',
            'docs/openclaw-runtime/contracts/source-roi-contract.md',
            'docs/openclaw-runtime/contracts/source-to-campaign-cutover-gate-contract.md',
            'docs/openclaw-runtime/contracts/offhours-aperture-contract.md',
            'docs/openclaw-runtime/contracts/brave-budget-guard-contract.md',
            'docs/openclaw-runtime/contracts/query-pack-contract.md',
            'docs/openclaw-runtime/contracts/source-fetch-record-contract.md',
            'docs/openclaw-runtime/contracts/source-atom-contract.md',
            'docs/openclaw-runtime/contracts/claim-atom-contract.md',
            'docs/openclaw-runtime/contracts/context-gap-contract.md',
            'docs/openclaw-runtime/contracts/discord-campaign-board-package-contract.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-00-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-01-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-02-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-03-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-04-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-05-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-06-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-07-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-08-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-09-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-10-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-11-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-12-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-13-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-to-campaign-phase-14-implementation-critic.md',
            'docs/openclaw-runtime/critics/source-freshness-hotfix-2026-04-17-critic.md',
            'docs/openclaw-runtime/critics/offhours-intelligence-p0-implementation-critic.md',
            'docs/openclaw-runtime/critics/offhours-intelligence-p1-implementation-critic.md',
            'docs/openclaw-runtime/critics/offhours-intelligence-p2-implementation-critic.md',
            'docs/openclaw-runtime/critics/offhours-intelligence-p3-implementation-critic.md',
            'docs/openclaw-runtime/critics/marketday-core-review-p4-implementation-critic.md',
            'docs/openclaw-runtime/critics/marketday-report-calendar-p5-implementation-critic.md',
            'docs/openclaw-runtime/critics/exchange-calendar-provider-p6-implementation-critic.md',
            'docs/openclaw-runtime/critics/delivery-observed-audit-p7-implementation-critic.md',
            'docs/openclaw-runtime/critics/watchdog-delivery-proof-hardening-p7-followup-critic.md',
            'docs/openclaw-runtime/critics/brave-source-recovery-p8-implementation-critic.md',
            'docs/openclaw-runtime/critics/sec-fallback-activation-p9-implementation-critic.md',
            'docs/openclaw-runtime/cleanup/offhours-intelligence-p0-20260419.md',
            'docs/openclaw-runtime/cleanup/offhours-intelligence-p1-20260419.md',
            'docs/openclaw-runtime/cleanup/offhours-intelligence-p2-20260419.md',
            'docs/openclaw-runtime/cleanup/offhours-intelligence-p3-20260419.md',
            'docs/openclaw-runtime/cleanup/marketday-core-review-p4-20260419.md',
            'docs/openclaw-runtime/cleanup/marketday-report-calendar-p5-20260419.md',
            'docs/openclaw-runtime/cleanup/exchange-calendar-provider-p6-20260419.md',
            'docs/openclaw-runtime/cleanup/delivery-observed-audit-p7-20260419.md',
            'docs/openclaw-runtime/cleanup/brave-source-recovery-p8-20260419.md',
            'docs/openclaw-runtime/cleanup/sec-fallback-activation-p9-20260419.md',
            'docs/openclaw-runtime/critics/phase-2-implementation-critic.md',
            'docs/openclaw-runtime/critics/phase-3-implementation-critic.md',
            'docs/openclaw-runtime/critics/phase-4-implementation-critic.md',
            'docs/openclaw-runtime/critics/phase-5-implementation-critic.md',
            'docs/openclaw-runtime/critics/phase-6-implementation-critic.md',
            'docs/openclaw-runtime/critics/phase-7-implementation-critic.md',
            'docs/openclaw-runtime/critics/phase-8-implementation-critic.md',
            'docs/openclaw-runtime/critics/phase-9-implementation-critic.md',
            *contracts,
            *schemas,
            *parent_runtime,
            *runtime_control_state,
        ],
        'note': 'Generated from the local OpenClaw runtime. State files and secrets are intentionally excluded.',
    })
    (OUT / 'README.md').write_text(
        '# OpenClaw Runtime Snapshot\n\n'
        'This directory is generated by `tools/export_openclaw_runtime_snapshot.py`.\n\n'
        'It lets GitHub reviewers inspect the OpenClaw runtime surfaces that are outside the finance repository, including finance cron jobs, finance-related crontab lines, model-role mappings, and stable OpenClaw contract docs.\n\n'
        'Live `state/`, raw Flex XML, secrets, and account identifiers are intentionally excluded.\n',
        encoding='utf-8',
    )
    print(json.dumps({'status': 'pass', 'out': str(OUT), 'contracts': len(contracts)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
