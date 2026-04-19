# Ingestion Fabric Phase 02 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/ingestion-fabric-phase-02-brave-api-audit-ralplan.md`
- `tools/export_brave_api_capability_audit.py`
- `docs/openclaw-runtime/brave-api-capability-audit.json`
- `tests/test_brave_api_capability_audit_phase02.py`

Checks:
- Audit detects current configured Brave mode as `llm-context`.
- Audit reports implemented OpenClaw endpoints: `brave/web/search` and `brave/llm/context`.
- Audit reports missing endpoints: `brave/news/search` and `brave/answers/chat_completions`.
- Audit integrates external scout findings from official Brave Web, News, LLM Context, Answers, pricing, and terms docs.
- Audit records the important mismatch: official LLM Context supports freshness, but current OpenClaw `llm-context` abstraction rejects freshness/date filters.
- Audit records Brave 402 quota failures from gateway logs without exporting API keys.
- Audit records rights/storage boundary: no committed long-lived raw Brave Search Results database; committed artifacts must stay sanitized.
- Audit keeps Brave Answers as `sidecar_synthesis_only`; citation URLs can seed EvidenceAtom candidates, answer prose cannot become canonical evidence.
- Phase is documentation/audit only and does not change source ingestion behavior.

Risks:
- Audit reads installed OpenClaw dist paths; if OpenClaw updates, endpoint detection should be rerun.
- Quota failures are log-derived, not live API billing state.
- Brave pricing/rate-limit details are time-sensitive; fetcher implementation must re-check official docs before activation.
- Future SourceFetchRecord design must reconcile point-in-time replay needs with Brave Search Result storage restrictions.

Required follow-up:
- Phase 03 should implement query registry/lane watermarks/source memory before adding Brave fetchers.
- Phase 04 fetchers must include rate-limit handling, no raw-result commit policy, and News/Web lane separation.

Commit gate: pass.
