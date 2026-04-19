from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'docs' / 'review-04-17-2026.md'
RALPLAN = ROOT / 'docs' / 'openclaw-runtime' / 'ralplan' / 'source-to-campaign-phase-00-review-intake-ralplan.md'
LEDGER = ROOT / 'docs' / 'openclaw-runtime' / 'source-to-campaign-phase-ledger.json'
CRITIC = ROOT / 'docs' / 'openclaw-runtime' / 'critics' / 'source-to-campaign-phase-00-implementation-critic.md'


def test_phase00_ralplan_embeds_full_review_text() -> None:
    review = REVIEW.read_text(encoding='utf-8')
    ralplan = RALPLAN.read_text(encoding='utf-8')
    assert '<!-- REVIEW_04_17_2026_FULL_TEXT_BEGIN -->' in ralplan
    assert '<!-- REVIEW_04_17_2026_FULL_TEXT_END -->' in ralplan
    assert review in ralplan
    digest = hashlib.sha256(review.encode()).hexdigest()
    ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
    assert ledger['source_review_sha256'] == digest


def test_phase_ledger_covers_review_required_workstreams() -> None:
    ledger = json.loads(LEDGER.read_text(encoding='utf-8'))
    phase_text = json.dumps(ledger, ensure_ascii=False)
    required = [
        'Source Office 2.0',
        'source scout',
        'EvidenceAtom',
        'ClaimAtom',
        'ContextGap',
        'Options and IV sensitivity',
        'Report-time archive and exact replay',
        'Undercurrent Engine',
        'Campaign OS',
        'Verb-specific follow-up',
        'Deep-dive cache',
        '72h inactive finance thread lifecycle',
        'Reviewer packet exact replay',
        'Source ROI',
        'Final active cutover',
        'Monitoring',
    ]
    for item in required:
        assert item in phase_text
    phases = ledger['phases']
    assert [phase['phase'] for phase in phases] == list(range(15))
    assert all('acceptance' in phase and phase['acceptance'] for phase in phases)


def test_phase00_critic_approves_without_runtime_touch() -> None:
    critic = CRITIC.read_text(encoding='utf-8')
    assert 'Verdict: APPROVE' in critic
    assert 'does not change active runtime' in critic
    assert 'options/IV' in critic
    assert '72h inactive thread lifecycle' in critic
