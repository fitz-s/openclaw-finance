# Offhours Intelligence P2 Internal Explorer

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## Explorer Summary

A read-only internal explorer mapped the current Brave compression path.

Current state:

- `brave_llm_context_fetcher.py` already blocks unscoped reader queries and preserves metadata/digests only.
- `brave_answers_sidecar.py` already requires `authority_level=sidecar_only`, parses citations, and marks answer text as non-canonical evidence.
- `source_health_monitor.py` already reads LLM Context and Answers records.
- `brave_budget_guard.py` already supports separate `answers` and `llm_context` counters.
- No integrated activation path currently schedules LLM Context/Answers from offhours routing.
- Current activation budget enforcement is Search-only.

Recommended implementation:

- Add a separate `brave_compression_activation.py` runner.
- Feed it selected URLs from existing Web/News records and planned QueryPacks.
- Check `llm_context` budget before LLM Context calls.
- Check `answers` budget before Answers sidecar calls.
- Default to dry-run and keep output sidecar-only.
- Wire parent offhours dry-run path to include the compression activation report.
