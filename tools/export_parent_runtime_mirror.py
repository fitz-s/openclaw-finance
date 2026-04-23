#!/usr/bin/env python3
"""Mirror parent runtime files touched by finance cutover for reviewers."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FINANCE = Path(__file__).resolve().parents[1]
OPENCLAW_HOME = FINANCE.parents[1]
WORKSPACE = OPENCLAW_HOME / 'workspace'
SERVICE = WORKSPACE / 'services' / 'market-ingest'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'parent-runtime'
CRON = OPENCLAW_HOME / 'cron' / 'jobs.json'

MIRROR_FILES = {
    'services/market-ingest/adapters/live_finance_adapter.py': SERVICE / 'adapters' / 'live_finance_adapter.py',
    'services/market-ingest/normalizer/source_promotion.py': SERVICE / 'normalizer' / 'source_promotion.py',
    'services/market-ingest/normalizer/semantic_normalizer.py': SERVICE / 'normalizer' / 'semantic_normalizer.py',
    'services/market-ingest/source_health/compiler.py': SERVICE / 'source_health' / 'compiler.py',
    'services/market-ingest/packet_compiler/compiler.py': SERVICE / 'packet_compiler' / 'compiler.py',
    'services/market-ingest/wake_policy/policy.py': SERVICE / 'wake_policy' / 'policy.py',
    'systems/tradingagents-bridge-contract.md': WORKSPACE / 'systems' / 'tradingagents-bridge-contract.md',
    'skills/finance-tradingagents-sidecar/SKILL.md': WORKSPACE / 'skills' / 'finance-tradingagents-sidecar' / 'SKILL.md',
    'skills/finance-tradingagents-sidecar/_meta.json': WORKSPACE / 'skills' / 'finance-tradingagents-sidecar' / '_meta.json',
}
FINANCE_JOB_NAMES = {
    'finance-premarket-brief',
    'finance-subagent-scanner',
    'finance-subagent-scanner-offhours',
    'finance-premarket-delivery-watchdog',
    'finance-midday-operator-review',
    'finance-tradingagents-sidecar',
}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def mirror_file(rel: str, source: Path) -> dict[str, Any]:
    target = OUT / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        shutil.copy2(source, target)
    return {
        'role': rel,
        'source_path': str(source),
        'mirror_path': str(target.relative_to(FINANCE)),
        'exists': source.exists(),
        'sha256': sha256(source),
    }


def finance_cron_slice() -> dict[str, Any]:
    payload = load_json(CRON, {}) or {}
    jobs = []
    for job in payload.get('jobs', []) if isinstance(payload.get('jobs'), list) else []:
        if not isinstance(job, dict) or job.get('name') not in FINANCE_JOB_NAMES:
            continue
        jobs.append({
            'id': job.get('id'),
            'name': job.get('name'),
            'enabled': job.get('enabled'),
            'schedule': job.get('schedule'),
            'delivery': job.get('delivery'),
            'sessionTarget': job.get('sessionTarget'),
            'payload': {
                'kind': (job.get('payload') or {}).get('kind') if isinstance(job.get('payload'), dict) else None,
                'model': (job.get('payload') or {}).get('model') if isinstance(job.get('payload'), dict) else None,
                'message': (job.get('payload') or {}).get('message') if isinstance(job.get('payload'), dict) else None,
            },
        })
    return {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'source_path': str(CRON),
        'jobs': sorted(jobs, key=lambda item: item.get('name') or ''),
        'no_execution': True,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    files = [mirror_file(rel, source) for rel, source in MIRROR_FILES.items()]
    cron_slice = finance_cron_slice()
    cron_path = OUT / 'cron' / 'finance-jobs-slice.json'
    cron_path.parent.mkdir(parents=True, exist_ok=True)
    cron_path.write_text(json.dumps(cron_slice, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    manifest = {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'contract': 'parent-runtime-mirror-v1',
        'status': 'pass' if all(item['exists'] for item in files) else 'degraded',
        'purpose': 'Reviewer-visible mirror of parent runtime files relevant to finance cutover.',
        'files': files,
        'cron_slice': str(cron_path.relative_to(FINANCE)),
        'no_execution': True,
    }
    manifest_path = OUT / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': manifest['status'], 'file_count': len(files), 'out': str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
