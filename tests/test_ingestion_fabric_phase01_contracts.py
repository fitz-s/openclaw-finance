from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / 'docs' / 'openclaw-runtime' / 'contracts'


def test_query_pack_contract_defines_planner_not_evidence_boundary() -> None:
    text = (CONTRACTS / 'query-pack-contract.md').read_text(encoding='utf-8')
    for needle in ['lane', 'purpose', 'freshness', 'date_after', 'allowed_domains', 'authority_level', 'sidecar_only']:
        assert needle in text
    assert 'QueryPack is not evidence' in text
    assert 'Brave Answers packs must use `authority_level=sidecar_only`' in text


def test_source_fetch_record_contract_captures_quota_and_watermark() -> None:
    text = (CONTRACTS / 'source-fetch-record-contract.md').read_text(encoding='utf-8')
    for needle in ['fetch_id', 'pack_id', 'endpoint', 'request_params', 'quota_state', 'result_count', 'watermark_key', 'rate_limited']:
        assert needle in text
    assert 'cannot directly drive reports' in text


def test_source_atom_contract_links_to_fetch_record() -> None:
    text = (CONTRACTS / 'source-atom-contract.md').read_text(encoding='utf-8')
    assert 'fetch_id' in text
    assert 'SourceFetchRecord' in text
