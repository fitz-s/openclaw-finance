#!/usr/bin/env python3
"""Compare current parent dependency inventory to the committed Git baseline."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FINANCE = Path(__file__).resolve().parents[1]
INVENTORY = FINANCE / 'docs' / 'openclaw-runtime' / 'parent-dependency-inventory.json'
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'parent-dependency-drift.json'


def load_json_text(text: str, default: Any = None) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return default


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default


def baseline_inventory() -> dict[str, Any] | None:
    proc = subprocess.run(
        ['git', 'show', f'HEAD:{INVENTORY.relative_to(FINANCE)}'],
        cwd=str(FINANCE),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if proc.returncode != 0:
        return None
    payload = load_json_text(proc.stdout)
    return payload if isinstance(payload, dict) else None


def file_map(payload: dict[str, Any]) -> dict[str, str | None]:
    return {
        str(item.get('role')): item.get('sha256')
        for item in payload.get('files', [])
        if isinstance(item, dict)
    }


def main() -> int:
    current = load_json(INVENTORY, {}) or {}
    baseline = baseline_inventory()
    current_map = file_map(current)
    baseline_map = file_map(baseline or {})
    changed = []
    missing_baseline = baseline is None
    if baseline is not None:
        roles = sorted(set(current_map) | set(baseline_map))
        changed = [
            {'role': role, 'baseline_sha256': baseline_map.get(role), 'current_sha256': current_map.get(role)}
            for role in roles
            if current_map.get(role) != baseline_map.get(role)
        ]
    report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'status': 'baseline_missing' if missing_baseline else 'drift_detected' if changed else 'pass',
        'changed_count': len(changed),
        'changed': changed,
        'note': 'Drift is informational for reviewer visibility; commit the refreshed snapshot after intentional parent dependency changes.',
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'status': report['status'], 'changed_count': report['changed_count'], 'out': str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
