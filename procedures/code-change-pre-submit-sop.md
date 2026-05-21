# Code Change Pre-Submit SOP

**Last Updated:** 2026-05-21
**Owner:** The Council (enforced by [[the-gatekeeper]])
**Applies To:** Every AI agent (Council member, GitHub Copilot, Claude Code, custom subagent) that produces or modifies code in this workspace.

---

## Purpose

This SOP is the **standard gate before any code change is declared "done"** — before a push, before a PR, before reporting success to a human partner.

It exists because:

- **Tests passing ≠ correct.** Tests can be wrong, mocked at the wrong layer, or assert the wrong invariant.
- **A diff is not the full method.** A 3-line edit can silently change the contract of a 60-line method.
- **GitHub Copilot's PR review catches things we should have caught.** If an automated PR reviewer would flag it, we already failed the gate.
- **Regressions don't announce themselves.** Adjacent tests must run, not just the new ones.

If any phase fails, **stop and fix before moving forward.** Do not paper over a failed phase with a comment in the PR description.

---

## Roles (Council Mapping)

| Phase | Owning Council Member |
|------|------------------------|
| 1. Brainstorm | [[the-architect]] + [[the-coder]] (whoever owns the design space) |
| 2. Implement | [[the-coder]] / [[the-builder]] / [[the-timekeeper]] / [[the-renderer]] |
| 3. Purify | [[the-purifier]] |
| 4. Static Analysis | [[the-purifier]] |
| 5. Unit Tests | [[the-prover]] |
| 6. Coverage Validation | [[the-prover]] |
| 7. Regression | [[the-prover]] |
| 8. Diff-vs-Behavior Review | [[the-gatekeeper]] |
| 9. Integration / Build | [[the-prover]] + [[the-builder]] |
| 10. Copilot PR-Review Simulation | [[the-gatekeeper]] |
| 11. Documentation Update | [[the-codex]] (audited by [[the-gatekeeper]]) |

The **Gatekeeper** is the final voice. If the Gatekeeper has not run, the work is not done.

---

## The 11-Phase Pre-Submit Gate

### Phase 1 — Brainstorm

**Before writing code, the Council runs a brainstorm.**

- State the goal in one sentence.
- Identify the smallest unit of behavior change.
- Surface unknowns explicitly (nullability, partition keys, downstream consumers, idempotency, time/clock dependencies).
- Decide which Council members are needed and in what order.
- If the change touches workflow code, **the Timekeeper must be in the room.**
- If the change touches auth, PII, or payment data, **the Sentinel must be in the room.**

Skip this phase only when the change is purely mechanical (rename, formatting, dependency bump) **and** no behavioral surface is touched.

**Exit criteria:** Written one-paragraph design note covering scope, contract changes, and risk areas.

---

### Phase 2 — Implement

The owning member writes the change. Rules that apply to every member:

- **Read the full file**, not just the area being edited.
- **Read the full method being modified** before changing any line in it.
- Match existing patterns in the repo. Do not invent a new convention silently.
- Keep edits surgical — no opportunistic refactors of unrelated code.
- If a serializer / deserializer feeds into the changed code path, **note every nullable field** and confirm the runtime behavior of each.

**Exit criteria:** The code compiles locally.

---

### Phase 3 — Purify (Cleaner Pass)

[[the-purifier]] runs its **Five-Pass Protocol** on every changed file:

1. Formatting & style (file-scoped namespaces, `var` usage, `.editorconfig` compliance)
2. Modernization (primary constructors, pattern matching, collection expressions, raw string literals, `is null`)
3. Dead code & redundancy
4. Complexity reduction (cognitive complexity ≤ 15 per method)
5. Naming & readability

**Tripwires** the Purifier always sweeps for: trailing whitespace, BOMs, mixed line endings, `async` without `await`, missing `Async` suffix, `new HttpClient()`, `DateTime.UtcNow` in workflow code, magic config strings, `throw ex;`, empty catch blocks, string concatenation in log calls, PII in logs.

