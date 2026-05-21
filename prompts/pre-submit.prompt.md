---
applyTo: '**'
description: 'Run The Council pre-submit gate (11-phase) on a change before declaring it done'
---

# Pre-Submit (Council Gatekeeper)

Run the full 11-phase Pre-Submit Gate on the change described below. The Gatekeeper is the final voice — do not push, open a PR, or report "done" until every phase is ✅ (or explicitly n/a with justification) and the verdict is **READY**.

References:
- SOP: `docs/procedures/code-change-pre-submit-sop.md`
- Skill: `@.claude/skills/council/the-gatekeeper/SKILL.md`
- Supporting members: `@.claude/skills/council/the-purifier/SKILL.md`, `@.claude/skills/council/the-prover/SKILL.md`, `@.claude/skills/council/the-codex/SKILL.md`, `@.claude/skills/council/the-architect/SKILL.md`

## Mandatory Rules

1. **Brainstorm first.** State the goal, the smallest unit of behavior change, nullable inputs, partition keys, idempotency / retry concerns, and which Council members you will invoke — before writing code.
2. **Run the gate in order.** Each phase has an exit criterion. If a phase fails, stop and fix before continuing.
3. **Phase 4 — zero new lints.** `dotnet build -warnaserror` (or repo equivalent), ReSharper inspections on changed files, SonarQube quality gate. Do not silence — fix.
4. **Phase 7 — regression on the full affected suite,** not just new tests. Same passing count as before + the new ones. No skipped tests added. Shared library change → run tests in every consumer.
5. **Phase 8 — diff-vs-behavior is a reading exercise.** For every changed production file: `git --no-pager show HEAD:<path>`, read the original method, read the new method end-to-end, verify nullability of every serializer / HTTP / queue / DB input, verify fallback behavior, verify partition-key consistency. For every changed test: arrange data really proves the named behavior; keys match the production write path; mocks model real contracts.
6. **Phase 10 — Copilot PR-review simulation.** Read the diff as a hostile reviewer: nullability, semantic test mismatch, fallback, integration-test assumptions, regressions vs original, PII / logging, concurrency, exception hygiene, public API shape, determinism (workflow code), security (auth / payment).
7. **Phase 11 — documentation.** Update `README.md`, `docs/architecture/`, `docs/procedures/`, `docs/decisions/`, `AGENTS.md` / `copilot-instructions.md`, `CHANGELOG.md`, XML doc comments, and any diagrams that referenced the changed behavior. If no doc surface was affected, say so explicitly with reasoning.

## Required Output

End your work with this exact report and nothing else as your completion message:

```
Gatekeeper Report — <branch / change description>
--------------------------------------------------
Phase 1  Brainstorm:                    [✅|⚠️|❌|n/a]   notes:
Phase 2  Implement:                     [✅|⚠️|❌]       notes:
Phase 3  Purify:                        [✅|⚠️|❌]       notes:
Phase 4  Static analysis (no new lint): [✅|⚠️|❌]       notes:
Phase 5  Unit tests:                    [✅|⚠️|❌]       notes:
Phase 6  Coverage on changed lines:     [✅|⚠️|❌]       notes:
Phase 7  Regression (affected suite):   [✅|⚠️|❌]       notes:
Phase 8  Diff-vs-behavior review:       [✅|⚠️|❌]       notes:
Phase 9  Integration & build:           [✅|⚠️|❌|env]   notes:
Phase 10 Copilot PR-review simulation:  [✅|⚠️|❌]       notes:
Phase 11 Documentation update:          [✅|⚠️|❌|n/a]   notes:

Verdict: READY | BLOCKED
Blocking issues:
  - …
```

Only **READY** permits a push or "done" report. If any phase is ⚠️ or ❌, the verdict is **BLOCKED** — stop and report what's blocking.

## Auto-Fail Anti-Rationalizations

- "Tests passed, shipping."
- "I only changed one line."
- "The failing test was unrelated."
- "I'll let Copilot's PR review catch the rest."
- "Coverage is low because it's hard to test."
- "I disabled the analyzer because it was noisy."
- "Docs are out of date anyway."
- "I'll update the README later."

## The Change

${input:change:Paste the file(s), defect description, or change request here}
