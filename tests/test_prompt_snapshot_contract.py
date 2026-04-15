from __future__ import annotations

import json
from pathlib import Path


SNAPSHOT = Path('/Users/leofitz/.openclaw/workspace/finance/docs/openclaw-runtime/finance-job-prompt-contract.json')


def test_exported_prompt_snapshot_enforces_context_pack_contract() -> None:
    payload = json.loads(SNAPSHOT.read_text())
    jobs = payload['jobs']

    assert jobs['finance-premarket-brief']['contains_context_pack'] is True
    assert jobs['finance-premarket-brief']['contains_non_authority_boundary'] is True
    assert jobs['finance-premarket-brief']['contains_candidate_path'] is True
    assert jobs['finance-subagent-scanner']['contains_unknown_discovery_contract'] is True
    assert jobs['finance-subagent-scanner']['contains_non_authority_boundary'] is True
    assert jobs['finance-subagent-scanner-offhours']['contains_unknown_discovery_contract'] is True
    assert jobs['finance-subagent-scanner-offhours']['contains_non_authority_boundary'] is True
    assert jobs['finance-weekly-learning-review']['contains_threshold_mutation_ban'] is True
    assert jobs['finance-weekly-learning-review']['contains_non_authority_boundary'] is True
    assert jobs['finance-thesis-sidecar']['enabled'] is False
    assert jobs['finance-thesis-sidecar']['contains_non_authority_boundary'] is True
    assert jobs['finance-thesis-sidecar']['delivery']['mode'] == 'none'