**Exit criteria:** No Purifier tripwires remain. File matches surrounding files in style.

---

### Phase 4 — Static Analysis (No New Lints)

**Hard rule: zero new warnings introduced by this change.**

Run, in order:

1. `dotnet build -warnaserror` (or repo equivalent) — must succeed.
2. ReSharper / Rider code inspections on changed files — no new suggestions.
3. Roslyn analyzers (StyleCop, SonarAnalyzer, Microsoft.CodeAnalysis.NetAnalyzers) — no new diagnostics.
4. SonarQube quality gate (if configured) — pass.

If a warning was pre-existing in the file and not caused by this change, document it; do not silence it without approval.

**Exit criteria:** Build is clean. No new analyzer diagnostics. No new ReSharper suggestions in the diff.

---

### Phase 5 — Unit Tests

[[the-prover]] writes or updates unit tests for every behavior change.

For each test, the Prover verifies:

- **Naming follows the convention:** `<Subject>_<ExpectedOutcome>_<Condition>`.
- **Arrange / Act / Assert** spacing is correct.
- **Arrange data actually proves the intended behavior** — not a happy-path placeholder that would pass with any implementation.
- **Partition keys / IDs / tenant IDs** in arrange data match the write-path behavior of the production code. Mismatched keys are a top-3 silent-failure source.
- **Mocks verify the right interaction** at the right specificity (no blanket `It.IsAny<>` when a specific argument is the contract).
- **Boundary cases:** null inputs, empty collections, default values from deserializers.
- **Async paths** are awaited in the test, not fire-and-forget.

**Exit criteria:** New tests fail without the change and pass with it. (Mutation check optional but encouraged.)

---

### Phase 6 — Coverage Validation

- Coverage on changed lines: **≥ 80%** (or repo-specific threshold).
- Coverage on changed branches: every new branch hit at least once.
- If a line is intentionally uncovered (e.g., defensive guard against impossible state), annotate with a comment explaining why.

**Exit criteria:** Coverage report shows changed code is exercised. Uncovered lines are justified.

---

### Phase 7 — Regression

**Run the entire affected test surface, not just the new tests.**

- Run all unit tests in the changed project.
- Run all unit tests in projects that reference the changed project.
- If the change is in a shared library, run unit tests in **every** consumer.
- Diff the test result count: same number of tests passing as before + the new ones. No silently disabled or skipped tests.

**Exit criteria:** Full unit-test suite for affected scope is green. No skipped tests added.

---

### Phase 8 — Diff-vs-Behavior Review (Semantic Diff)

This is the phase most commonly skipped. The Gatekeeper owns it.

1. `git diff --name-only` — list every changed file.
2. For **every changed production file**:
   - Read the **full changed method**, not just the diff hunk.
   - Compare against the **original behavior** (use `git show HEAD:<file>` if needed).
   - Check **nullable inputs** from serializers / deserializers — does the new code handle `null`, missing properties, default values, empty collections?
   - Check **fallback behavior** — if a dependency throws, returns null, returns empty, or times out, does the new code do the right thing?
   - Check **idempotency / retry safety** if the method is part of a retryable pipeline.
   - Check **partition-key / write-key consistency** with read-side code.
3. For **every changed test file**:
   - Verify the **arrange data actually proves** the intended behavior.
   - Confirm **partition keys / IDs** in test data match the production write path.
   - Confirm mocks model the **real dependency contract**, not a convenient fiction.
4. For **every deleted line**, ask: "What contract did this line guarantee, and where is that contract now satisfied?"

**Exit criteria:** Every changed method has been read end-to-end and compared to its prior behavior. Every changed test has been validated as a real proof, not a tautology.

---

### Phase 9 — Integration Tests & Build

