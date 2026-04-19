from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from source_atom_compiler import MAX_SNIPPET_CHARS, atom_from_observation, compile_atoms, load_source_registry


def _scan_state() -> dict:
    return {
        'last_updated': '2026-04-16T15:00:00Z',
        'accumulated': [
            {
                'id': 'obs:tsla-risk',
                'ts': '2026-04-16T14:59:00Z',
                'theme': 'TSLA delivery risk conflicts with current thesis',
                'summary': 'Reuters says TSLA delivery risk is increasing while price action remains mixed.',
                'sources': ['Reuters'],
                'tickers': ['TSLA'],
                'candidate_type': 'invalidator_check',
            },
            {
                'id': 'obs:long',
                'ts': '2026-04-16T14:58:00Z',
                'theme': 'Unknown discovery narrative',
                'summary': 'x' * 500,
                'sources': ['Random Blog'],
            },
        ],
    }


def test_source_atom_compiler_writes_deterministic_atoms() -> None:
    registry = load_source_registry()
    first = compile_atoms(_scan_state(), registry=registry, generated_at='2026-04-16T15:01:00Z')
    second = compile_atoms(_scan_state(), registry=registry, generated_at='2026-04-16T15:01:00Z')

    assert first['atom_count'] == 2
    assert first['atom_hash'] == second['atom_hash']
    assert [row['atom_id'] for row in first['atoms']] == [row['atom_id'] for row in second['atoms']]
    assert all(row['no_execution'] is True for row in first['atoms'])
    assert first['shadow_only'] is True


def test_source_atom_preserves_raw_ref_and_point_in_time_hash() -> None:
    atom = atom_from_observation(_scan_state()['accumulated'][0], registry=load_source_registry(), scan_file='state:test.json')

    assert atom['raw_ref'] == 'finance-scan:obs:tsla-risk'
    assert atom['point_in_time_hash'].startswith('sha256:')
    assert atom['source_id'] == 'source:reuters'
    assert atom['symbol_candidates'] == ['TSLA']
    assert 'state:test.json' in atom['lineage_chain']


def test_source_atom_bounds_raw_snippet() -> None:
    atom = atom_from_observation(_scan_state()['accumulated'][1], registry=load_source_registry())
    assert len(atom['raw_snippet']) <= MAX_SNIPPET_CHARS
    assert atom['redistribution_policy'] == 'unknown'
    assert atom['raw_snippet_ref'] == atom['raw_ref']
    assert atom['safe_excerpt'] is None
    assert atom['raw_snippet_redaction_required'] is True
    assert atom['export_policy'] == 'metadata_only'
    assert atom['lane'] == atom['source_lane']
    assert atom['source_sublane']


def test_source_atom_does_not_mutate_accumulated_observations() -> None:
    scan = _scan_state()
    before = copy.deepcopy(scan)
    compile_atoms(scan, registry=load_source_registry(), generated_at='2026-04-16T15:01:00Z')
    assert scan == before


def test_source_atom_cli_rejects_unsafe_output(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / 'source_atom_compiler.py'), '--out', str(tmp_path / 'atoms.jsonl')],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert 'unsafe_out_path' in result.stdout
