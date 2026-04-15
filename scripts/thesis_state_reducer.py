#!/usr/bin/env python3
"""Run the first Thesis Spine reducers in deterministic order."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
STEPS = [
    'watch_intent_compiler.py',
    'thesis_registry_compiler.py',
    'opportunity_queue_builder.py',
    'invalidator_ledger_compiler.py',
]


def main() -> int:
    results = []
    ok = True
    for script in STEPS:
        proc = subprocess.run([sys.executable, str(SCRIPTS / script)], capture_output=True, text=True, timeout=60)
        try:
            payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
        except Exception:
            payload = {'stdout_preview': proc.stdout.strip()[:500]}
        payload['returncode'] = proc.returncode
        payload['script'] = script
        if proc.stderr.strip():
            payload['stderr_preview'] = proc.stderr.strip()[:500]
        results.append(payload)
        if proc.returncode != 0:
            ok = False
            break
    print(json.dumps({'status': 'pass' if ok else 'fail', 'steps': results}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())

