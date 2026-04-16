from __future__ import annotations

import json
import sys
from pathlib import Path


SCRIPTS = Path('/Users/leofitz/.openclaw/workspace/finance/scripts')
sys.path.insert(0, str(SCRIPTS))

from finance_llm_context_pack import MAX_PACK_CHARS, build_packs
from finance_worker import compact_seen_ids


def test_llm_context_packs_are_non_authoritative_and_provenance_bearing() -> None:
    packs = build_packs()

    assert set(packs) == {'report-orchestrator', 'scanner', 'thesis-sidecar', 'weekly-learning', 'report-followup'}
    for pack in packs.values():
        encoded = json.dumps(pack, ensure_ascii=False, sort_keys=True)
        assert len(encoded) <= MAX_PACK_CHARS
        assert pack['pack_is_not_authority'] is True
        assert 'ContextPacket/WakeDecision/JudgmentEnvelope' in pack['canonical_authority']
        assert pack['source_artifacts']
        assert all('path' in item and 'hash' in item and 'required' in item for item in pack['source_artifacts'])
        assert pack['forbidden_actions']
        assert 'accountId' not in encoded
        assert 'acctAlias' not in encoded
        assert 'FlexQueryResponse' not in encoded


def test_report_pack_has_candidate_contract_and_evidence_boundaries() -> None:
    report = build_packs()['report-orchestrator']

    assert 'judgment-envelope-candidate.json' in report['candidate_contract']['path']
    assert report['candidate_contract']['scheduled_context_allowed_thesis_states'] == ['no_trade', 'watch']
    assert report['candidate_contract']['evidence_rule'] == 'candidate evidence_refs must be subset of allowed_evidence_refs'
    for row in report['allowed_evidence_refs']:
        assert row.get('evidence_id')
        assert row.get('source_artifact')
        assert row.get('source_ref')


def test_scanner_pack_has_hard_unknown_discovery_contract() -> None:
    scanner = build_packs()['scanner']

    assert scanner['fixed_search_budget']['unknown_discovery_minimum_attempts'] >= 1
    assert 'unknown_discovery_exhausted_reason' in scanner['observation_schema_extension']
    assert 'held_or_watchlist_as_unknown' in scanner['forbidden_actions']
    assert isinstance(scanner['known_symbols_must_not_satisfy_unknown_discovery'], list)


def test_sidecar_and_weekly_packs_cannot_deliver_or_mutate_thresholds() -> None:
    packs = build_packs()
    sidecar = packs['thesis-sidecar']
    weekly = packs['weekly-learning']

    assert 'discord' in sidecar['forbidden_actions']
    assert 'threshold_mutation' in sidecar['forbidden_actions']
    assert 'automatic_threshold_mutation' in weekly['forbidden_actions']
    assert 'model_routing' in weekly['recommendation_targets_allowed']


def test_followup_pack_prefers_bundle_rehydration() -> None:
    followup = build_packs()['report-followup']

    assert followup['followup_bundle_path'].endswith('latest.json')
    assert 'bundle is memory' in followup['rehydration_rule']
    assert {'why', 'challenge', 'compare', 'scenario', 'sources', 'expand'} <= set(followup['answer_format']['interrogation_verbs'])


def test_finance_worker_seen_id_helper_remains_deterministic() -> None:
    assert compact_seen_ids(['a', 'b', 'a', None, 'c'], limit=3) == ['a', 'b', 'c']