- Run the relevant integration test filter (containerized test fixtures, mocked external services, etc.).
- If integration tests cannot run locally (environment-only failure), **document the environment requirement explicitly** in the PR description — do not silently skip.
- Run a full repo build one final time after all prior fixes.

**Exit criteria:** Integration tests pass, or the environment-only gap is documented with the exact command and required environment.

---

### Phase 10 — GitHub Copilot PR-Review Simulation

**This is the final gate. It is not optional.**

The Gatekeeper performs a Copilot-style PR review on the current diff, evaluating every changed production method and its tests against:

| Category | What to check |
|----------|---------------|
| **Nullability** | Every input from a serializer, HTTP body, queue message, or DB read — is null handled? |
| **Semantic test mismatch** | Does the test name claim a behavior that the assertions don't actually verify? |
| **Fallback behavior** | If a dependency fails, does the code recover correctly per the original contract? |
| **Integration assumptions** | Do tests assume container state, time, or external order that production won't guarantee? |
| **Regressions against original behavior** | Has any path that used to work been silently changed? |
| **Logging & PII** | Has any new log statement leaked sensitive data? |
| **Concurrency** | Any new shared state, race conditions, missing `await`, or fire-and-forget? |
| **Error messages** | Are exceptions still informative, with `throw;` preserving stack traces? |
| **Public API shape** | Have any non-private signatures changed in a way callers won't expect? |

**Do not just run tests in this phase.** This is a reading exercise.

**Exit criteria:** The Gatekeeper can state, in writing, that a Copilot PR review on this diff would surface zero substantive issues.

---

### Phase 11 — Documentation Update

**No code change is done until the documents that describe the system are still true.**

[[the-codex]] owns this phase. The Gatekeeper audits it.

For every change, walk the documentation surface and update what is now stale:

#### Repo-level docs (in the changed repo)

- **`README.md`** — setup steps, dependencies, environment variables, build/run/test commands. If any of these changed, the README changes.
- **`docs/architecture/`** — if the change touches module boundaries, public contracts, message flows, data models, partition keys, or external dependencies, update the relevant architecture snapshot.
- **`docs/procedures/`** — if a new recurring task was introduced or an existing procedure changed, create or update the SOP.
- **`docs/decisions/`** — if a non-trivial design choice was made (or a prior choice reversed), record it as a decision / ADR. Include lessons learned.
- **`AGENTS.md` / `copilot-instructions.md` / `CLAUDE.md`** — if agent-facing conventions, commands, or guardrails changed, update the agent instructions so future sessions inherit them.
- **`CHANGELOG.md`** — if the repo maintains one, add the entry under the correct version / unreleased section.
- **XML doc comments** — public types, methods, and parameters that changed signature or contract get their `<summary>`, `<param>`, `<returns>`, and `<exception>` tags updated.
- **Diagrams** — if Mermaid / PlantUML diagrams in the docs reference a renamed component, new flow, or removed dependency, regenerate them.

#### Workspace-level docs (in the parent MemoryForge / context workspace)

- **`docs/architecture/{repo}/`** mirrors — if the workspace tracks architecture snapshots per child repo, refresh the mirror for the affected repo.
- **`docs/maps/`** — Obsidian / knowledge-graph maps that reference the changed component get updated links and notes.
- **`docs/handoffs/`** — if this change closes or opens a handoff item, update it.
- **Session artifacts** — `plan.md`, decision notes, or task breakdowns in the session folder should be archived or marked complete.

#### Documentation tripwires (Codex sweeps for these every time)

| Tripwire | Fix |
|---|---|
| README "Getting Started" doesn't actually work after the change | Re-run the steps. Update them. |
| Architecture diagram still shows a removed component | Regenerate the diagram. |
| Code comment contradicts the new behavior | Update or delete the comment. |
| XML doc says `<returns>null if not found</returns>` but the method now throws | Update the XML doc. |
| Environment variable renamed in code but old name still in README / `.env.example` | Update both. |
| New public type with no XML doc summary | Add one. |
| ADR for a now-reversed decision was never updated | Add a superseding ADR; mark the old one. |
| `AGENTS.md` mentions a Council member, command, or skill that no longer behaves the same | Update. |

