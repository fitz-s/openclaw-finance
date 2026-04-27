# PROJECT_BRIEF

## Project name
OpenClaw Finance AI Handoff Foundation

## One-sentence objective
Add a durable handoff/documentation exoskeleton to the existing OpenClaw Finance repo so future Claude Code / Codex / ChatGPT Pro work starts from locked repo reality, invariants, implementation stages, and verification surfaces.

## User / operator
Primary operator: Fitz, using Discord as the main finance consumption surface and this repo as the canonical implementation/audit surface.

## Core problem
The finance repo has accumulated a large, safety-sensitive runtime: calendar-aware offhours scanning, report delivery, campaign boards, Brave/SEC source lanes, and parent OpenClaw cron integration. Future AI agents need a stable handoff layer that prevents drift between intent, architecture, implementation, and verification.

## Why now
Recent work completed P0-P9 of the Calendar-Aware Offhours Intelligence Fabric and marketday delivery hardening. The next risk is not missing code, but future agents misunderstanding the current truth surface, regressing authority boundaries, or applying generic starter-kit assumptions to a live OpenClaw-embedded finance subsystem.

## Success criteria
- The starter-kit docs/prompts/templates/skills/scripts are integrated without overwriting existing finance source or current AGENTS authority.
- Finance-specific PROJECT_BRIEF / PRD / ARCHITECTURE / IMPLEMENTATION_PLAN / TASK_PACKET / VERIFICATION_PLAN / DECISIONS / NOT_NOW / RISKS / OPEN_QUESTIONS are populated from current repo reality.
- A handoff zip can be generated from the real repo and used as a stable context bundle without pretending it is a full source snapshot.
- Existing finance tests and audits still pass.

## Non-goals
- Do not replace the existing OpenClaw Finance `AGENTS.md` contract with the generic starter-kit AGENTS file.
- Do not copy starter-kit `src/` or placeholder `tests/` over existing repo directories.
- Do not change finance runtime behavior, cron jobs, Discord delivery, wake thresholds, broker/session authority, source activation policy, or report surfaces in this package.

## Hard constraints
- Review-only finance boundary remains intact: no trade execution, broker mutation, threshold mutation, or live authority change.
- Parent OpenClaw runtime changes affecting finance must be mirrored into `docs/openclaw-runtime/` before commit.
- Medium/large changes must include impact summary, touched files, invariants, verification, and rollback notes.
- Handoff zip is documentation/guidance context, not a full repository snapshot.

## Open questions
- Should the handoff zip be generated on every major phase closeout, or only before external reviewer/agent handoff?
- Should future handoff bundles include sanitized reviewer packets by default, or only docs/prompts/templates/skills?

## Initial risk notes
- Generic starter-kit AGENTS guidance could conflict with existing OpenClaw-specific AGENTS rules if blindly copied.
- Handoff docs can drift unless future agents update them alongside architecture/runtime changes.
