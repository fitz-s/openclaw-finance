# REPORT_TEMPLATE.md — Compatibility Stub

This file exists only for legacy OpenClaw BOOT/mainline audit scripts that still
hash or check the historical root-level `REPORT_TEMPLATE.md` path.

Active finance reporting no longer uses this template.

Current active path:
`ContextPacket -> WakeDecision -> JudgmentEnvelope -> finance_decision_report_render.py -> finance_report_product_validator.py -> finance_decision_log_compiler.py -> finance_report_delivery_safety.py -> Discord operator primary + thread seed`

Canonical current style/contract surfaces:
- `STYLE_GUIDE.md`
- `docs/openclaw-runtime/contracts/finance-report-contract.md`
- `state/finance-decision-report-envelope.json`

Historical v1 template is preserved at:
- `legacy/report-v1/REPORT_TEMPLATE.md`

Rules:
- Do not use this file to render active reports.
- Do not re-enable the deprecated `finance-report-renderer` from this file.
- Do not bypass product validation, decision log, or delivery safety.
- Do not output legacy phrases like `thresholds not met` as the user-visible report.
