# Finance Workflow (OpenClaw Embedded)

## Active Architecture

```text
OpenClaw scanner cron
  -> buffer observations
  -> deterministic worker/gate
  -> typed evidence + ContextPacket
  -> WakeDecision
  -> OpenClaw report orchestrator
  -> JudgmentEnvelope
  -> product report validator
  -> decision log
  -> delivery safety gate
  -> Discord announce
```

The scanner/gate layer decides whether there is enough signal to request a report. It is not the final report renderer.

## Modes

### Continuous Scan

- Runs through OpenClaw cron.
- Reads `watchlist-resolved.json`, portfolio quality state, prices, option risk, event watchers, and scanner state.
- Writes bounded observations into `finance/buffer/`.
- Runs `finance_worker.py` and `gate_evaluator.py` by absolute path.

### Threshold / Wake Dispatch

- `gate_evaluator.py` updates `report-gate-state.json`.
- The typed wake pipeline updates `latest-context-packet.json`, `latest-wake-decision.json`, and `wake-dispatch-state.json`.
- If canonical wake dispatch is not sufficient but legacy intraday thresholds pass, `gate_evaluator.py` bridges to the active OpenClaw report orchestrator, not the deprecated renderer.
- `report-input-packet.json` is refreshed only as a compatibility view.

### Report Orchestration

`finance-premarket-brief` is the active report job even for event-driven reports. The title and content must reflect the event/window; it is not allowed to produce a stale "盘前/开盘" label during mid/late/post sessions.

The job must:

- Read typed packet and wake state.
- Produce or validate `judgment-envelope.json`.
- Run product validation.
- Compile the decision log.
- Run delivery safety.
- Output only the markdown stored in `finance-decision-report-envelope.json` when safety passes.

### Learning / Replay

The weekly learning job reads replay, decision log, product validation, and judgment validation outputs. It can recommend changes to policy/schema/tests/prompts/model routing, but it must not automatically change thresholds or issue trading instructions.

## Deprecated Path

The old `scan -> gate -> renderer -> quality_gate` wording is historical. The `finance-report-renderer` cron is disabled/manual-only and direct delivery from local Python scripts is blocked.
