---
name: handoff-packager
description: Use when the requirements and architecture are settled enough to create a durable handoff bundle for downstream coding agents.
---

# Handoff Packager

## Purpose
Emit a zip-ready project handoff with stable truth surfaces.

## Required contents
- brief
- PRD
- architecture
- decisions
- implementation plan
- task packet
- verification plan
- AGENTS guidance
- prompts
- references
- not-now list

## Method
1. Verify that requirements are sufficiently closed.
2. Ensure each document has a clear role and no conflicting truth surface.
3. Remove stale drafts or clearly mark them as non-canonical.
4. Package only the artifacts that a downstream coding agent must read.
5. Include verification commands and rollback notes.

## Success condition
A downstream agent can unzip the bundle and continue work without needing the original conversation.
