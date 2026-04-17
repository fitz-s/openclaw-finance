from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from claim_graph_compiler import claim_from_atom, event_class_for


def _atom() -> dict:
    return {
        'atom_id': 'atom:abc',
        'source_id': 'source:test_options',
        'source_lane': 'market_structure',
        'lane': 'market_structure',
        'source_sublane': 'market_structure.options_iv',
        'symbol_candidates': ['RGTI'],
        'raw_snippet': 'RGTI option IV spike with elevated volume/OI ratio',
        'safe_excerpt': None,
        'raw_snippet_ref': 'finance-scan:obs:rgti-iv',
        'point_in_time_hash': 'sha256:abc',
        'reliability_score': 0.55,
        'uniqueness_score': 0.65,
        'compliance_class': 'licensed_restricted',
        'redistribution_policy': 'derived_only',
        'export_policy': 'derived_only',
        'raw_snippet_redaction_required': True,
        'candidate_type': 'unknown_discovery',
        'no_execution': True,
    }


def test_claim_atom_preserves_source_metadata_for_lineage() -> None:
    claim = claim_from_atom(_atom())
    assert claim['atom_id'] == 'atom:abc'
    assert claim['source_id'] == 'source:test_options'
    assert claim['source_lane'] == 'market_structure'
    assert claim['source_sublane'] == 'market_structure.options_iv'
    assert claim['source_reliability_score'] == 0.55
    assert claim['source_uniqueness_score'] == 0.65
    assert claim['evidence_rights']['export_policy'] == 'derived_only'
    assert claim['evidence_rights']['raw_snippet_redaction_required'] is True
    assert claim['lineage']['point_in_time_hash'] == 'sha256:abc'
    assert claim['lineage']['raw_snippet_ref'] == 'finance-scan:obs:rgti-iv'
    assert claim['no_execution'] is True


def test_options_iv_sublane_classifies_as_flow_claim() -> None:
    assert event_class_for(_atom()) == 'flow'
    claim = claim_from_atom(_atom())
    assert claim['predicate'] == 'shows_flow'
    assert 'flow' in claim['why_it_matters_tags']
