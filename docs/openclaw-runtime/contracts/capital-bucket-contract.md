# Capital Bucket Contract

`CapitalBucket` defines the scarce capital competition grammar for OpenClaw Finance.

Buckets are not position sizes and not execution plans. They are review-only attention budget categories that make capital scarcity explicit in the system.

## Default Buckets

- `core_compounders`: long-term growth holdings with compounding thesis.
- `cyclical_beta`: positions with cyclical/commodity/rate exposure.
- `macro_hedges`: positions or theses that hedge portfolio-level risk factors.
- `event_driven`: event-sensitive theses without existing held exposure.
- `speculative_optionality`: curiosity-driven, unknown-discovery, and high-uncertainty candidates.

## Configuration

Bucket definitions are user-configurable via `state/capital-bucket-config.json`.

Required fields per bucket:

- `bucket_id`
- `label`
- `description`
- `max_thesis_slots`: attention budget cap for this bucket.
- `role_mapping`: which WatchIntent roles map to this bucket.

Default configuration is provided. Missing config falls back to hardcoded defaults.

## Computed Fields

The capital graph compiler populates these fields per bucket at compile time:

- `current_thesis_refs`: list of thesis IDs assigned to this bucket.
- `current_position_refs`: list of position symbols in this bucket.
- `utilization`: `len(current_thesis_refs) / max_thesis_slots`.
- `hedge_coverage_status`: `covered` | `partial` | `uncovered` | `not_applicable`.

## Assignment Rule

Each thesis is assigned to exactly one bucket. Assignment is deterministic:

1. `held_core` + growth instrument -> `core_compounders`
2. `held_core` + cyclical/commodity -> `cyclical_beta`
3. `hedge` / `macro_proxy` -> `macro_hedges`
4. `event_sensitive` without `held_core` -> `event_driven`
5. `curiosity` / unknown_discovery -> `speculative_optionality`
6. Fallback: `speculative_optionality`

## Runtime Boundary

`CapitalBucket` is a review-only classification. It must not encode trade instructions, target position sizes, or execution commands. Bucket utilization warnings are analysis artifacts, not execution triggers.

## Fallback Rule

Missing or invalid `capital-bucket-config.json` must fall back to hardcoded default buckets. Missing bucket configuration must never block delivery.
