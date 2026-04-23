# OpenClaw TradingAgents Model Resolution Contract

This contract defines how OpenClaw model policy is translated into TradingAgents provider-native configuration.

## Purpose

OpenClaw and TradingAgents use different model configuration shapes.

OpenClaw role policy provides:

- one runtime alias string in `roles[*].model`
- job-to-role assignment
- cost tier / role intent

TradingAgents requires:

- provider
- quick model
- deep model
- base URL
- provider-native optional settings
- auth source

This contract is the anti-corrosion layer between those systems.

## Source Of Truth

OpenClaw remains the source of truth for:

- role naming
- job assignment
- runtime alias policy

TradingAgents remains the source of truth for:

- provider-native client shape
- supported provider families
- provider-native model names

## Schema Extension

`workspace/ops/model-roles.json` may include:

```json
{
  "roles": {
    "<role-name>": {
      "model": "<openclaw-runtime-alias>",
      "integrations": {
        "tradingagents": {
          "enabled": true,
          "provider": "google|openai|anthropic|openrouter|ollama",
          "quick_model": "<provider-native-model>",
          "deep_model": "<provider-native-model>",
          "base_url": null,
          "auth_source": "GOOGLE_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|OPENROUTER_API_KEY|none",
          "google_thinking_level": null,
          "google_use_application_default_credentials": false,
          "google_vertexai": false,
          "google_location": null,
          "openai_reasoning_effort": null,
          "anthropic_effort": null,
          "resolution_contract_version": "v1"
        }
      }
    }
  }
}
```

## Required Rules

1. `roles[*].model` remains unchanged for OpenClaw runtime consumers.
2. `integrations.tradingagents` is optional.
3. Missing `integrations.tradingagents` means unsupported for TradingAgents resolution.
4. The resolver must fail closed on unsupported aliases or missing required fields.
5. The resolver must not read OpenClaw auth profiles or Codex auth files.
6. Runtime/auth reuse is explicitly out of scope for this contract version.
7. Google roles may enable Application Default Credentials through provider options without changing the runtime alias or report authority model.

## Alias Families

Supported initial OpenClaw alias families:

- `google-gemini-cli/*` -> provider `google`
- `openai-codex/*` -> provider `openai`
- `claude-max/*` -> provider `anthropic`

Explicitly unsupported in `v1`:

- `minimax-portal/*`

Unsupported means:

- no TradingAgents config is produced
- the sidecar request compiler must fail closed with an explicit reason

## Resolution Output

The finance-side resolver should emit:

```json
{
  "status": "supported|unsupported",
  "job_name": "finance-tradingagents-sidecar",
  "role_name": "finance-tradingagents",
  "openclaw_runtime_alias": "google-gemini-cli/gemini-3-flash-preview",
  "provider": "google",
  "quick_model": "gemini-3-flash-preview",
  "deep_model": "gemini-3.1-pro-preview",
  "base_url": null,
  "auth_source": "GOOGLE_API_KEY",
  "provider_options": {
    "google_thinking_level": "high",
    "google_use_application_default_credentials": true,
    "google_vertexai": true,
    "google_location": "global"
  },
  "unsupported_reason": null,
  "resolution_contract_version": "v1"
}
```

## Non-Goals

- Do not infer provider credentials from OpenClaw auth internals.
- Do not pass `payload.model` straight into TradingAgents clients.
- Do not modify TradingAgents provider clients to accept OpenClaw aliases directly.
- Do not alter report, wake, judgment, or delivery authority.

## Rollback

Rollback is simple:

- remove the integration metadata block
- keep the OpenClaw runtime alias untouched
- revert finance-side resolver usage

That must not affect ordinary OpenClaw job execution.
