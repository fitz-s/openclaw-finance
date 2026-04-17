#!/usr/bin/env python3
"""Export sanitized Brave API capability audit for finance ingestion planning."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FINANCE = Path(__file__).resolve().parents[1]
OPENCLAW_HOME = FINANCE.parents[1]
CONFIG = OPENCLAW_HOME / 'openclaw.json'
GATEWAY_ERR = OPENCLAW_HOME / 'logs' / 'gateway.err.log'
DIST = Path('/Users/leofitz/.npm-global/lib/node_modules/openclaw/dist/brave-web-search-provider.runtime-CXY3p9_i.js')
OUT = FINANCE / 'docs' / 'openclaw-runtime' / 'brave-api-capability-audit.json'

OFFICIAL_DOCS_REVIEWED_AT = '2026-04-17'

OFFICIAL_SOURCES = [
    {
        'name': 'Brave Web Search documentation',
        'url': 'https://api-dashboard.search.brave.com/documentation/services/web-search',
        'role': 'web_source_discovery',
    },
    {
        'name': 'Brave News Search documentation',
        'url': 'https://api-dashboard.search.brave.com/documentation/services/news-search',
        'role': 'fresh_news_discovery',
    },
    {
        'name': 'Brave LLM Context documentation',
        'url': 'https://api-dashboard.search.brave.com/documentation/services/llm-context',
        'role': 'selected_source_reading',
    },
    {
        'name': 'Brave Answers documentation',
        'url': 'https://api-dashboard.search.brave.com/documentation/services/answers',
        'role': 'sidecar_synthesis_only',
    },
    {
        'name': 'Brave pricing and rate limits documentation',
        'url': 'https://api-dashboard.search.brave.com/documentation/pricing',
        'role': 'quota_and_plan_boundary',
    },
    {
        'name': 'Brave API terms of service',
        'url': 'https://api-dashboard.search.brave.com/documentation/resources/terms-of-service',
        'role': 'storage_and_redistribution_boundary',
    },
]

OFFICIAL_CAPABILITIES: dict[str, dict[str, Any]] = {
    'brave/web/search': {
        'endpoint': 'GET /res/v1/web/search',
        'authority_boundary': 'source_discovery',
        'best_use': 'Broad source discovery across issuer sites, filings, docs, blogs, and general web coverage.',
        'max_count': 20,
        'max_offset': 9,
        'supports_freshness': True,
        'supports_custom_date_range': True,
        'supports_extra_snippets': True,
        'default_safesearch': 'moderate',
        'current_openclaw_provider_status': 'implemented',
        'recommended_phase': 'phase_04_brave_web_news_fetchers',
    },
    'brave/news/search': {
        'endpoint': 'GET /res/v1/news/search',
        'authority_boundary': 'fresh_news_discovery',
        'best_use': 'Fresh finance/news discovery for current events and market-moving coverage.',
        'max_count': 50,
        'max_offset': 9,
        'supports_freshness': True,
        'supports_custom_date_range': True,
        'supports_extra_snippets': True,
        'default_safesearch': 'strict',
        'current_openclaw_provider_status': 'missing',
        'recommended_phase': 'phase_04_brave_web_news_fetchers',
    },
    'brave/llm/context': {
        'endpoint': 'GET|POST /res/v1/llm/context',
        'authority_boundary': 'selected_source_reading',
        'best_use': 'Grounded reading/extraction for selected source candidates after deterministic discovery.',
        'query_limits': {'max_chars': 400, 'max_words': 50},
        'count_range': [1, 50],
        'maximum_number_of_urls_range': [1, 50],
        'maximum_number_of_tokens_range': [1024, 32768],
        'default_maximum_number_of_tokens': 8192,
        'supports_freshness_officially': True,
        'current_openclaw_provider_status': 'implemented',
        'current_openclaw_mode_gap': 'The installed OpenClaw llm-context web_search mode rejects freshness/date_after/date_before at the abstraction boundary.',
        'recommended_phase': 'phase_05_brave_llm_context_reader',
    },
    'brave/answers/chat_completions': {
        'endpoint': 'POST /res/v1/chat/completions',
        'authority_boundary': 'sidecar_synthesis_only',
        'best_use': 'Brave-grounded synthesis for sidecar exploration; citations can seed evidence candidates but answer prose is not canonical evidence.',
        'model': 'brave',
        'requires_stream_for': ['enable_citations', 'enable_entities', 'enable_research'],
        'current_openclaw_provider_status': 'missing',
        'recommended_phase': 'phase_06_brave_answers_sidecar',
        'promotion_rule': 'Never promote answer text directly; only citation URLs may enter EvidenceAtom candidate flow.',
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def current_mode(config: dict) -> str | None:
    try:
        mode = config['plugins']['entries']['brave']['config']['webSearch'].get('mode')
    except Exception:
        return None
    return str(mode) if mode is not None else None


def implemented_endpoints() -> list[str]:
    text = DIST.read_text(encoding='utf-8', errors='replace') if DIST.exists() else ''
    endpoints = []
    if '/res/v1/web/search' in text:
        endpoints.append('brave/web/search')
    if '/res/v1/llm/context' in text:
        endpoints.append('brave/llm/context')
    if '/res/v1/news/search' in text:
        endpoints.append('brave/news/search')
    if '/chat/completions' in text:
        endpoints.append('brave/answers/chat_completions')
    return endpoints


def quota_failures(limit: int = 20) -> list[dict[str, Any]]:
    if not GATEWAY_ERR.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in GATEWAY_ERR.read_text(encoding='utf-8', errors='replace').splitlines():
        if 'Brave LLM Context API error (402)' not in line and 'USAGE_LIMIT_EXCEEDED' not in line:
            continue
        query = None
        match = re.search(r'raw_params=(\{.*\})', line)
        if match:
            try:
                raw_params = json.loads(match.group(1))
                if isinstance(raw_params, dict):
                    query = raw_params.get('query')
            except Exception:
                query = None
        rows.append({'line_time': line[:25], 'error': 'USAGE_LIMIT_EXCEEDED', 'query': query})
    return rows[-limit:]


def endpoint_inventory(implemented: list[str]) -> dict[str, dict[str, Any]]:
    inventory: dict[str, dict[str, Any]] = {}
    implemented_set = set(implemented)
    for endpoint, capability in OFFICIAL_CAPABILITIES.items():
        row = dict(capability)
        row['installed_openclaw_detected'] = endpoint in implemented_set
        inventory[endpoint] = row
    return inventory


def build_report() -> dict[str, Any]:
    mode = current_mode(load_json(CONFIG))
    implemented = implemented_endpoints()
    required_endpoints = list(OFFICIAL_CAPABILITIES)
    missing = [endpoint for endpoint in required_endpoints if endpoint not in implemented]
    failures = quota_failures()
    return {
        'generated_at': now_iso(),
        'contract': 'brave-api-capability-audit-v1',
        'phase': 'ingestion_fabric_phase_02',
        'reviewed_external_docs_at': OFFICIAL_DOCS_REVIEWED_AT,
        'external_scout_used': True,
        'configured_provider': 'brave',
        'configured_mode': mode,
        'installed_openclaw_provider_dist': str(DIST),
        'implemented_endpoints': implemented,
        'required_endpoints': required_endpoints,
        'missing_endpoints': missing,
        'official_sources': OFFICIAL_SOURCES,
        'endpoint_inventory': endpoint_inventory(implemented),
        'known_mode_limits': {
            'openclaw_llm_context_rejects_freshness': True,
            'openclaw_llm_context_rejects_date_after_before': True,
            'web_mode_supports_freshness_and_date_range': True,
            'official_llm_context_supports_freshness_but_current_openclaw_abstraction_blocks_it': True,
        },
        'quota_health': {
            'status': 'degraded_from_logs' if failures else 'unknown_no_recent_402_in_logs',
            'source': str(GATEWAY_ERR),
            'failure_count_exported': len(failures),
            'limitation': 'Log-derived only; not a live billing API check.',
        },
        'quota_failures': failures,
        'pricing_and_rate_limit_boundary': {
            'search_plan_covers': ['web_search', 'news_search', 'llm_context'],
            'answers_is_separate_plan': True,
            'search_rate_limit_doc': '50 requests/sec on published pricing page as of docs review date; re-check before activation.',
            'answers_rate_limit_doc': '2 requests/sec on published pricing page as of docs review date; re-check before activation.',
            'must_use_rate_limit_headers': True,
        },
        'rights_and_storage_boundary': {
            'do_not_persist_raw_search_results_as_database': True,
            'committed_artifacts_must_be_sanitized': True,
            'search_result_cache_policy': 'transient operational cache only unless Brave contract permits persistence',
            'evidence_policy': 'Persist EvidenceAtom/ClaimAtom derived from independently readable source material; do not commit raw Brave snippets.',
            'api_keys_must_remain_secret': True,
        },
        'authority_boundaries': {
            'brave/web/search': 'source_discovery',
            'brave/news/search': 'fresh_news_discovery',
            'brave/llm/context': 'selected_source_reading',
            'brave/answers/chat_completions': 'sidecar_synthesis_only',
        },
        'recommendation': [
            'Do not activate Brave Answers in the hot path.',
            'Implement query registry and lane watermarks before adding high-volume Brave fetchers.',
            'Use brave/news/search for freshness-sensitive finance discovery.',
            'Use brave/web/search for domain/date-filtered source discovery.',
            'Use brave/llm/context only for selected reading after source discovery.',
            'Use Brave Answers only as sidecar synthesis with citation extraction.',
            'Treat 402 quota failures as source-health degradation instead of recycling stale narratives.',
        ],
        'no_secrets_exported': True,
        'no_api_calls_made_by_exporter': True,
        'no_runtime_config_change': True,
        'no_execution': True,
    }


def main() -> int:
    report = build_report()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'status': 'pass',
        'out': str(OUT),
        'mode': report['configured_mode'],
        'quota_status': report['quota_health']['status'],
        'quota_failures': len(report['quota_failures']),
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
