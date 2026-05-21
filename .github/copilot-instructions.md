# Copilot Instructions — Council of Mikes

> This file is read automatically by GitHub Copilot for every chat in this repository. It also doubles as a paste-ready integration block for any workspace that adopts the Council.

## Repository Purpose

This repo defines **15 AI expert personas** (the Council) plus an **11-phase Pre-Submit Quality Gate** enforced by the Gatekeeper. Treat every Council member skill (`council/the-*/SKILL.md`) as authoritative for its domain.

## When Routing User Requests

Before generating an answer, check whether the user is invoking the Council:

- `@TheCouncil`, `@Council`, `the council` → consult `council/council.md` to pick the right member
- `@TheCouncil use pre-submit skill` / `@TheGatekeeper ...` → load `council/the-gatekeeper/SKILL.md` and run the full 11-phase gate from `procedures/code-change-pre-submit-sop.md`
- `@The<Member> ...` (e.g., `@ThePurifier`, `@TheProver`, `@TheArchitect`) → load `council/<member>/SKILL.md` and follow its protocol

Full routing table and resolution order: see `AGENTS.md` and `prompts/council-routing.snippet.md`.

## Hard Rules

1. **Never** declare "done", "shipping", or "ready to PR" without a Gatekeeper Report ending in `Verdict: READY`.
2. **Always** run Phase 8 (diff-vs-behavior) as a reading exercise, not a test run.
3. **Always** run Phase 10 (Copilot PR-review simulation) as a hostile reviewer.
4. **Always** update documentation in Phase 11 or state explicitly "no doc surface affected" with reasoning.
5. **Tool names that are public OSS** (Testcontainers, Mockoon, SonarQube, xUnit, Moq, etc.) are fine in this repo. **Employer/customer-specific names, internal hostnames, or proprietary identifiers are not** — keep this repo public-safe.

## Auto-Fail Anti-Rationalizations

If you catch yourself thinking any of these, **STOP** and re-run the gate:

- "Tests passed, shipping"
- "Only changed one line"
- "Failing test was unrelated"
- "Copilot's PR review will catch it"
- "Disabled the analyzer, was noisy"
- "Docs are out of date anyway"
- "I'll update README later"

## Slash Commands

- `/pre-submit` — runs the 11-phase Pre-Submit Gate on pasted content (see `prompts/pre-submit.prompt.md`).

## Cross-References

- Full agent guide: `AGENTS.md`
- Member roster: `README.md`
- Pre-Submit SOP: `procedures/code-change-pre-submit-sop.md`
- Routing snippet (drop-in for other repos): `prompts/council-routing.snippet.md`
- Companion workspace-orchestration repo: [MemoryForge](https://github.com/underwms/MemoryForge)
