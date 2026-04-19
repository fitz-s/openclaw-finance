from __future__ import annotations

from pathlib import Path


ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
CONTRACTS = ROOT / 'docs' / 'openclaw-runtime' / 'contracts'


def test_phase2_contracts_exist_and_preserve_shadow_boundary() -> None:
    source_atom = (CONTRACTS / 'source-atom-contract.md').read_text(encoding='utf-8')
    claim_atom = (CONTRACTS / 'claim-atom-contract.md').read_text(encoding='utf-8')
    context_gap = (CONTRACTS / 'context-gap-contract.md').read_text(encoding='utf-8')

    assert 'shadow substrate' in source_atom
    assert 'must not become an artifact dump' in source_atom
    assert 'raw_snippet_ref' in source_atom
    assert 'safe_excerpt' in source_atom
    assert 'raw_snippet_redaction_required' in source_atom
    assert 'not by LLM free prose' in claim_atom
    assert 'evidence_rights' in claim_atom
    assert 'source_sublane' in claim_atom
    assert 'Gaps do not block delivery in Phase 2' in context_gap
    assert 'gap_status' in context_gap
    assert 'closure_condition' in context_gap
    assert 'weak_claim_ids' in context_gap
    assert 'no_execution' in source_atom + claim_atom + context_gap


def test_phase2_artifacts_are_shadow_only_by_contract() -> None:
    combined = '\n'.join((CONTRACTS / name).read_text(encoding='utf-8') for name in [
        'source-atom-contract.md',
        'claim-atom-contract.md',
        'context-gap-contract.md',
    ])
    assert 'wake' in combined
    assert 'JudgmentEnvelope' in combined or 'judgment' in combined
    assert 'execution' in combined
    assert 'Discord primary' in combined or 'delivery' in combined
