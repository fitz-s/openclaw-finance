# Announce Card Contract

The announce card is a deterministic **notification surface** compiled from the completed report envelope. It replaces the full report markdown as the Discord/cron channel delivery artifact.

## Purpose

Answer one question: *"Is this worth my attention right now?"*

The announce card is NOT the official record (that's the core report envelope). It is NOT the exploration surface (that's the reader bundle). It is an **attention router**.

## Schema

```json
{
  "card_id": "announce:<decision_id_short>",
  "generated_at": "ISO-8601",
  "report_ref": "<decision_id>",
  "reader_bundle_ref": "state/report-reader/<decision_id>.json",
  "core_report_path": "state/finance-decision-report-envelope.json",

  "attention_class": "deep_dive | review | skim | ops | ignore",
  "dominant_object": {
    "type": "thesis | opportunity | invalidator | scenario | system_steady_state",
    "id": "thesis:TSLA | opp:SMR | inv:0 | sc:tech_rally",
    "instrument": "TSLA",
    "label": "TSLA event_sensitive thesis"
  },
  "why_now": "one-liner string, ≤80 chars",
  "next_decision": "what the user should decide right now, ≤80 chars",
  "handles": ["R42", "T1", "O1", "I1"],

  "announce_markdown": "≤200 chars, the Discord message",
  "no_execution": true
}
```

## Attention Class Rules (deterministic, no LLM)

| Class | Condition |
|-------|-----------|
| `deep_dive` | Active wake dispatch + live invalidator hit_count ≥ 3 |
| `review` | thesis_delta with active thesis changes OR capital_delta with agenda items |
| `skim` | Fallback no_trade judgment, no new evidence |
| `ops` | Product validation or delivery safety failed |
| `ignore` | No state change from previous card |

## Dominant Object Rules

Priority order:
1. Capital agenda item with highest priority_score (if capital_delta)
2. Opportunity queue candidate with highest score
3. Invalidator with highest hit_count
4. Thesis with status change
5. `system_steady_state` if nothing changed

## Announce Markdown Format

```text
Finance｜{attention_class_label}
值得看：{dominant_object_summary}
为什么现在：{why_now}
你只要决定：{next_decision}
入口：{handles joined by /}
```

Total ≤ 200 characters. Chinese primary, English proper nouns per STYLE_GUIDE.md.

## Compatibility

- Must pass `report-posting-contract.json` `blockIfContains` filters
- Must NOT contain: UTC, raw paths, silent exit markers, shouldSend=false, HEARTBEAT_OK
- Title must use `Finance｜` prefix per existing posting contract `titleRules`
- `no_execution=true` always

## Authority

The announce card references but does not replace the core report. The core report chain (JudgmentEnvelope → render → validate → decision log → safety) remains canonical. The card compiler runs AFTER the full chain completes.
