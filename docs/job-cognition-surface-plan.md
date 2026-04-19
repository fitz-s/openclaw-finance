# Finance Job Cognition Surface Plan

Package: 9
Status: implementation contract

## Purpose

Finance jobs should give the LLM a compact role-specific cognition surface instead of making it hunt through many state files.

The new `llm-job-context/*.json` files are ephemeral views. They are not canonical state and must not become a second packet layer.

Canonical authority remains:

```text
ContextPacket -> WakeDecision -> JudgmentEnvelope -> product report -> decision log -> delivery safety
```

## Job Role Map

| Job | LLM role | Context pack | Allowed output | Forbidden |
| --- | --- | --- | --- | --- |
| `finance-subagent-scanner` | Find object-linked evidence candidates during market hours | `state/llm-job-context/scanner.json` | buffer JSON observations only | user messages, delivery, held/watchlist-as-unknown |
| `finance-subagent-scanner-offhours` | Find overnight object-linked evidence candidates | `state/llm-job-context/scanner.json` | buffer JSON observations only | user messages, delivery, stale watchlist substitution |
| `finance-premarket-brief` | Run deterministic report closure and print only the final operator surface | internal call from `finance_discord_report_job.py` | stdout: `NO_REPLY`, health-only markdown, or validated operator report | LLM progress text, report prose before safety, invented facts, execution |
| `finance-thesis-sidecar` | Run bounded research artifact flow | `state/llm-job-context/thesis-sidecar.json` | typed dossiers/scenario/custom metric artifacts | Discord, threshold mutation, execution |
| `finance-weekly-learning-review` | Review telemetry and recommend system improvements | `state/llm-job-context/weekly-learning.json` | Fact / Interpretation / Recommendation | market advice, automatic threshold mutation |

## Context Pack Contract

Every context pack must include:

- `pack_id`
- `pack_role`
- `generated_at`
- `pack_is_not_authority: true`
- `canonical_authority`
- `source_artifacts[]` with path, mtime, hash, and required flag
- `allowed_outputs[]`
- `forbidden_actions[]`
- object refs where relevant

Every summary row must have one of:

- a stable object ID
- a source artifact path/hash
- an evidence ref copied from the typed packet

The pack may summarize existing typed artifacts, but it must not create independent market conclusions.

## Prompt Contract

Finance cron prompts that ask an LLM to reason over finance state must be context-pack-first:

1. Run `finance_llm_context_pack.py`.
2. Read the role-specific context pack.
3. Perform only the bounded LLM role.
4. Run deterministic closure scripts.
5. Let validators and delivery safety decide what can be shown.

Prompt drift tests must fail if:

- scanner/sidecar/weekly cognition jobs stop referencing `llm-job-context`
- the user-visible premarket report job stops using `finance_discord_report_job.py`
- the user-visible premarket report job permits progress text or a free-form LLM orchestrator prompt
- scanner prompts allow held/watchlist symbols to satisfy unknown discovery
- sidecar delivery is enabled
- weekly learning permits automatic threshold mutation

The user-visible premarket report is intentionally not an LLM orchestrator prompt. It must run the deterministic stdout wrapper so intermediate text such as "Now running..." can never enter Discord.
