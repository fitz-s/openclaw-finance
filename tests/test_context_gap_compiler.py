from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from context_gap_compiler import compile_context_gaps


def _claim_graph() -> dict:
    return {
        'graph_hash': 'sha256:test',
        'claims': [
            {
                'claim_id': 'claim:narrative',
                'subject': 'TSLA',
                'predicate': 'mentions',
                'event_class': 'narrative',
                'source_lane': 'news_policy_narrative',
                'certainty': 'weak',
            },
            {
                'claim_id': 'claim:filed',
                'subject': 'TSLA',
                'predicate': 'files',
                'event_class': 'filing',
                'source_lane': 'corporate_filing',
                'certainty': 'confirmed',
            },
        ],
    }


def test_context_gap_marks_missing_market_structure_for_narrative_only_claim() -> None:
    report = compile_context_gaps(_claim_graph(), generated_at='2026-04-16T15:20:00Z')
    assert report['shadow_only'] is True
    assert report['no_execution'] is True
    assert any(gap['missing_lane'] == 'market_structure' for gap in report['gaps'])


def test_context_gap_marks_missing_corporate_filing_for_unverified_issuer_claim() -> None:
    report = compile_context_gaps(_claim_graph(), generated_at='2026-04-16T15:20:00Z')
    assert any(gap['missing_lane'] == 'corporate_filing' for gap in report['gaps'])


def test_context_gap_hash_is_deterministic() -> None:
    first = compile_context_gaps(_claim_graph(), generated_at='2026-04-16T15:20:00Z')
    second = compile_context_gaps(_claim_graph(), generated_at='2026-04-16T15:21:00Z')
    assert first['context_gap_hash'] == second['context_gap_hash']
