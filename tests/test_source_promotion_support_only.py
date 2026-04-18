from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


PROMOTION = Path('/Users/leofitz/.openclaw/workspace/services/market-ingest/normalizer/source_promotion.py')


def _load_module():
    spec = importlib.util.spec_from_file_location('source_promotion_test_module', PROMOTION)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _registry() -> list[dict]:
    return [
        {
            'source_id': 'source:unknown_web',
            'reliability_tier': 'T3_untrusted_or_syndicated',
            'latency_class': 'unknown',
            'license_usage': 'unknown',
            'domain_patterns': ['*'],
            'eligible_for_wake': False,
            'eligible_for_judgment_support': False,
            'title_only_policy': 'context_only',
        }
    ]


def test_confirmed_unknown_web_headline_is_support_only_not_wake() -> None:
    module = _load_module()
    case = {
        'fixture_id': 'hormuz-confirmed-headline',
        'raw_ref': 'finance-scan:hormuz-confirmed-headline',
        'title': '2 Indian-Flagged Vessels Attacked By Iran Gunboats In Hormuz',
        'source': 'native-emergency-news',
        'published_at': '2026-04-18T13:00:44Z',
        'observed_at': '2026-04-18T13:12:44Z',
        'detected_at': '2026-04-18T13:12:44Z',
    }

    candidate = module.candidate_from_case(case, _registry())
    result = module.promote_candidate(candidate, _registry())

    assert result['decision'] == 'CONTEXT_ONLY'
    assert result['allowed_for_wake'] is False
    assert result['allowed_for_judgment_support'] is True
    assert result['support_requires_primary_confirmation'] is True
    assert result['support_scope'] == 'confirmed_headline_metadata_only'
    assert result['support_reason_code'] == 'confirmed_untrusted_headline_requires_primary_confirmation'


def test_speculative_unknown_web_headline_stays_non_supporting() -> None:
    module = _load_module()
    case = {
        'fixture_id': 'rumor-headline',
        'raw_ref': 'finance-scan:rumor-headline',
        'title': 'Could oil stocks crash or rally next week?',
        'source': 'native-emergency-news',
        'published_at': '2026-04-18T13:00:44Z',
        'observed_at': '2026-04-18T13:12:44Z',
        'detected_at': '2026-04-18T13:12:44Z',
    }

    candidate = module.candidate_from_case(case, _registry())
    result = module.promote_candidate(candidate, _registry())

    assert result['decision'] == 'QUARANTINE'
    assert result['allowed_for_wake'] is False
    assert result['allowed_for_judgment_support'] is False
    assert result['support_requires_primary_confirmation'] is False


def test_targeted_or_closes_language_counts_as_confirmed_event() -> None:
    module = _load_module()
    case = {
        'fixture_id': 'hormuz-targeted-headline',
        'raw_ref': 'finance-scan:hormuz-targeted-headline',
        'title': 'Gunfire in Hormuz: Indian-flagged tanker targeted as Iran closes strait again',
        'source': 'native-emergency-news',
        'published_at': '2026-04-18T13:00:44Z',
        'observed_at': '2026-04-18T13:12:44Z',
        'detected_at': '2026-04-18T13:12:44Z',
    }

    candidate = module.candidate_from_case(case, _registry())
    result = module.promote_candidate(candidate, _registry())

    assert result['allowed_for_wake'] is False
    assert result['allowed_for_judgment_support'] is True
    assert result['support_requires_primary_confirmation'] is True
