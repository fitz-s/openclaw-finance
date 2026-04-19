from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
MANIFEST = ROOT / 'docs' / 'openclaw-runtime' / 'snapshot-manifest.json'


def test_snapshot_manifest_entries_exist() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    missing = [path for path in manifest['snapshot_files'] if not (ROOT / path).exists()]
    assert missing == []
