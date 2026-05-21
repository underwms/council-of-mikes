## Council Routing (@TheCouncil)

When the user invokes `@TheCouncil`, `@Council`, `the council`, or any direct mention of a Council member (`@TheGatekeeper`, `@ThePurifier`, `@TheProver`, `@TheCodex`, `@TheArchitect`, `@TheCoder`, `@TheBuilder`, `@TheTimekeeper`, `@TheSentinel`, `@TheWatcher`, `@TheRelay`, `@TheRenderer`, `@TheCurator`, `@ThePipelineer`, `@TheProvisioner`), resolve and load the matching Council skill file before responding.

**Council skill location (resolution order):**

1. `<workspace-root>/.claude/skills/council/<member>/SKILL.md`
2. `<workspace-root>/council-of-mikes/council/<member>/SKILL.md`

If neither resolves, ask the user where the Council lives in this workspace.

### Phrase → Skill Map

| User phrase | Action |
|---|---|
| `@TheCouncil use pre-submit skill` | Load `the-gatekeeper/SKILL.md` + `docs/procedures/code-change-pre-submit-sop.md`. Run the **11-phase Pre-Submit Gate** on the content the user pastes. End with the `Gatekeeper Report` and `Verdict: READY | BLOCKED`. |
| `@TheCouncil pre-submit ...` | Same as above. |
| `@TheCouncil gatekeeper ...` | Same as above. |
| `@TheGatekeeper ...` | Same as above. |
| `@TheCouncil brainstorm ...` | Load `the-architect/SKILL.md` and run the Brainstorm (Phase 1 of the SOP) on the content. |
| `@ThePurifier ...` | Load `the-purifier/SKILL.md`, run the Five-Pass Protocol on the content. |
| `@TheProver ...` | Load `the-prover/SKILL.md`, write/audit tests for the content. |
| `@TheCodex ...` | Load `the-codex/SKILL.md`, update docs for the content. |
| `@TheTimekeeper ...` | Load `the-timekeeper/SKILL.md` for workflow/temporal/determinism concerns. |
| `@TheSentinel ...` | Load `the-sentinel/SKILL.md` for auth/PII/payment concerns. |

### Pre-Submit Skill — Hard Rules

When `pre-submit skill` is invoked:

1. Treat the user-pasted content as the change being audited.
2. Run all 11 phases in order (Brainstorm → Implement → Purify → Static analysis → Unit tests → Coverage → Regression → Diff-vs-behavior → Integration & build → Copilot PR-review simulation → Documentation update).
3. **Phase 8 is a reading exercise** — `git --no-pager show HEAD:<file>`, read the original method end-to-end, read the new method end-to-end, verify nullability / fallback / partition keys.
4. **Phase 10 is a Copilot PR-review simulation** — read the diff as a hostile reviewer, not as a test runner.
5. **Phase 11 is documentation** — update `README.md`, `docs/`, `AGENTS.md`, `CHANGELOG.md`, XML docs, diagrams; or state explicitly "no doc surface affected" with reasoning.
6. End the response with the structured `Gatekeeper Report` block (all 11 phases + `Verdict: READY | BLOCKED`). Do not declare "done" unless every phase is ✅ or n/a-with-justification.

**Auto-fail anti-rationalizations:** "Tests passed, shipping" · "Only changed one line" · "Failing test was unrelated" · "Copilot's PR review will catch it" · "Disabled the analyzer, was noisy" · "Docs are out of date anyway" · "I'll update README later".

Slash-command equivalent: `/pre-submit` (see `.github/prompts/pre-submit.prompt.md`).
