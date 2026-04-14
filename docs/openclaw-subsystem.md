# Finance OpenClaw Subsystem

This repository is the finance subsystem embedded inside the local OpenClaw runtime.

It is not a standalone trading bot and it is not a generic Python script treadmill. The live system is driven by OpenClaw cron jobs and deterministic feeder scripts:

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

## Runtime Boundaries

- OpenClaw owns scheduling, isolated report turns, and user-visible delivery.
- Finance scripts own deterministic data collection, normalization, packet compilation, validation, and audit artifacts.
- `state/` contains live runtime artifacts and is intentionally not committed.
- `docs/openclaw-runtime/` contains sanitized snapshots exported from the live OpenClaw workspace so GitHub reviewers can inspect the runtime wiring.

## Watchlist Semantics

The active universe is `state/watchlist-resolved.json`, not the pinned fallback file.

The resolved watchlist is built from:

- IBKR Client Portal watchlists, when the local Client Portal session is authenticated.
- IBKR Flex holdings and option underlyings, as unattended fallback.
- `watchlists/core.json`, as local pinned fallback only.

IBKR Flex does not expose the IBKR UI watchlist. Flex is a statement/reporting source; Client Portal Web API is the watchlist source.

## Safety

All user-visible market reports must pass:

- `judgment_envelope_gate.py`
- `finance_report_product_validator.py`
- `finance_decision_log_compiler.py`
- `finance_report_delivery_safety.py`

The subsystem is review-only. No script in this repository may place trades or connect directly to an execution adapter without a separate risk-gate integration.
