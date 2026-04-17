from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from finance_llm_context_pack import build_packs
from query_pack_planner import build_query_packs, main as planner_main


def _scanner_pack() -> dict:
    return {
        'pack_id': 'llm-job-context:scanner:test',
        'scanner_canonical_role': 'planner_first_legacy_observation_bridge',
        'known_symbols_must_not_satisfy_unknown_discovery': ['TSLA', 'NVDA', 'SPX'],
        'fixed_search_budget': {'unknown_discovery_minimum_attempts': 1},
        'top_invalidators': [
            {'invalidator_id': 'I1', 'target_id': 'TSLA', 'description': 'delivery source conflict', 'evidence_refs': ['ev:1']},
        ],
        'top_opportunity_candidates': [
            {'candidate_id': 'O1', 'instrument': 'BNO', 'theme': 'oil supply risk', 'score': 9.2},
        ],
        'top_thesis_deltas': [
            {'thesis_id': 'T1', 'instrument': 'NVDA', 'required_confirmations': ['price continuation', 'flow confirmation']},
        ],
    }


def test_scanner_pack_declares_query_planner_first_boundary() -> None:
    scanner = build_packs()['scanner']
    assert scanner['scanner_canonical_role'] == 'planner_first_legacy_observation_bridge'
    assert scanner['free_form_web_search_canonical_ingestion'] is False
    assert scanner['planner_is_not_evidence'] is True
    assert scanner['query_pack_contract']['additional_properties_allowed'] is False
    assert 'free_form_web_search_as_canonical_ingestion' in scanner['forbidden_actions']
    assert 'query_pack_planner.py' in ' '.join(scanner['required_commands'])
    assert scanner['legacy_observation_bridge']['observations_are_not_canonical_ingestion'] is True


def test_query_pack_planner_emits_required_query_pack_fields() -> None:
    report = build_query_packs(_scanner_pack(), generated_at='2026-04-17T22:00:00Z')
    assert report['status'] == 'pass'
    assert report['free_form_web_search_canonical_ingestion'] is False
    assert report['query_pack_count'] >= 4
    required = {'pack_id', 'lane', 'purpose', 'query', 'freshness', 'allowed_domains', 'required_entities', 'max_results', 'authority_level', 'forbidden', 'planner_not_evidence', 'pack_is_not_authority', 'no_execution'}
    for pack in report['query_packs']:
        assert required <= set(pack)
        assert pack['contract'] == 'query-pack-v1'
        assert pack['lane'] == 'news_policy_narrative'
        assert pack['authority_level'] == 'canonical_candidate'
        assert pack['no_execution'] is True


def test_unknown_discovery_query_pack_carries_known_symbol_exclusions() -> None:
    report = build_query_packs(_scanner_pack(), generated_at='2026-04-17T22:00:00Z')
    unknown = [pack for pack in report['query_packs'] if pack['source_object_refs'] == ['unknown_discovery_lane']]
    assert unknown
    assert {'TSLA', 'NVDA', 'SPX'} <= set(unknown[0]['exclusion_symbols'])
    assert unknown[0]['required_entities'] == []


def test_query_pack_planner_marks_packs_non_authoritative() -> None:
    report = build_query_packs(_scanner_pack(), generated_at='2026-04-17T22:00:00Z')
    for pack in report['query_packs']:
        assert pack['planner_not_evidence'] is True
        assert pack['pack_is_not_authority'] is True
        assert 'judgment_mutation' in pack['forbidden']
        assert 'execution' in pack['forbidden']


def test_query_pack_planner_cli_writes_jsonl_and_report(tmp_path: Path) -> None:
    pack_path = tmp_path / 'scanner.json'
    pack_path.write_text(json.dumps(_scanner_pack()), encoding='utf-8')
    out = Path('/Users/leofitz/.openclaw/workspace/finance/state/query-packs/test-scanner-planned.jsonl')
    report = Path('/Users/leofitz/.openclaw/workspace/finance/state/query-packs/test-scanner-planned-report.json')
    try:
        code = planner_main(['--scanner-pack', str(pack_path), '--out', str(out), '--report', str(report)])
        assert code == 0
        rows = [json.loads(line) for line in out.read_text(encoding='utf-8').splitlines() if line.strip()]
        payload = json.loads(report.read_text(encoding='utf-8'))
        assert rows
        assert payload['query_pack_count'] == len(rows)
        assert payload['planner_role'] == 'query_pack_planner_not_evidence'
    finally:
        out.unlink(missing_ok=True)
        report.unlink(missing_ok=True)
