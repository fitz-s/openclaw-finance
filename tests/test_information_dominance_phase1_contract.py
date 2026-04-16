from __future__ import annotations

import json
from pathlib import Path


ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
CONTRACTS = ROOT / 'docs' / 'openclaw-runtime' / 'contracts'
INVENTORY = ROOT / 'docs' / 'openclaw-runtime' / 'parent-dependency-inventory.json'
MANIFEST = ROOT / 'docs' / 'openclaw-runtime' / 'snapshot-manifest.json'
SCHEMA_SNAPSHOT = ROOT / 'docs' / 'openclaw-runtime' / 'schemas'


def test_phase1_contracts_exist_and_preserve_shadow_boundary() -> None:
    registry = (CONTRACTS / 'source-registry-v2-contract.md').read_text(encoding='utf-8')
    health = (CONTRACTS / 'source-health-contract.md').read_text(encoding='utf-8')

    assert 'Source Registry 2.0' in registry
    assert 'Phase 1 Shadow Rule' in registry
    assert 'must not change' in registry
    assert 'Source Health is a shadow audit surface' in health
    assert 'Hard-gating wake' in health
    assert 'no_execution' in health


def test_parent_dependency_inventory_tracks_phase1_parent_files() -> None:
    payload = json.loads(INVENTORY.read_text(encoding='utf-8'))
    roles = {item['role'] for item in payload['files']}

    assert 'source_registry_schema' in roles
    assert 'source_health_schema' in roles
    assert 'source_health_compiler' in roles


def test_snapshot_manifest_exposes_phase1_contracts_and_schema_snapshots() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    files = set(manifest['snapshot_files'])

    assert 'docs/openclaw-runtime/contracts/source-registry-v2-contract.md' in files
    assert 'docs/openclaw-runtime/contracts/source-health-contract.md' in files
    assert 'docs/openclaw-runtime/schemas/source-registry-record.schema.json' in files
    assert 'docs/openclaw-runtime/schemas/source-health.schema.json' in files
    assert (SCHEMA_SNAPSHOT / 'source-registry-record.schema.json').exists()
    assert (SCHEMA_SNAPSHOT / 'source-health.schema.json').exists()
