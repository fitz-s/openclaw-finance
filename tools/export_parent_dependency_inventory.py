#!/usr/bin/env python3
"""Export hashes for parent OpenClaw market-ingest files used by finance."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


FINANCE = Path(__file__).resolve().parents[1]
OPENCLAW_HOME = FINANCE.parents[1]
WORKSPACE = OPENCLAW_HOME / 'workspace'
SERVICE = WORKSPACE / 'services' / 'market-ingest'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'parent-dependency-inventory.json'

DEPENDENCIES = {
    'decision_log_writer': WORKSPACE / 'decisions' / 'decision_log.py',
    'decision_log_schema': WORKSPACE / 'schemas' / 'decision-log.schema.json',
    'packet_schema': WORKSPACE / 'schemas' / 'packet.schema.json',
    'wake_decision_schema': WORKSPACE / 'schemas' / 'wake-decision.schema.json',
    'judgment_envelope_schema': WORKSPACE / 'schemas' / 'judgment-envelope.schema.json',
    'watch_intent_schema': WORKSPACE / 'schemas' / 'watch-intent.schema.json',
    'thesis_card_schema': WORKSPACE / 'schemas' / 'thesis-card.schema.json',
    'scenario_card_schema': WORKSPACE / 'schemas' / 'scenario-card.schema.json',
    'opportunity_queue_schema': WORKSPACE / 'schemas' / 'opportunity-queue.schema.json',
    'invalidator_ledger_schema': WORKSPACE / 'schemas' / 'invalidator-ledger.schema.json',
    'source_registry': SERVICE / 'config' / 'source-registry.json',
    'live_finance_adapter': SERVICE / 'adapters' / 'live_finance_adapter.py',
    'source_promotion': SERVICE / 'normalizer' / 'source_promotion.py',
    'semantic_normalizer': SERVICE / 'normalizer' / 'semantic_normalizer.py',
    'temporal_alignment': SERVICE / 'temporal_alignment' / 'alignment.py',
    'packet_compiler': SERVICE / 'packet_compiler' / 'compiler.py',
    'wake_policy': SERVICE / 'wake_policy' / 'policy.py',
    'judgment_validator': SERVICE / 'validator' / 'judgment_validator.py',
}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    files = []
    for role, path in DEPENDENCIES.items():
        files.append({
            'role': role,
            'path': str(path),
            'exists': path.exists(),
            'sha256': sha256(path),
        })
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pass' if all(item['exists'] for item in files) else 'degraded',
        'dependency_boundary': 'parent_openclaw_workspace',
        'finance_repo_policy': (
            'These files are load-bearing runtime dependencies but are not owned by the finance repository. '
            'Reviewers must inspect this inventory when packet/wake/judgment behavior changes.'
        ),
        'files': files,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'file_count': len(files), 'out': str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
