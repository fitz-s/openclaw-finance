# Ingestion Fabric Phase 05 Implementation Critic

Verdict: APPROVE

Scope reviewed:
- `docs/openclaw-runtime/ralplan/ingestion-fabric-phase-05-brave-llm-context-reader-ralplan.md`
- `scripts/brave_llm_context_fetcher.py`
- `tests/test_brave_llm_context_phase05.py`

Checks:
- Reader is not wired into scanner cron, report delivery, wake policy, thresholds, or parent OpenClaw runtime.
- Reader blocks unscoped first-pass discovery packs; source scope must come from selected URLs, allowed domains, or Goggles.
- Request params enforce query length, count, URL, token, snippet, freshness, and threshold bounds.
- Total snippet ceiling is configurable to handle Brave docs/API-reference mismatch.
- Mocked LLM Context responses produce metadata-only context refs with URL/hostname/title/age/snippet_count/snippet_digest.
- Raw snippets and raw context bodies are not persisted.
- Local recall payloads are not merged into generic source refs and are recorded only as counts/metadata.
- Rate-limit errors become explicit metadata with application code, error class, retryability, and quota headers.
- Dry-run works without API key or network.

Risks:
- Live Brave API behavior is not exercised because tests use mocks and local quota is degraded.
- Goggles registration/hosted-file validation is not implemented yet; this phase only accepts/passes the field.
- API-version pinning is not implemented yet; add before production scheduling.
- LLM Context returns extracted content from Brave; keeping only digests protects repo artifacts but means downstream EvidenceAtom creation still needs a rights-aware source-reading policy.

Required follow-up:
- Phase 06 Brave Answers sidecar must stay citation-only and must not reuse this reader as answer authority.
- Before active use, add source-health/backoff handling for 402/429 and decide whether API version should be pinned.

Commit gate: pass.
