# Finance Operating Model

This repository is not an app, terminal, standalone trading bot, or direct execution lane. It is an OpenClaw-embedded finance subsystem.

## Problem Statement

The core operating problem is not missing features. It is keeping one adjudicable operating model across OpenClaw cron, typed packet/wake/judgment artifacts, deterministic validators, delivery safety, docs, and GitHub-visible runtime snapshots.

Success means:

- one active user-visible path
- personalization from `watchlist-resolved.json`, portfolio state, invalidators, and typed evidence
- wake routing before judgment
- deterministic product/risk/safety gates after judgment
- compatibility surfaces marked as compatibility
- deprecated surfaces unable to become active delivery
- GitHub reviewers able to inspect runtime wiring snapshots

Failure means:

- scripts, docs, cron payloads, and snapshots describe different active paths
- reports bypass JudgmentEnvelope -> product validator -> decision log -> delivery safety
- benchmarks turn this repository into a standalone app or execution system
- GitHub CI green is mistaken for live OpenClaw runtime health

## Authority Order

Authority is domain-specific:

1. **Live entrypoint authority**: active OpenClaw cron payloads plus machine truth surfaces.
2. **Semantic authority**: `systems/` contracts for wake, judgment, report, risk, and safety semantics.
3. **Implementation authority**: deterministic Python scripts that transform, validate, log, or audit.
4. **Doctrine authority**: repository docs that explain boundaries and reviewer workflow.
5. **Compatibility authority**: old mirrors such as `report-input-packet.json`, only while explicitly marked compatibility-only.
6. **Deprecated authority**: disabled/manual renderers, old templates, and direct delivery scripts have no active delivery authority.
7. **Prompt authority**: prompts are phrasing shells and cannot bypass product validation or delivery safety.

## Active Path

```text
OpenClaw finance scanner cron
  -> finance/buffer observations
  -> finance_worker.py
  -> gate_evaluator.py
  -> typed EvidenceRecord / ContextPacket / WakeDecision
  -> OpenClaw finance report orchestrator
  -> JudgmentEnvelope
  -> product report validator
  -> decision log
  -> delivery safety gate
  -> OpenClaw Discord announce
```

## Compatibility And Deprecated Surfaces

`state/report-input-packet.json` is a compatibility mirror, not the active cognition substrate. It exists to keep old consumers from seeing stale state while the active path remains typed-decision.

Deprecated/manual-only surfaces include:

- `finance-report-renderer`
- `legacy/report-v1/REPORT_TEMPLATE.md` as active template
- `legacy/report-v1/scripts/native_premarket_brief_live.py --deliver`
- `legacy/report-v1/scripts/finance_deterministic_report_render.py`
- `legacy/report-v1/scripts/finance_report_validator.py`
- `legacy/report-v1/scripts/quality_gate.py`

They may exist for evidence, regression, or migration reference. They must not own active delivery.

## Load-Bearing Branches

### Personalization

Personalization comes from:

- `watchlist-resolved.json`
- portfolio / option-risk state
- invalidators
- typed evidence refs

Generic market chatter is not a substitute for this layer.

### Wake Precision

Wake is bounded routing. It is not prose summarization and not execution. It must classify updates before judgment and before report delivery.

### Review-Only Safety

The subsystem cannot execute trades. Execution-adjacent words in JudgmentEnvelope remain review artifacts until a separately approved execution adapter changes the risk contract.

### Runtime Visibility

GitHub-hosted CI cannot see local `~/.openclaw` runtime state. Reviewer visibility depends on `docs/openclaw-runtime/` snapshots exported from the running machine.

### Parent Workspace Dependency

Canonical packet compilation and wake policy are currently parent-workspace runtime surfaces, not fully owned by this repository. This repo must reflect that dependency instead of pretending to be standalone.

## Benchmark Boundary

Benchmarks are source material for local patterns, not product templates:

- Magnifi-style linked-account investing is out of scope unless an approved advisory/execution surface exists.
- OpenBB-style workspaces/widgets/apps are out of scope unless they remain outside user-visible delivery authority.
- FinRobot-style multi-agent trading is out of scope for the hot path.
- Fiscal.ai-style terminal/API/dashboard/notifications are out of scope unless reduced to OpenClaw-compatible evidence or alert inputs.
- Chat/code-execution financial assistants are out of scope as a product template.

Adoptable benchmark patterns must preserve this subsystem's authority order.
