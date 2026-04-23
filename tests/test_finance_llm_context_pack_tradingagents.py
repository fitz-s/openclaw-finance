from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

import finance_llm_context_pack as pack


def test_load_tradingagents_digest_filters_and_build_packs_include_sidecar(monkeypatch, tmp_path: Path) -> None:
    digest_path = tmp_path / 'latest-context-digest.json'
    digest = {
        'generated_at': '2099-04-23T00:00:00Z',
        'run_id': 'ta:test',
        'instrument': 'NVDA',
        'analysis_date': '2026-04-23',
        'report_hash': 'sha256:report',
        'packet_hash': 'sha256:packet',
        'safe_bullets': ['Demand remains durable and requires validation.'],
        'invalidators_safe': ['If deterministic sources disagree, deprioritize the sidecar.'],
        'required_confirmations_safe': ['Validate source freshness before review use.'],
        'source_gaps_safe': ['No deterministic citation promotion exists yet.'],
        'risk_flags_safe': ['Wait for valuation confirmation.'],
        'authority_rule': 'non_authoritative_context_only_not_evidence_wake_threshold_or_execution',
        'candidate_contract_exclusion': True,
        'validation_ref': '/tmp/validation.json',
        'review_only': True,
        'no_execution': True,
        'max_age_hours': 24,
    }
    digest_path.write_text(json.dumps(digest), encoding='utf-8')
    monkeypatch.setattr(pack, 'TRADINGAGENTS_CONTEXT_DIGEST', digest_path)

    loaded = pack.load_tradingagents_digest()
    assert loaded is not None
    report = pack.build_packs()['report-orchestrator']
    assert 'tradingagents_sidecar' in report
    assert report['tradingagents_sidecar']['run_id'] == 'ta:test'
    assert report['candidate_contract']['evidence_rule'] == 'candidate evidence_refs must be subset of allowed_evidence_refs'


def test_load_tradingagents_digest_excludes_stale_payload(monkeypatch, tmp_path: Path) -> None:
    digest_path = tmp_path / 'latest-context-digest.json'
    digest_path.write_text(json.dumps({
        'generated_at': '2020-04-23T00:00:00Z',
        'candidate_contract_exclusion': True,
        'review_only': True,
        'no_execution': True,
        'max_age_hours': 1,
    }), encoding='utf-8')
    monkeypatch.setattr(pack, 'TRADINGAGENTS_CONTEXT_DIGEST', digest_path)
    assert pack.load_tradingagents_digest() is None
