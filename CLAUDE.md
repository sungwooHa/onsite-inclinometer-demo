# CLAUDE.md

*Always in effect — these take priority over everything else.*

## Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.
- State assumptions explicitly; ask when uncertain.
- Multiple interpretations? Present them all — don't silently pick one.
- Name a simpler approach when one exists; push back when warranted.
- When something is ambiguous, stop and say what's unclear.

## Simplicity First
Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for one-off code; no unrequested flexibility or config.
- No error handling for scenarios that can't happen.
- If 200 lines can be 50, rewrite it.

## Surgical Changes
Touch only what you must. Clean up only your own mess.
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor what works; match the existing style.
- Remove only the imports/variables your change orphaned.
- Every changed line traces back to the request.

## Goal-Driven Execution
Define success criteria. Loop until verified.
- Turn the task into a verifiable goal ("fix the bug" → "write a failing test, make it pass").
- State a short plan for multi-step work; each step has a check.
- Strong criteria enable independent looping; weak ones force constant clarification.

---
Everything else → [docs/INDEX.md](docs/INDEX.md)
