from __future__ import annotations

import json
from pathlib import Path


JOBS = Path('/Users/leofitz/.openclaw/cron/jobs.json')


def jobs_by_name() -> dict[str, dict]:
    payload = json.loads(JOBS.read_text())
    return {
        item.get('name'): item
        for item in payload.get('jobs', [])
        if isinstance(item, dict) and item.get('name')
    }


def message(job: dict) -> str:
    payload = job.get('payload') if isinstance(job.get('payload'), dict) else {}
    return str(payload.get('message') or '')


def test_report_orchestrator_prompt_is_context_pack_first() -> None:
    job = jobs_by_name()['finance-premarket-brief']
    text = message(job)

    assert job['enabled'] is True
    assert job['delivery']['mode'] == 'announce'
    assert 'finance_llm_context_pack.py' in text
    assert 'llm-job-context/report-orchestrator.json' in text
    assert 'pack_is_not_authority' in text
    assert 'judgment-envelope-candidate.json' in text
    assert '--context-pack /Users/leofitz/.openclaw/workspace/finance/state/llm-job-context/report-orchestrator.json' in text
    assert 'no_trade|watch' in text
    assert 'allowed_evidence_refs' in text
    assert 'delivery safety' in text or 'Delivery safety' in text
    assert 'finance-decision-report-envelope.json' in text


def test_scanner_prompts_have_object_link_and_unknown_discovery_contract() -> None:
    jobs = jobs_by_name()
    for name in ['finance-subagent-scanner', 'finance-subagent-scanner-offhours']:
        job = jobs[name]
        text = message(job)
        assert job['enabled'] is True
        assert job['delivery']['mode'] == 'none'
        assert 'finance_llm_context_pack.py' in text
        assert 'llm-job-context/scanner.json' in text
        assert 'pack_is_not_authority' in text or 'view cache' in text
        assert 'object_links' in text
        assert 'unknown_discovery_exhausted_reason' in text
        assert '不得把已在 watchlist/held 的标的当作 unknown_discovery' in text
        assert 'unknown_discovery_minimum_attempts' in text


def test_sidecar_job_is_manual_or_disabled_and_has_no_delivery() -> None:
    job = jobs_by_name()['finance-thesis-sidecar']
    text = message(job)

    assert job.get('enabled') is False
    assert job.get('schedule', {}).get('kind') == 'manual'
    assert job.get('delivery', {}).get('mode') == 'none'
    assert 'llm-job-context/thesis-sidecar.json' in text
    assert 'pack_is_not_authority' in text or 'view cache' in text
    assert 'thesis_research_sidecar.py' in text
    assert '禁止 Discord' in text or 'no Discord' in text
    assert '禁止自动改 thresholds' in text
    assert '禁止交易执行' in text


def test_weekly_learning_prompt_uses_context_pack_and_forbids_threshold_mutation() -> None:
    job = jobs_by_name()['finance-weekly-learning-review']
    text = message(job)

    assert job['enabled'] is True
    assert 'finance_llm_context_pack.py' in text
    assert 'llm-job-context/weekly-learning.json' in text
    assert 'pack_is_not_authority' in text or 'view cache' in text
    assert 'dispatch-attribution' in text
    assert 'thesis-outcomes' in text
    assert 'report-usefulness-history' in text
    assert '禁止自动改 thresholds' in text
    assert 'Recommendation 只能指向 policy / schema / tests / prompt / model_routing' in text
