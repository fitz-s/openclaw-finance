# Legacy Report v1 Archive

This directory contains deprecated Finance Report v1 surfaces.

They are kept only for historical context, regression archaeology, or migration reference. They are not active OpenClaw Finance runtime authority.

Active user-visible reporting is:

```text
ContextPacket / WakeDecision
-> JudgmentEnvelope
-> finance_decision_report_render.py
-> finance_report_product_validator.py
-> finance_decision_log_compiler.py
-> finance_report_delivery_safety.py
```

Do not wire files from this directory into OpenClaw cron jobs or user-visible delivery.

Archived surfaces:

- `REPORT_TEMPLATE.md`
- `prompts/report-renderer.md`
- `scripts/finance_deterministic_report_render.py`
- `scripts/finance_report_validator.py`
- `scripts/quality_gate.py`
- `scripts/native_premarket_brief.py`
- `scripts/native_premarket_brief_live.py`
- `scripts/finance_llm_report_render.py`
