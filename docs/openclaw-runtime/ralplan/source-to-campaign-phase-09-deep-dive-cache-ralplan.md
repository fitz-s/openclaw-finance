# RALPLAN Source-to-Campaign Phase 09: Deep-Dive Cache

Status: approved_for_implementation
Go for implementation: true

## Task Statement

Upgrade campaign deep-dive cache so top campaigns have pre-baked why/challenge/compare/scenario/sources/trace/expand cards with evidence groups, grounding counts, and insufficient-data status before the user asks in Discord.

This phase stays finance-local and does not change parent Discord routing.

## Principles

1. Cache should prepare committee context, not decorate prose.
2. Each verb card must state required evidence groups and grounding refs.
3. Missing compare/scenario context should be marked insufficient_data.
4. Thread seed should include prepared deep-dive content, not only starter verbs.
5. Review-only; no execution language.

## Decision Drivers

1. The review says thread follow-up should be anticipatory and verb-specific.
2. Phase 08 now defines evidence groups and coverage semantics.
3. User explicitly complained thread should already have more detailed content.

## Selected Plan

- Enrich `finance_campaign_cache_builder.py` cards with evidence groups, grounding summary, answer status, and refresh policy.
- Add pre-baked deep-dive summary to campaign thread seed.
- Add tests for all verb cards and thread seed content.

## Acceptance Criteria

- Cache includes every verb for top campaigns.
- Verb cards include `required_evidence_groups`, `grounding_summary`, and `answer_status`.
- Compare/scenario cards can mark `insufficient_data` when slices are empty.
- Thread seed includes `预备深挖` content.

## Test Plan

- `test_campaign_cache_builds_all_verb_cards_for_top_campaigns`
- `test_campaign_cache_marks_missing_compare_as_insufficient_data`
- `test_thread_seed_includes_prebaked_deep_dive_entries`

## Critic Review

Deferred to `docs/openclaw-runtime/critics/source-to-campaign-phase-09-implementation-critic.md` after implementation.
