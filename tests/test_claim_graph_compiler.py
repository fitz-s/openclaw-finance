from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from claim_graph_compiler import compile_claim_graph


def _atoms() -> list[dict]:
    return [
        {
            'atom_id': 'atom:a',
            'source_id': 'source:reuters',
            'source_lane': 'news_policy_narrative',
            'raw_snippet': 'TSLA risk down after delivery delay conflict',
            'symbol_candidates': ['TSLA'],
            'compliance_class': 'licensed',
            'candidate_type': 'invalidator_check',
        },
        {
            'atom_id': 'atom:b',
            'source_id': 'source:sec_edgar',
            'source_lane': 'corporate_filing',
            'raw_snippet': 'TSLA filed 8-K confirmed update',
            'symbol_candidates': ['TSLA'],
            'compliance_class': 'public',
        },
        {
            'atom_id': 'atom:c',
            'source_id': 'source:yfinance',
            'source_lane': 'market_structure',
            'raw_snippet': 'TSLA quote up 2 percent',
            'symbol_candidates': ['TSLA'],
            'compliance_class': 'public',
        },
    ]


def test_claim_graph_derives_claims_from_atoms_without_llm() -> None:
    graph = compile_claim_graph(_atoms(), generated_at='2026-04-16T15:10:00Z')
    assert graph['claim_count'] == 3
    assert graph['shadow_only'] is True
    assert graph['no_execution'] is True
    assert {claim['event_class'] for claim in graph['claims']} >= {'narrative', 'filing', 'price'}
    assert all(claim['claim_id'].startswith('claim:') for claim in graph['claims'])


def test_claim_graph_hash_is_deterministic() -> None:
    first = compile_claim_graph(_atoms(), generated_at='2026-04-16T15:10:00Z')
    second = compile_claim_graph(list(reversed(_atoms())), generated_at='2026-04-16T15:11:00Z')
    assert first['graph_hash'] == second['graph_hash']


def test_claim_graph_marks_contradictions_by_subject() -> None:
    graph = compile_claim_graph(_atoms(), generated_at='2026-04-16T15:10:00Z')
    tsla = [claim for claim in graph['claims'] if claim['subject'] == 'TSLA']
    assert any(claim['contradicts'] for claim in tsla)
