from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

import finance_worker
from claim_graph_compiler import compile_claim_graph
from context_gap_compiler import compile_context_gaps


def _claim_graph() -> dict:
    atom = {
        'atom_id': 'atom:phase08',
        'source_id': 'source:reuters',
        'source_lane': 'news_policy_narrative',
        'source_sublane': 'news_policy_narrative.entity_event',
        'symbol_candidates': ['TSLA'],
        'raw_snippet': 'TSLA delivery risk conflicts with current thesis',
        'raw_snippet_ref': 'finance-scan:obs:phase08',
        'point_in_time_hash': 'sha256:phase08',
        'reliability_score': 0.8,
        'uniqueness_score': 0.6,
        'compliance_class': 'public',
        'redistribution_policy': 'derived_only',
        'export_policy': 'derived_only',
        'raw_snippet_redaction_required': True,
        'candidate_type': 'invalidator_check',
        'no_execution': True,
    }
    return compile_claim_graph([atom], generated_at='2026-04-17T22:00:00Z')


def test_reduce_claims_to_legacy_observations_uses_claim_and_gap_metadata() -> None:
    graph = _claim_graph()
    gaps = compile_context_gaps(graph, generated_at='2026-04-17T22:00:00Z')
    rows = finance_worker.reduce_claims_to_legacy_observations(graph, gaps, generated_at='2026-04-17T22:00:00Z')
    assert rows
    row = rows[0]
    assert row['id'].startswith('claim-reducer:')
    assert row['candidate_type'] == 'claim_reducer_projection'
    assert row['legacy_bridge_only'] is True
    assert row['canonical_ingestion'] is False
    assert row['no_execution'] is True
    assert row['object_links']['claim_refs'] == [graph['claims'][0]['claim_id']]
    assert row['confirmation_needed']


def test_finance_worker_shadow_reducer_report_marks_legacy_bridge(tmp_path: Path, monkeypatch) -> None:
    atoms = tmp_path / 'latest.jsonl'
    claim_out = tmp_path / 'claim-graph.json'
    gaps_out = tmp_path / 'context-gaps.json'
    reducer_report = tmp_path / 'finance-worker-reducer-report.json'
    atom = {
        'atom_id': 'atom:phase08',
        'source_id': 'source:reuters',
        'source_lane': 'news_policy_narrative',
        'source_sublane': 'news_policy_narrative.entity_event',
        'symbol_candidates': ['TSLA'],
        'raw_snippet': 'TSLA delivery risk conflicts with current thesis',
        'raw_snippet_ref': 'finance-scan:obs:phase08',
        'point_in_time_hash': 'sha256:phase08',
        'reliability_score': 0.8,
        'uniqueness_score': 0.6,
        'compliance_class': 'public',
        'redistribution_policy': 'derived_only',
        'export_policy': 'derived_only',
        'raw_snippet_redaction_required': True,
        'candidate_type': 'invalidator_check',
        'no_execution': True,
    }
    atoms.write_text(json.dumps(atom) + '\n', encoding='utf-8')

    import claim_graph_compiler
    import context_gap_compiler
    import source_atom_compiler

    monkeypatch.setattr(source_atom_compiler, 'SOURCE_ATOMS_LATEST', atoms)
    monkeypatch.setattr(claim_graph_compiler, 'OUT', claim_out)
    monkeypatch.setattr(context_gap_compiler, 'OUT', gaps_out)
    monkeypatch.setattr(finance_worker, 'REDUCER_REPORT', reducer_report)

    report = finance_worker.write_shadow_claim_gap_reducer_report('2026-04-17T22:00:00Z')
    assert report is not None
    assert report['worker_role'] == 'compatibility_reducer'
    assert report['migration_mode'] == 'legacy_and_shadow'
    assert report['evaluation_mode'] == 'both'
    assert report['accumulated_authority'] == 'legacy_bridge_not_canonical_ingestion'
    assert report['idempotency_key'].startswith('sha256:')
    assert report['claim_count'] == 1
    assert report['gap_count'] >= 1
    assert report['reduced_legacy_observation_count'] == 1
    assert report['no_execution'] is True
    assert claim_out.exists()
    assert gaps_out.exists()
    persisted = json.loads(reducer_report.read_text(encoding='utf-8'))
    assert persisted['shadow_only'] is True


def test_finance_worker_parallel_claim_gap_write_is_best_effort(monkeypatch) -> None:
    import source_atom_compiler

    monkeypatch.setattr(source_atom_compiler, 'SOURCE_ATOMS_LATEST', Path('/definitely/missing/atoms.jsonl'))
    report = finance_worker.write_shadow_claim_gap_reducer_report('2026-04-17T22:00:00Z')
    assert report is not None
    assert report['source_atom_count'] == 0
    assert report['claim_count'] == 0
    assert report['gap_count'] == 0
