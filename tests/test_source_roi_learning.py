from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

from context_coverage_audit import build_report as build_coverage
from source_roi_tracker import build_report, campaign_outcome_rows, source_roi_rows


def _source_health() -> dict:
    return {'sources': [
        {'source_id': 'source:reuters', 'freshness_status': 'fresh', 'rights_status': 'restricted'},
        {'source_id': 'source:yfinance', 'freshness_status': 'unknown', 'rights_status': 'ok'},
    ]}


def _atoms() -> list[dict]:
    return [
        {'atom_id': 'atom:news', 'source_id': 'source:reuters', 'source_lane': 'news_policy_narrative'},
        {'atom_id': 'atom:price', 'source_id': 'source:yfinance', 'source_lane': 'market_structure'},
    ]


def _claim_graph() -> dict:
    return {'claims': [
        {'claim_id': 'claim:news', 'atom_id': 'atom:news'},
        {'claim_id': 'claim:price', 'atom_id': 'atom:price'},
    ]}


def _campaign_board() -> dict:
    return {'campaigns': [{
        'campaign_id': 'campaign:tsla',
        'human_title': 'TSLA risk',
        'board_class': 'risk',
        'stage': 'review',
        'stage_reason': 'risk review',
        'source_diversity': 2,
        'known_unknowns': [{'gap_id': 'gap:filing'}],
        'linked_atoms': ['atom:news'],
        'linked_claims': ['claim:news'],
        'linked_context_gaps': ['gap:filing'],
        'cross_lane_confirmation': 2,
    }]}


def test_source_roi_tracker_scores_source_contribution_without_mutation() -> None:
    rows = source_roi_rows(_source_health(), _atoms(), _claim_graph(), _campaign_board(), generated_at='2026-04-17T00:00:00Z')
    by_id = {row['source_id']: row for row in rows}
    assert by_id['source:reuters']['campaign_contribution_count'] == 1
    assert by_id['source:reuters']['source_lane_set'] == ['news_policy_narrative']
    assert by_id['source:reuters']['campaign_value_score'] > 0
    assert by_id['source:reuters']['claim_refs'] == ['claim:news']
    assert by_id['source:reuters']['campaign_refs'] == ['campaign:tsla']
    assert by_id['source:reuters']['context_gap_closure_time_hours'] is None
    assert by_id['source:reuters']['no_threshold_mutation'] is True
    assert by_id['source:reuters']['no_execution'] is True


def test_campaign_outcomes_record_campaign_ids_and_followup_hits() -> None:
    rows = campaign_outcome_rows(_campaign_board(), {'resolved_primary_handle': 'campaign:tsla', 'verb': 'why', 'evidence_slice_id': 'slice:x'}, generated_at='2026-04-17T00:00:00Z')
    assert rows[0]['campaign_id'] == 'campaign:tsla'
    assert rows[0]['followup_hit'] is True
    assert rows[0]['followup_verb'] == 'why'
    assert rows[0]['linked_claims'] == ['claim:news']
    assert rows[0]['linked_context_gaps'] == ['gap:filing']
    assert rows[0]['cross_lane_confirmation'] == 2
    assert rows[0]['peacetime_to_live_conversion'] is False
    assert rows[0]['no_threshold_mutation'] is True


def test_context_coverage_audit_reports_gap_rate() -> None:
    report = build_coverage(_source_health(), {'claims': [{}, {}]}, {'gaps': [{'gap_id': 'g1'}]}, _campaign_board(), {'insufficient_data': True})
    assert report['campaign_context_gap_rate'] == 0.5
    assert report['followup_grounding_failure'] is True
    assert report['no_threshold_mutation'] is True


def test_learning_outputs_no_threshold_mutation() -> None:
    report = build_report(_source_health(), _atoms(), _claim_graph(), _campaign_board(), {'resolved_primary_handle': 'campaign:tsla'})
    assert report['no_threshold_mutation'] is True
    assert all(row['no_threshold_mutation'] for row in report['source_roi_rows'])
    assert all(row['no_threshold_mutation'] for row in report['campaign_outcome_rows'])


def test_source_roi_cli_rejects_unsafe_history_path(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, '/Users/leofitz/.openclaw/workspace/finance/scripts/source_roi_tracker.py', '--source-roi-history', str(tmp_path / 'roi.jsonl')],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert 'unsafe_state_path' in result.stdout
