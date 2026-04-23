from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
FIXTURES = ROOT / 'tests' / 'fixtures' / 'tradingagents'
sys.path.insert(0, str(SCRIPTS))

from tradingagents_advisory_translate import translate_run


def test_translate_run_builds_normalized_artifacts(tmp_path: Path) -> None:
    run_root = tmp_path / 'run'
    raw_dir = run_root / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FIXTURES / 'final_state.json', raw_dir / 'redacted-final-state.json')
    artifact = json.loads((FIXTURES / 'raw_run_artifact.json').read_text(encoding='utf-8'))
    artifact['final_state_path'] = str(raw_dir / 'redacted-final-state.json')
    (raw_dir / 'run-artifact.json').write_text(json.dumps(artifact), encoding='utf-8')

    result = translate_run(run_root)

    assert result['status'] == 'pass'
    advisory = json.loads((run_root / 'normalized' / 'advisory-decision.json').read_text(encoding='utf-8'))
    assert advisory['instrument'] == 'NVDA'
    assert advisory['hypothetical_rating'] == 'OVERWEIGHT'
    assert advisory['execution_readiness'] == 'disabled'
    assert advisory['review_only'] is True
    assert advisory['no_execution'] is True
    assert all('buy' not in str(item).lower() for item in advisory['why_now_safe'])
    assert all('overweight' not in str(item).lower() for item in advisory['why_not_now_safe'])
