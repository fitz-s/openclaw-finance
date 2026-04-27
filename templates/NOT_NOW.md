# NOT_NOW

These are explicitly out of scope for the current handoff foundation:
- Replacing the existing root `AGENTS.md` with the generic starter-kit AGENTS.
- Copying starter-kit `src/` or placeholder `tests/` over existing finance source/tests.
- Changing report/scanner cron behavior, Discord delivery, wake thresholds, broker authority, or source activation.
- Packaging raw `state/`, raw Flex XML, secrets, broker account IDs, or licensed/vendor payloads into the handoff zip.
- Creating or configuring ChatGPT GitHub connector permissions from this repo.
- Opening a PR automatically.

Reason:
This package is a guidance/handoff exoskeleton for an existing live subsystem. It must improve future agent handoff quality without changing runtime behavior or exposing sensitive data.
