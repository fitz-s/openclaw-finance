# RALPLAN Ingestion Fabric Phase 12: Parent Market-Ingest Handoff

Status: implemented_after_external_scout
Go for implementation: true
Terminal state: implementation_ready_for_commit

## Task Statement

Prepare parent-side changes without silently modifying the parent OpenClaw authority chain. This phase produces handoff documentation, a machine-readable handoff contract, and tests only.

## RALPLAN-DR Summary

### External Scout Inputs

Source class: API/contract compatibility, rollout gates, feature flags, protected ownership, and rollback practices.

Integrated findings:
- Publish handoff as an explicit contract, not an informal dependency.
- Treat compatibility as default; breaking changes require new version and migration window.
- Run old/new paths side by side before cutover.
- Gate promotion on readiness/health/rollout verification.
- Keep rollback and kill switches available.
- Parent owns runtime authority, deploy credentials, and merge/deploy approval.

Reference links from scout:
- OpenAPI specification: https://spec.openapis.org/oas/
- Pact contract testing: https://docs.pact.io/
- Google AIP-180 compatibility: https://google.aip.dev/180
- Kubernetes readiness/deployments: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
- Feature flags: https://learn.microsoft.com/en-us/dotnet/architecture/cloud-native/feature-flags
- GitHub CODEOWNERS/protected branches: https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners

### Principles

1. Finance repo proposes artifacts; parent runtime owns activation.
2. Contracts before mutation.
3. Feature flags default off.
4. Rollback is prebuilt, not a future task.
5. Complete readable Discord report fallback must survive every parent failure.

## Selected Design

Add:
- `docs/openclaw-runtime/parent-ingestion-handoff.md`
- `docs/openclaw-runtime/parent-ingestion-handoff-contract.json`
- `tests/test_ingestion_fabric_phase12_parent_handoff.py`

No parent files are edited.

## Acceptance Criteria

1. Parent files are mapped.
2. Blast radius and rollback are documented.
3. Machine-readable contract lists producer artifacts, parent consumers, feature flags, gates, and rollback.
4. Tests enforce no parent mutation authority and route-card-only rollback ban.

## Non-Goals

- Do not edit parent workspace.
- Do not restart OpenClaw runtime.
- Do not enable flags.
- Do not mutate wake, packet, Discord, or judgment behavior.

## Critic Requirements

Critic must verify parent authority boundary, compatibility policy, default-off flags, and rollback path.
