from __future__ import annotations

import json
import sys
from pathlib import Path


SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from judgment_envelope_gate import gate_candidate


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')


def packet() -> dict:
    return {
        'packet_id': 'packet:test',
        'packet_hash': 'sha256:' + 'a' * 64,
        'instrument': 'SPY',
        'position_state': {'authority': 'review-only'},
        'market_state': {},
        'policy_version': 'finance-semantic-v1',
        'evidence_refs': ['ev:allowed', 'ev:blocked'],
        'accepted_evidence_records': [
            {'evidence_id': 'ev:allowed', 'quarantine': {'allowed_for_judgment_support': True, 'allowed_for_wake': True}},
            {'evidence_id': 'ev:blocked', 'quarantine': {'allowed_for_judgment_support': False, 'allowed_for_wake': False}},
        ],
    }


def candidate(ref: str) -> dict:
    return {
        'judgment_id': f'judgment:{ref}',
        'packet_id': 'packet:test',
        'packet_hash': 'sha256:' + 'a' * 64,
        'instrument': 'SPY',
        'thesis_state': 'no_trade',
        'actionability': 'none',
        'confidence': 0.0,
        'why_now': ['context updated'],
        'why_not': ['review-only'],
        'invalidators': ['packet staleness'],
        'required_confirmations': ['operator review'],
        'evidence_refs': [ref],
        'policy_version': 'finance-semantic-v1',
        'model_id': 'test',
    }


def test_judgment_gate_rejects_candidate_ref_not_exposed_in_context_pack(tmp_path: Path) -> None:
    packet_path = tmp_path / 'packet.json'
    candidate_path = tmp_path / 'candidate.json'
    selected_path = Path('/Users/leofitz/.openclaw/workspace/finance/state/test-context-gate-selected.json')
    validation_path = Path('/Users/leofitz/.openclaw/workspace/finance/state/test-context-gate-validation.json')
    context_pack_path = tmp_path / 'report-orchestrator.json'
    write_json(packet_path, packet())
    write_json(candidate_path, candidate('ev:blocked'))
    write_json(context_pack_path, {
        'pack_is_not_authority': True,
        'allowed_evidence_refs': [{'evidence_id': 'ev:allowed'}],
    })

    report = gate_candidate(
        packet_path=packet_path,
        candidate_path=candidate_path,
        selected_path=selected_path,
        validation_path=validation_path,
        context_pack_path=context_pack_path,
        adjudication_mode='scheduled_context',
    )

    assert report['status'] == 'blocked'
    assert 'evidence_ref_not_in_llm_context_pack' in report['blocking_reasons']
    validation = json.loads(validation_path.read_text())
    assert validation['outcome'] == 'rejected_missing_refs'


def test_judgment_gate_accepts_candidate_ref_exposed_in_context_pack(tmp_path: Path) -> None:
    packet_path = tmp_path / 'packet.json'
    candidate_path = tmp_path / 'candidate.json'
    selected_path = Path('/Users/leofitz/.openclaw/workspace/finance/state/test-context-gate-selected-ok.json')
    validation_path = Path('/Users/leofitz/.openclaw/workspace/finance/state/test-context-gate-validation-ok.json')
    context_pack_path = tmp_path / 'report-orchestrator.json'
    write_json(packet_path, packet())
    write_json(candidate_path, candidate('ev:allowed'))
    write_json(context_pack_path, {
        'pack_is_not_authority': True,
        'allowed_evidence_refs': [{'evidence_id': 'ev:allowed'}],
    })

    report = gate_candidate(
        packet_path=packet_path,
        candidate_path=candidate_path,
        selected_path=selected_path,
        validation_path=validation_path,
        context_pack_path=context_pack_path,
        adjudication_mode='scheduled_context',
    )

    assert report['status'] == 'pass'
    assert report['selected_source'] == 'candidate'
