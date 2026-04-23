from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path('/Users/leofitz/.openclaw/workspace/finance')
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from tradingagents_model_resolution import resolve_tradingagents_role, resolved_tradingagents_config


def test_resolve_tradingagents_role_from_parent_policy() -> None:
    resolved = resolve_tradingagents_role()
    assert resolved['status'] == 'supported'
    assert resolved['job_name'] == 'finance-tradingagents-sidecar'
    assert resolved['role_name'] == 'finance-tradingagents'
    assert resolved['provider'] == 'google'
    assert resolved['quick_model'] == 'gemini-3-flash-preview'
    assert resolved['deep_model'] == 'gemini-3.1-pro-preview'
    assert resolved['auth_source'] == 'GOOGLE_API_KEY'
    assert resolved['openclaw_runtime_alias'] == 'google-gemini-cli/gemini-3-flash-preview'


def test_finance_model_roles_snapshot_matches_parent_policy_for_tradingagents() -> None:
    parent_roles = json.loads((ROOT.parent / 'ops' / 'model-roles.json').read_text(encoding='utf-8'))
    snapshot_roles = json.loads((ROOT / 'docs' / 'openclaw-runtime' / 'finance-model-roles.json').read_text(encoding='utf-8'))
    parent_role = parent_roles['roles']['finance-tradingagents']
    snapshot_role = snapshot_roles['roles']['finance-tradingagents']

    assert snapshot_roles['job_assignments']['finance-tradingagents-sidecar'] == 'finance-tradingagents'
    assert snapshot_role == parent_role


def test_tradingagents_defaults_do_not_override_model_resolution() -> None:
    defaults = json.loads((ROOT / 'ops' / 'tradingagents-sidecar.defaults.json').read_text(encoding='utf-8'))
    for key in ('llm_provider', 'quick_think_llm', 'deep_think_llm', 'backend_url'):
        assert key not in defaults


def test_resolve_tradingagents_role_rejects_unsupported_family() -> None:
    payload = {
        'roles': {
            'bad-role': {
                'model': 'minimax-portal/MiniMax-M2.7',
                'integrations': {
                    'tradingagents': {
                        'enabled': True,
                        'provider': 'google',
                        'quick_model': 'gemini-3-flash-preview',
                        'deep_model': 'gemini-3.1-pro-preview',
                        'auth_source': 'GOOGLE_API_KEY',
                        'resolution_contract_version': 'v1',
                    }
                },
            }
        },
        'job_assignments': {
            'finance-tradingagents-sidecar': 'bad-role'
        },
    }
    resolved = resolve_tradingagents_role(roles_payload=payload)
    assert resolved['status'] == 'unsupported'
    assert resolved['unsupported_reason'] == 'unsupported_openclaw_alias_family:minimax-portal'


def test_resolve_tradingagents_role_rejects_missing_integration_metadata() -> None:
    payload = {
        'roles': {
            'bad-role': {
                'model': 'google-gemini-cli/gemini-3-flash-preview',
            }
        },
        'job_assignments': {
            'finance-tradingagents-sidecar': 'bad-role'
        },
    }
    resolved = resolve_tradingagents_role(roles_payload=payload)
    assert resolved['status'] == 'unsupported'
    assert resolved['unsupported_reason'] == 'missing_tradingagents_integration_metadata'


def test_resolved_tradingagents_config_returns_provider_native_shape() -> None:
    config = resolved_tradingagents_config()
    assert config['llm_provider'] == 'google'
    assert config['quick_think_llm'] == 'gemini-3-flash-preview'
    assert config['deep_think_llm'] == 'gemini-3.1-pro-preview'
    assert config['google_thinking_level'] == 'high'
