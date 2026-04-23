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


def test_premarket_report_job_is_deterministic_stdout_only() -> None:
    job = jobs_by_name()['finance-premarket-brief']
    text = message(job)

    assert job['enabled'] is True
    assert job['delivery']['mode'] == 'announce'
    assert job['sessionKey'] == 'agent:main:cron:finance-premarket-brief'
    assert job['sessionTarget'] == 'isolated'
    assert 'OpenClaw Finance Deterministic Report Job' in text
    assert 'finance_discord_report_job.py --mode marketday-review' in text
    assert 'Return stdout exactly' in text
    assert 'Do not emit progress text' in text
    assert 'Do not summarize' in text
    assert 'Do not send messages yourself' in text
    assert 'OpenClaw Finance Report Orchestrator' not in text
    assert "Now I'll" not in text


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


def test_tradingagents_sidecar_job_is_enabled_cron_and_has_no_delivery() -> None:
    job = jobs_by_name()['finance-tradingagents-sidecar']
    text = message(job)

    assert job.get('enabled') is True
    assert job.get('schedule', {}).get('kind') == 'cron'
    assert job.get('schedule', {}).get('expr') == '15 8-18 * * 1-5'
    assert job.get('schedule', {}).get('tz') == 'America/Chicago'
    assert job.get('delivery', {}).get('mode') == 'none'
    assert 'finance_llm_context_pack.py' in text
    assert 'llm-job-context/tradingagents-sidecar.json' in text
    assert 'thesis_research_packet.py' in text
    assert 'tradingagents_sidecar_job.py --mode scheduled' in text
    assert 'view cache' in text or 'pack_is_not_authority' in text
    assert '禁止 Discord' in text or 'no Discord' in text
    assert '禁止自动改 thresholds' in text
    assert '禁止交易执行' in text
    assert 'state/tradingagents/' in text


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
