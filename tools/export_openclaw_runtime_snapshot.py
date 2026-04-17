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

FINANCE_JOB_NAMES = {
    'finance-subagent-scanner',
    'finance-subagent-scanner-offhours',
    'finance-premarket-brief',
    'finance-premarket-delivery-watchdog',
    'finance-midday-operator-review',
    'finance-weekly-learning-review',
    'finance-thesis-sidecar',
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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    contracts = copy_contracts()
    schemas = copy_schemas()
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
            'docs/openclaw-runtime/ingestion-fabric-phase-ledger.json',
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
            'docs/openclaw-runtime/source-to-campaign-phase-ledger.json',
            'docs/openclaw-runtime/source-to-campaign-closeout.json',
            'docs/openclaw-runtime/source-scout-candidates.json',
            'docs/openclaw-runtime/finance-cron-jobs.json',
            'docs/openclaw-runtime/finance-crontab.txt',
            'docs/openclaw-runtime/finance-model-roles.json',
            'docs/openclaw-runtime/finance-job-prompt-contract.json',
            'docs/openclaw-runtime/operating-model-audit.json',
            'docs/openclaw-runtime/parent-dependency-inventory.json',
            'docs/openclaw-runtime/parent-dependency-drift.json',
            'docs/openclaw-runtime/wake-threshold-attribution.json',
            'docs/openclaw-runtime/report-usefulness-score.json',
            'docs/openclaw-runtime/reviewer-packets/index.json',
            'docs/openclaw-runtime/reviewer-packets/README.md',
            'docs/openclaw-runtime/context-coverage-audit.json',
            'docs/openclaw-runtime/active-campaign-board-cutover.json',
            'docs/openclaw-runtime/thesis-spine-telemetry-summary.json',
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
