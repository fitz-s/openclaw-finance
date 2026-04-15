# Displacement Case Contract

`DisplacementCase` is the comparative justification required when an opportunity candidate would overlap, conflict with, or displace existing exposure in the capital graph.

## Purpose

Without displacement analysis, the opportunity queue grows without bound — every good story gets added but nothing is compared against the existing book. `DisplacementCase` forces the system to answer: "what does this candidate replace, compete with, or improve?"

## Core Fields

- `case_id`
- `candidate_thesis_ref`: the opportunity/thesis being evaluated.
- `displaced_thesis_ref`: the existing thesis that would be displaced or affected.
- `bucket_ref`: the CapitalBucket where competition occurs.
- `overlap_type`: `instrument_overlap` | `factor_overlap` | `scenario_dependency` | `bucket_crowding` | `hedge_conflict`.
- `exposure_delta`: qualitative assessment of net exposure change.
- `hedge_gap_impact`: `improves` | `neutral` | `worsens`.
- `scenario_sensitivity_change`: which scenarios become more/less covered.
- `justification`: deterministic compiler explanation of why this case was generated.
- `no_execution`: must always be `true`.

## Generation Rule

`DisplacementCase` is generated only when the capital graph detects:

- Instrument overlap between candidate and existing thesis.
- Factor overlap (shared sector, rate sensitivity, commodity dependency).
- Bucket crowding (bucket utilization exceeds threshold).
- Scenario dependency conflict.
- Hedge coverage change.

`DisplacementCase` must never be generated indiscriminately for all candidates. The system must be specific about which overlap triggered the case.

## Selective Emission Rule

If no overlap, conflict, or gap exists for a candidate, no `DisplacementCase` is emitted. The candidate proceeds as a standard opportunity without displacement analysis.

## Runtime Boundary

`DisplacementCase` is a review-only analysis artifact. It explains trade-offs but does not recommend, execute, or authorize any portfolio action. `no_execution` must always be `true`.
