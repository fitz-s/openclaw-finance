#!/usr/bin/env python3
"""Audit that benchmark absorption remains bounded to OpenClaw-compatible patterns."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


FINANCE = Path(__file__).resolve().parents[1]
PLAN = FINANCE / 'docs' / 'benchmark-absorption-plan.md'
MODEL = FINANCE / 'docs' / 'operating-model.md'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'benchmark-boundary-audit.json'

REQUIRED = [
    'OpenClaw-embedded',
    'review-only',
    'Absorbable Patterns',
    'Rejected Whole-Product Imports',
    'direct execution / buy buttons',
    'model swarm on report hot path',
]


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8') if path.exists() else ''


def main() -> int:
    text = read(PLAN) + '\n' + read(MODEL)
    checks = {f'contains:{token}': token in text for token in REQUIRED}
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'pass' if all(checks.values()) else 'fail',
        'checks': checks,
        'blocking_reasons': [key for key, ok in checks.items() if not ok],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'blocking_reasons': report['blocking_reasons'], 'out': str(OUT)}, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
