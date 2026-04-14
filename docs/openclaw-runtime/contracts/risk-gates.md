# Risk Gates

Risk gates are deterministic and run after agent judgment.

## Required Checks

- Packet freshness.
- Evidence refs exist and are present in the packet.
- Packet hash matches the referenced packet.
- Policy version is supported.
- Model id is recorded for model-mediated output.
- Action is within policy.
- Action does not conflict with current position/risk budget.
- Live authority is false unless an explicit later packet grants it.

## Outcomes

- `accepted_for_log`
- `requires_operator_review`
- `rejected_stale_packet`
- `rejected_missing_refs`
- `rejected_policy_violation`
- `rejected_risk_conflict`
- `rejected_live_authority`

## Rules

- Failed validator output can be logged and reviewed, but cannot reach execution.
- Auto execution is out of scope until a separate approved execution adapter packet exists.
