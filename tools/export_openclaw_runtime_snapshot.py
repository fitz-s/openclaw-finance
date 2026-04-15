#!/usr/bin/env python3
"""Export sanitized OpenClaw runtime context for GitHub reviewers."""
from __future__ import annotations

import json
import shutil
import subprocess
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

FINANCE_JOB_NAMES = {
    'finance-subagent-scanner',
    'finance-subagent-scanner-offhours',
    'finance-premarket-brief',
    'finance-weekly-learning-review',
    'finance-report-renderer',
    'finance-watcher-update',
}

CONTRACT_DOCS = [
    WORKSPACE / 'systems' / 'finance-openclaw-runtime-contract.md',
    WORKSPACE / 'systems' / 'finance-report-contract.md',
    WORKSPACE / 'systems' / 'finance-gate-taxonomy.md',
    WORKSPACE / 'systems' / 'judgment-contract.md',
    WORKSPACE / 'systems' / 'wake-policy.md',
    WORKSPACE / 'systems' / 'risk-gates.md',
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


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    contracts = copy_contracts()
    write_json(OUT / 'finance-cron-jobs.json', {
        'generated_at': now_iso(),
        'source': str(CRON_JOBS),
        'jobs': finance_jobs(),
    })
    (OUT / 'finance-crontab.txt').write_text('\n'.join(finance_crontab_lines()) + '\n', encoding='utf-8')
    write_json(OUT / 'finance-model-roles.json', finance_model_roles())
    write_json(OUT / 'snapshot-manifest.json', {
        'generated_at': now_iso(),
        'subsystem': 'finance',
        'openclaw_home': str(OPENCLAW_HOME),
        'finance_repo': str(FINANCE),
        'snapshot_files': [
            'docs/openclaw-runtime/finance-cron-jobs.json',
            'docs/openclaw-runtime/finance-crontab.txt',
            'docs/openclaw-runtime/finance-model-roles.json',
            'docs/openclaw-runtime/operating-model-audit.json',
            'docs/openclaw-runtime/parent-dependency-inventory.json',
            'docs/openclaw-runtime/runtime-gap-review.json',
            *contracts,
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
