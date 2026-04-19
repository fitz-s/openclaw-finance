# Offhours Intelligence P2 External Scout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

## External Sources Checked

- Brave LLM Context API documentation: https://api-dashboard.search.brave.com/documentation/services/llm-context
- Brave Answers API documentation: https://api-dashboard.search.brave.com/documentation/services/answers
- Brave pricing/rate-limit documentation: https://api-dashboard.search.brave.com/documentation/pricing

The official docs were reachable during P2 scout.

## Findings For P2

- LLM Context should be treated as selected-source reading/compression after source discovery, not first-pass discovery.
- Answers should be treated as citation-gated sidecar synthesis only. Answer prose is derived context, not canonical evidence.
- Answers and LLM Context must have separate budget kinds from Search; using Search budget for compression would hide quota burn.
- P2 should default compression activation to dry-run unless explicitly enabled, because rate-limit state already shows Brave live calls are constrained.

## P2 Design Consequence

Do not fold LLM Context/Answers into Web/News activation directly. Add a separate compression activation lane that consumes seed URLs/handles and writes explicit budget decisions.
