from __future__ import annotations

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / 'docs' / 'openclaw-runtime' / 'parent-ingestion-handoff.md'
CONTRACT = ROOT / 'docs' / 'openclaw-runtime' / 'parent-ingestion-handoff-contract.json'


def test_parent_handoff_maps_required_parent_components() -> None:
    text = HANDOFF.read_text(encoding='utf-8')
    required = [
        'source registry',
        'source promotion',
        'semantic normalizer',
        'temporal alignment',
        'packet compiler',
        'wake policy',
        'judgment validator',
    ]
    for item in required:
        assert item in text


def test_parent_handoff_blocks_unapproved_parent_mutation() -> None:
    text = HANDOFF.read_text(encoding='utf-8')
    assert 'does not authorize direct parent mutation' in text
    assert 'Default must be off' in text
    assert 'restart OpenClaw runtime' in text


def test_parent_handoff_has_rollbacks_and_followup_slice_requirement() -> None:
    text = HANDOFF.read_text(encoding='utf-8')
    assert 'Disable all flags' in text
    assert 'never route-card-only' in text
    assert 'followup_slice_index' in text
    assert 'raw thread history' in text


def test_parent_handoff_machine_contract_is_flagged_and_non_authoritative() -> None:
    payload = json.loads(CONTRACT.read_text(encoding='utf-8'))
    assert payload['contract'] == 'parent-ingestion-handoff-v1'
    assert payload['status'] == 'proposal_only_no_parent_mutation'
    assert payload['authority_boundary']['promotion_requires_explicit_parent_approval'] is True
    assert 'services/market-ingest/packet_compiler/compiler.py' in payload['parent_consumers']
    assert 'state/report-reader/latest.json' in payload['producer_artifacts']
    assert payload['rollback']['discord_fallback'] == 'complete_readable_primary_report_never_route_card_only'
    assert payload['no_execution'] is True
