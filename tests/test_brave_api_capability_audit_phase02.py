from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TOOLS = Path('/Users/leofitz/.openclaw/workspace/finance/tools')
sys.path.insert(0, str(TOOLS))

from export_brave_api_capability_audit import build_report


def test_brave_audit_detects_current_llm_context_mode_and_missing_endpoints() -> None:
    report = build_report()
    assert report['configured_provider'] == 'brave'
    assert report['configured_mode'] in {'llm-context', 'web'}
    assert 'brave/web/search' in report['implemented_endpoints']
    assert 'brave/llm/context' in report['implemented_endpoints']
    assert 'brave/news/search' in report['missing_endpoints']
    assert 'brave/answers/chat_completions' in report['missing_endpoints']
    assert report['no_secrets_exported'] is True


def test_brave_audit_documents_llm_context_time_filter_gap() -> None:
    report = build_report()
    limits = report['known_mode_limits']
    assert limits['openclaw_llm_context_rejects_freshness'] is True
    assert limits['openclaw_llm_context_rejects_date_after_before'] is True
    assert limits['official_llm_context_supports_freshness_but_current_openclaw_abstraction_blocks_it'] is True


def test_brave_audit_records_official_endpoint_roles() -> None:
    report = build_report()
    inventory = report['endpoint_inventory']
    assert inventory['brave/web/search']['authority_boundary'] == 'source_discovery'
    assert inventory['brave/news/search']['authority_boundary'] == 'fresh_news_discovery'
    assert inventory['brave/news/search']['max_count'] == 50
    assert inventory['brave/llm/context']['authority_boundary'] == 'selected_source_reading'
    assert inventory['brave/answers/chat_completions']['authority_boundary'] == 'sidecar_synthesis_only'
    assert inventory['brave/answers/chat_completions']['promotion_rule'].startswith('Never promote answer text')


def test_brave_audit_preserves_rights_and_storage_boundary() -> None:
    report = build_report()
    boundary = report['rights_and_storage_boundary']
    assert boundary['do_not_persist_raw_search_results_as_database'] is True
    assert boundary['committed_artifacts_must_be_sanitized'] is True
    assert boundary['api_keys_must_remain_secret'] is True
    assert report['no_api_calls_made_by_exporter'] is True
    assert report['no_runtime_config_change'] is True


def test_brave_audit_exports_no_obvious_api_secret() -> None:
    report_text = json.dumps(build_report(), sort_keys=True)
    assert 'X-Subscription-Token' not in report_text
    assert not re.search(r'BSA[a-zA-Z0-9_-]{20,}', report_text)
    assert not re.search(r'brave[-_ ]?api[-_ ]?key', report_text, re.IGNORECASE)
