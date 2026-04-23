#!/usr/bin/env python3
"""Resolve OpenClaw role policy into TradingAgents provider-native config."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


FINANCE = Path('/Users/leofitz/.openclaw/workspace/finance')
OPENCLAW_WORKSPACE = FINANCE.parent
MODEL_ROLES = OPENCLAW_WORKSPACE / 'ops' / 'model-roles.json'
TRADINGAGENTS_MODELS = FINANCE / 'third_party' / 'tradingagents' / 'tradingagents' / 'llm_clients' / 'model_catalog.py'

SUPPORTED_ALIAS_FAMILIES = {
    'google-gemini-cli': 'google',
    'openai-codex': 'openai',
    'claude-max': 'anthropic',
}
UNSUPPORTED_ALIAS_FAMILIES = {
    'minimax-portal': 'unsupported_openclaw_alias_family:minimax-portal',
}
ALLOWED_AUTH_SOURCES = {
    'OPENAI_API_KEY',
    'GOOGLE_API_KEY',
    'ANTHROPIC_API_KEY',
    'OPENROUTER_API_KEY',
    'none',
}
PROVIDER_OPTION_KEYS = {
    'google_thinking_level',
    'openai_reasoning_effort',
    'anthropic_effort',
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def _load_known_models() -> dict[str, list[str]]:
    spec = importlib.util.spec_from_file_location('tradingagents_model_catalog', TRADINGAGENTS_MODELS)
    if not spec or not spec.loader:
        return {}
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_known_models()  # type: ignore[attr-defined]


def alias_family(alias: str) -> str:
    return alias.split('/', 1)[0] if '/' in alias else alias


def resolve_tradingagents_role(
    *,
    job_name: str = 'finance-tradingagents-sidecar',
    roles_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    roles_payload = roles_payload if isinstance(roles_payload, dict) else load_json(MODEL_ROLES)
    role_map = roles_payload.get('roles', {}) if isinstance(roles_payload.get('roles'), dict) else {}
    assignments = roles_payload.get('job_assignments', {}) if isinstance(roles_payload.get('job_assignments'), dict) else {}
    role_name = assignments.get(job_name)
    if not role_name:
        return {
            'status': 'unsupported',
            'job_name': job_name,
            'unsupported_reason': 'missing_job_assignment',
            'resolution_contract_version': 'v1',
        }
    role = role_map.get(role_name)
    if not isinstance(role, dict):
        return {
            'status': 'unsupported',
            'job_name': job_name,
            'role_name': role_name,
            'unsupported_reason': 'missing_role_definition',
            'resolution_contract_version': 'v1',
        }

    runtime_alias = str(role.get('model') or '')
    family = alias_family(runtime_alias)
    if family in UNSUPPORTED_ALIAS_FAMILIES:
        return {
            'status': 'unsupported',
            'job_name': job_name,
            'role_name': role_name,
            'openclaw_runtime_alias': runtime_alias,
            'unsupported_reason': UNSUPPORTED_ALIAS_FAMILIES[family],
            'resolution_contract_version': 'v1',
        }

    integration = (((role.get('integrations') or {}).get('tradingagents')) if isinstance(role.get('integrations'), dict) else None)
    if not isinstance(integration, dict):
        return {
            'status': 'unsupported',
            'job_name': job_name,
            'role_name': role_name,
            'openclaw_runtime_alias': runtime_alias,
            'unsupported_reason': 'missing_tradingagents_integration_metadata',
            'resolution_contract_version': 'v1',
        }
    if integration.get('enabled') is not True:
        return {
            'status': 'unsupported',
            'job_name': job_name,
            'role_name': role_name,
            'openclaw_runtime_alias': runtime_alias,
            'unsupported_reason': 'tradingagents_integration_disabled',
            'resolution_contract_version': 'v1',
        }

    provider = str(integration.get('provider') or '')
    expected_provider = SUPPORTED_ALIAS_FAMILIES.get(family)
    if not expected_provider:
        return {
            'status': 'unsupported',
            'job_name': job_name,
            'role_name': role_name,
            'openclaw_runtime_alias': runtime_alias,
            'unsupported_reason': f'unknown_openclaw_alias_family:{family}',
            'resolution_contract_version': 'v1',
        }
    if provider != expected_provider:
        return {
            'status': 'unsupported',
            'job_name': job_name,
            'role_name': role_name,
            'openclaw_runtime_alias': runtime_alias,
            'unsupported_reason': f'provider_alias_mismatch:{provider}:{expected_provider}',
            'resolution_contract_version': 'v1',
        }

    quick_model = str(integration.get('quick_model') or '')
    deep_model = str(integration.get('deep_model') or '')
    auth_source = str(integration.get('auth_source') or '')
    if not quick_model or not deep_model:
        return {
            'status': 'unsupported',
            'job_name': job_name,
            'role_name': role_name,
            'openclaw_runtime_alias': runtime_alias,
            'unsupported_reason': 'missing_quick_or_deep_model',
            'resolution_contract_version': 'v1',
        }
    if auth_source not in ALLOWED_AUTH_SOURCES:
        return {
            'status': 'unsupported',
            'job_name': job_name,
            'role_name': role_name,
            'openclaw_runtime_alias': runtime_alias,
            'unsupported_reason': f'unsupported_auth_source:{auth_source}',
            'resolution_contract_version': 'v1',
        }

    known_models = _load_known_models()
    provider_known = set(known_models.get(provider, []))
    if provider_known:
        if quick_model not in provider_known:
            return {
                'status': 'unsupported',
                'job_name': job_name,
                'role_name': role_name,
                'openclaw_runtime_alias': runtime_alias,
                'unsupported_reason': f'unknown_quick_model:{quick_model}',
                'resolution_contract_version': 'v1',
            }
        if deep_model not in provider_known:
            return {
                'status': 'unsupported',
                'job_name': job_name,
                'role_name': role_name,
                'openclaw_runtime_alias': runtime_alias,
                'unsupported_reason': f'unknown_deep_model:{deep_model}',
                'resolution_contract_version': 'v1',
            }

    provider_options = {
        key: integration.get(key)
        for key in PROVIDER_OPTION_KEYS
        if key in integration and integration.get(key) is not None
    }

    return {
        'status': 'supported',
        'job_name': job_name,
        'role_name': role_name,
        'openclaw_runtime_alias': runtime_alias,
        'provider': provider,
        'quick_model': quick_model,
        'deep_model': deep_model,
        'base_url': integration.get('base_url'),
        'auth_source': auth_source,
        'provider_options': provider_options,
        'unsupported_reason': None,
        'resolution_contract_version': str(integration.get('resolution_contract_version') or 'v1'),
    }


def resolved_tradingagents_config(job_name: str = 'finance-tradingagents-sidecar') -> dict[str, Any]:
    resolved = resolve_tradingagents_role(job_name=job_name)
    if resolved.get('status') != 'supported':
        reason = resolved.get('unsupported_reason') or 'unknown'
        raise ValueError(f'TradingAgents model resolution failed: {reason}')
    config = {
        'llm_provider': resolved['provider'],
        'deep_think_llm': resolved['deep_model'],
        'quick_think_llm': resolved['quick_model'],
        'backend_url': resolved.get('base_url'),
    }
    config.update(resolved.get('provider_options', {}) if isinstance(resolved.get('provider_options'), dict) else {})
    return config


if __name__ == '__main__':
    print(json.dumps(resolve_tradingagents_role(), indent=2, ensure_ascii=False))
