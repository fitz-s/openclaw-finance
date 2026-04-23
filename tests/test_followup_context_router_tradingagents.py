from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from finance_followup_context_router import route_context


def test_route_context_accepts_tradingagents_handle_from_bundle_slice() -> None:
    bundle = {
        'bundle_id': 'rb:R1234',
        'handles': {'TA1': {'type': 'tradingagents_research', 'ref': 'ta:test'}},
        'object_cards': [{'handle': 'TA1', 'type': 'tradingagents_research', 'label': 'TradingAgents sidecar | NVDA'}],
        'campaign_alias_map': {},
        'followup_slice_index': {
            'TA1': {
                'why': {
                    'evidence_slice_id': 'slice:ta:test:TA1:why',
                    'linked_claims': [],
                    'linked_atoms': [],
                    'linked_context_gaps': [],
                    'lane_coverage': {},
                    'source_health_summary': {},
                    'retrieval_score': 0.0,
                    'permission_metadata': {
                        'review_only': True,
                        'raw_thread_history_allowed': False,
                        'raw_source_dump_allowed': False,
                    },
                    'content_hash': 'sha256:test',
                    'no_execution': True,
                }
            }
        },
    }
    route = route_context(query='why TA1', bundle=bundle, campaign_board={}, campaign_cache={})
    assert route['status'] == 'pass'
    assert route['resolved_primary_handle'] == 'TA1'
    assert route['evidence_slice_id'] == 'slice:ta:test:TA1:why'
    assert route['selected_object_card']['handle'] == 'TA1'
