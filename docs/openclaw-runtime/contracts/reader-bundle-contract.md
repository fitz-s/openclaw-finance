# Reader Bundle Contract

The reader bundle is the **exploration surface** — a self-contained rehydration artifact compiled after the report chain completes. It is consumed when the user wants to deep-dive into a specific object from the announce card.

## Purpose

Convert the internal object graph into navigable handles with starter questions. The bundle is the **memory**, not the thread. Every follow-up answer reconstructs context from the immutable bundle, never from raw conversation history.

## Schema

```json
{
  "bundle_id": "rb:<decision_id>",
  "decision_id": "...",
  "report_hash": "sha256:...",
  "generated_at": "ISO-8601",

  "handles": {
    "R42": {"type": "report", "ref": "..."},
    "T1":  {"type": "thesis", "ref": "thesis:TSLA", "instrument": "TSLA"},
    "O1":  {"type": "opportunity", "ref": "opp:SMR", "instrument": "SMR"},
    "I1":  {"type": "invalidator", "ref": "inv:0", "description": "..."},
    "S1":  {"type": "scenario", "ref": "sc:tech_rally", "title": "..."}
  },

  "object_cards": [...],
  "starter_questions": [...],
  "portfolio_attachment": {...},
  "capital_summary": {...}
}
```

## Handle Assignment (deterministic)

- `R<n>`: report decision_id short hash (stable per report)
- `T<n>`: theses sorted by (status=active first, then instrument alphabetical), 1-indexed
- `O<n>`: opportunities sorted by score descending, 1-indexed
- `I<n>`: invalidators sorted by hit_count descending, 1-indexed
- `S<n>`: scenarios sorted by title alphabetical, 1-indexed

Same inputs → same handles. Handles are stable within a report cycle, not across cycles.

## Object Card Schema

```json
{
  "handle": "T1",
  "type": "thesis",
  "instrument": "TSLA",
  "status": "active",
  "roles": ["event_sensitive"],
  "bucket_ref": "event_driven",
  "why_now": "...",
  "required_confirmations": ["..."],
  "invalidators": ["I1"],
  "evidence_snapshot": ["ev:1", "ev:2"],
  "price": "$265.30",
  "change_pct": "-1.2%"
}
```

## Starter Questions

Each starter question maps to an interrogation verb:
- `trace`: evidence chain, no editorializing
- `challenge`: countercase + invalidators + required confirmations
- `compare`: overlap + opportunity cost + portfolio relevance
- `scenario`: trigger + transmission + impacted objects + what changes

## Inputs

The bundle reads from completed pipeline artifacts only:
- `finance-decision-report-envelope.json`
- `finance-decision-log-report.json`
- `thesis-registry.json`, `watch-intent.json`
- `scenario-cards.json`, `opportunity-queue.json`, `invalidator-ledger.json`
- `capital-agenda.json`, `capital-graph.json`, `displacement-cases.json`
- `thesis-dossiers/*.json`, `custom-metrics/*.json` (optional)
- `prices.json`, `portfolio-resolved.json`

## Authority

The reader bundle is a derived view. It does not replace the core report envelope or decision log as canonical state. It carries `no_execution=true`.