#### Stale-doc detection commands

```bash
# Identify docs touched in the last N commits to spot drift
git --no-pager log --since="1 month ago" --name-only --pretty=format: -- 'docs/**' README.md AGENTS.md | sort -u

# Find references to renamed symbols in the docs
grep -rni "<old-name>" docs/ README.md AGENTS.md

# List public APIs missing XML docs (C# example)
dotnet build -p:GenerateDocumentationFile=true -warnaserror:CS1591
```

#### What Codex does **not** do in this phase

- Does not invent new docs that aren't justified by the change.
- Does not paste auto-generated boilerplate. Every updated doc must be readable as if a human wrote it.
- Does not duplicate content already covered elsewhere — link, don't copy.

**Exit criteria:** Every document that *referenced the changed behavior* now reflects the new behavior. Every new public surface has at least one place a human (or future agent) can read to understand it. The Codex can name each updated doc in the done-report.

---

## Reporting "Done"

Only after Phase 11 may an agent report the work as done. The done-report **must** include:

```
✅ Phase 1 — Brainstorm: [link or summary]
✅ Phase 2 — Implement: [files changed]
✅ Phase 3 — Purify: [no tripwires]
✅ Phase 4 — Static analysis: [build clean, 0 new lints]
✅ Phase 5 — Unit tests: [N new / M updated]
✅ Phase 6 — Coverage: [X% on changed lines]
✅ Phase 7 — Regression: [N tests, all green]
✅ Phase 8 — Diff-vs-behavior: [summary of methods re-read]
✅ Phase 9 — Integration & build: [command + result, or env gap documented]
✅ Phase 10 — Copilot PR-review simulation: [summary]
✅ Phase 11 — Documentation update: [files updated, or "no doc surface affected"]
```

If any phase is `⚠️` or `❌`, the work is **not** done. Report what's blocking and stop.

---

## Anti-Patterns (Auto-Fail the Gate)

- "Tests passed, shipping." — Phase 8 and 10 were skipped.
- "I only changed one line, it's safe." — Read the full method.
- "I'll let Copilot's PR review catch the rest." — That's the gate, not a safety net.
- "The failing test was unrelated." — Prove it. Do not skip or `[Fact(Skip=...)]` your way past a red test.
- "Coverage on the new code is low because it's hard to test." — Escalate to the Prover; do not lower the bar.
- "I disabled the analyzer because it was noisy." — Escalate; do not silence.
- "The docs are out of date everywhere anyway." — Update the ones your change touched. Drift compounds.
- "I'll update the README later." — Later doesn't come. Update it now.

---

## When to Short-Circuit

The full 11 phases apply to behavioral changes. For these narrow cases, you may run a reduced gate, but **document which phases were skipped and why**:

| Change type | Required phases |
|-------------|-----------------|
| Pure rename / format-only | 3, 4, 7, 10, 11 |
| Dependency version bump (no API change) | 3, 4, 7, 9, 10, 11 |
| Documentation only | 10, 11 |
| Configuration value change | 4, 7, 8, 10, 11 |

Anything that touches a method body, a test, or a public API runs the **full** gate.

---

## Cross-References

- [[the-gatekeeper|The Gatekeeper Skill]] — enforces this SOP
- [[the-purifier|The Purifier]] — Phases 3 & 4
- [[the-prover|The Prover]] — Phases 5, 6, 7, 9
- [[the-architect|The Architect]] — Phase 1
- [[the-codex|The Codex]] — Phase 11
- [[the-sentinel|The Sentinel]] — Pulled in for auth/PII/payment changes
- [[the-timekeeper|The Timekeeper]] — Pulled in for workflow/temporal changes
