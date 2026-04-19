---
name: requirements-tribunal
description: Use when the user has a vague or overloaded product idea and needs rigorous requirement closure before implementation.
---

# Requirements Tribunal

## Purpose
Convert a fuzzy idea into a stable implementation handoff.

## When to use
Use this skill when:
- the request is broad, high-stakes, or underspecified
- the user asks for a “complete implementation” but the real task is still requirement closure
- architecture and scope are more important than immediately writing code

## Method
1. Reconstruct the real problem.
2. Ask one question at a time.
3. Separate:
   - Facts
   - Decisions
   - Open Questions
   - Risks
4. Find hidden branches:
   - missing constraints
   - integration boundaries
   - rollout / rollback concerns
   - what is explicitly out of scope
5. Stop only when you can emit:
   - `PROJECT_BRIEF.md`
   - `PRD.md`
   - `ARCHITECTURE.md`
   - `OPEN_QUESTIONS.md`
   - `RISKS.md`

## Output style
- concise
- high signal
- no generic encouragement
- do not jump into code prematurely

## Guardrails
- do not treat guesses as settled truth
- do not over-expand into speculative features
- do not replace the user’s goal with your favorite generic process
