# Finance Report Template Deprecated

This file is no longer the active finance report renderer contract.

Active user-visible flow:

```text
OpenClaw cron `finance-premarket-brief`
  -> read typed ContextPacket / WakeDecision
  -> write or validate JudgmentEnvelope
  -> finance_decision_report_render.py
  -> finance_report_product_validator.py
  -> finance_decision_log_compiler.py
  -> finance_report_delivery_safety.py
  -> final markdown from finance-decision-report-envelope.json
  -> OpenClaw announce delivery
```

`report-input-packet.json` is only a deprecated compatibility view. It must not be used as the cognition source for a new report.

Authoritative contracts:

- `systems/finance-openclaw-runtime-contract.md`
- `systems/finance-report-contract.md`
- `systems/finance-gate-taxonomy.md`
- `schemas/packet.schema.json`
- `schemas/judgment-envelope.schema.json`
- `schemas/validator-result.schema.json`
- `schemas/decision-log.schema.json`

Deprecated surfaces that must not become active delivery:

- `finance-report-renderer`
- `native_premarket_brief_live.py --deliver`
- `finance_deterministic_report_render.py`
- `finance_report_validator.py`
- `quality_gate.py`

If any job or prompt treats this file as an active template, run:

```bash
/opt/homebrew/bin/python3 /Users/leofitz/.openclaw/workspace/ops/scripts/finance_openclaw_embedded_audit.py
```
