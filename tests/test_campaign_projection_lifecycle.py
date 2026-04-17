from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from campaign_projection_compiler import build_stage_transitions, build_thread_registry, compile_campaign_board


def _undercurrents() -> dict:
    return {'undercurrents': [{
        'undercurrent_id': 'und:tsla',
        'human_title': 'TSLA｜delivery risk undercurrent',
        'source_type': 'invalidator_cluster',
        'persistence_score': 9,
        'velocity': 3,
        'divergence': 'medium',
        'crowding': 'unknown',
        'hedge_gap': 'unknown',
        'promotion_reason': 'TSLA delivery risk keeps accumulating',
        'kill_conditions': ['risk clears'],
        'linked_refs': {
            'thesis': ['thesis:tsla'],
            'scenario': [],
            'opportunity': [],
            'invalidator': ['inv:tsla'],
            'capital_graph': [],
            'atom': ['atom:news'],
            'claim': ['claim:news'],
            'context_gap': ['gap:filing'],
        },
        'source_freshness': {'status': 'mixed', 'source_refs': ['state:claim-graph.json']},
        'source_diversity': 2,
        'cross_lane_confirmation': 2,
        'contradiction_load': 1,
        'known_unknowns': [{'gap_id': 'gap:filing', 'missing_lane': 'corporate_filing', 'why_load_bearing': 'issuer confirmation missing'}],
        'source_health_summary': {'degraded_count': 1, 'degraded_sources': ['source:yfinance']},
        'no_execution': True,
    }]}


def test_campaign_projection_carries_undercurrent_shadow_refs() -> None:
    board = compile_campaign_board({}, {}, {}, {}, {}, {}, {}, _undercurrents())
    campaign = board['campaigns'][0]
    assert campaign['linked_atoms'] == ['atom:news']
    assert campaign['linked_claims'] == ['claim:news']
    assert campaign['linked_context_gaps'] == ['gap:filing']
    assert campaign['known_unknowns'][0]['missing_lane'] == 'corporate_filing'
    assert campaign['source_health_summary']['degraded_count'] == 1
    assert campaign['no_execution'] is True


def test_campaign_stage_reason_uses_quality_fields_without_authority_change() -> None:
    board = compile_campaign_board({}, {}, {}, {}, {}, {}, {}, _undercurrents())
    campaign = board['campaigns'][0]
    assert campaign['stage'] in {'review', 'candidate', 'accumulating'}
    assert 'source_diversity=2' in campaign['stage_reason']
    assert campaign['last_stage_hash'].startswith('sha256:')
    assert board['no_execution'] is True


def test_campaign_stage_history_records_transition() -> None:
    board = compile_campaign_board({}, {}, {}, {}, {}, {}, {}, _undercurrents())
    transitions = build_stage_transitions(board['campaigns'], [], generated_at='2026-04-17T00:00:00Z')
    assert len(transitions) == 1
    row = transitions[0]
    assert row['campaign_id'] == board['campaigns'][0]['campaign_id']
    assert row['no_execution'] is True
    assert row['source_refs']['claims'] == ['claim:news']


def test_campaign_threads_registry_is_local_unbound_by_default() -> None:
    board = compile_campaign_board({}, {}, {}, {}, {}, {}, {}, _undercurrents())
    registry = build_thread_registry(board['campaigns'], {}, generated_at='2026-04-17T00:00:00Z')
    record = next(iter(registry['threads'].values()))
    assert record['thread_status'] == 'unbound'
    assert record['discord_thread_id'] is None
    assert registry['thread_is_ui_not_memory'] is True
    assert registry['no_execution'] is True


def test_campaign_projection_cli_writes_local_lifecycle_artifacts(tmp_path) -> None:
    undercurrents = tmp_path / 'undercurrents.json'
    out = Path('/Users/leofitz/.openclaw/workspace/finance/state/test-campaign-board.json')
    stage = Path('/Users/leofitz/.openclaw/workspace/finance/state/test-campaign-stage-history.jsonl')
    threads = Path('/Users/leofitz/.openclaw/workspace/finance/state/test-campaign-threads.json')
    for path in [out, stage, threads]:
        if path.exists():
            path.unlink()
    undercurrents.write_text(json.dumps(_undercurrents(), ensure_ascii=False))
    result = subprocess.run(
        [
            sys.executable,
            '/Users/leofitz/.openclaw/workspace/finance/scripts/campaign_projection_compiler.py',
            '--capital-agenda', str(tmp_path / 'missing-agenda.json'),
            '--thesis-registry', str(tmp_path / 'missing-thesis.json'),
            '--opportunities', str(tmp_path / 'missing-opps.json'),
            '--invalidators', str(tmp_path / 'missing-inv.json'),
            '--scenarios', str(tmp_path / 'missing-scenarios.json'),
            '--capital-graph', str(tmp_path / 'missing-graph.json'),
            '--displacement-cases', str(tmp_path / 'missing-displacement.json'),
            '--undercurrents', str(undercurrents),
            '--out', str(out),
            '--stage-history', str(stage),
            '--campaign-threads', str(threads),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert out.exists()
    assert stage.exists()
    assert threads.exists()
    registry = json.loads(threads.read_text())
    assert next(iter(registry['threads'].values()))['thread_status'] == 'unbound'
