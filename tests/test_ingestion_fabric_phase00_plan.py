from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'docs' / 'review2-04-17-2026.md'
RALPLAN = ROOT / 'docs' / 'openclaw-runtime' / 'ralplan' / 'ingestion-fabric-phase-00-review2-intake-ralplan.md'
LEDGER = ROOT / 'docs' / 'openclaw-runtime' / 'ingestion-fabric-phase-ledger.json'
CRITIC = ROOT / 'docs' / 'openclaw-runtime' / 'critics' / 'ingestion-fabric-phase-00-implementation-critic.md'


def test_ingestion_fabric_ralplan_embeds_full_review2() -> None:
    review = REVIEW.read_text(encoding='utf-8')
    ralplan = RALPLAN.read_text(encoding='utf-8')
    assert '<!-- REVIEW2_04_17_2026_FULL_TEXT_BEGIN -->' in ralplan
    assert '<!-- REVIEW2_04_17_2026_FULL_TEXT_END -->' in ralplan
    assert review in ralplan
    assert json.loads(LEDGER.read_text())['source_review_sha256'] == hashlib.sha256(review.encode('utf-8')).hexdigest()


def test_ingestion_fabric_ledger_covers_review2_core_requirements() -> None:
    ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
    text = json.dumps(ledger, ensure_ascii=False)
    required = [
        'QueryPack',
        'SourceFetchRecord',
        'EvidenceAtom',
        'ClaimAtom',
        'ContextGap',
        'Brave Web',
        'Brave Answers',
        'query_registry',
        'lane_watermarks',
        'source_memory_index',
        'finance_worker reducer',
        'Parent market-ingest',
    ]
    for item in required:
        assert item in text
    phases = ledger['phases']
    assert [phase['phase'] for phase in phases] == list(range(14))


def test_ingestion_phase00_critic_approves_no_runtime_change() -> None:
    critic = CRITIC.read_text(encoding='utf-8')
    assert 'Verdict: APPROVE' in critic
    assert 'does not alter active runtime' in critic
    assert 'Brave Answers canonical authority' in critic
