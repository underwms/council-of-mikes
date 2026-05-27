# Council of Mikes — Agent Guide

This file tells AI coding agents (GitHub Copilot, Claude Code, Cursor, etc.) how to operate inside this repository and how to invoke the Council from any project that adopts it.

## ⛔ ALWAYS-ON GATEKEEPER — READ FIRST

**The Gatekeeper runs implicitly before every "done", every push, and every PR.** The user does not have to say "use pre-submit skill" — the gate is the default.

If you are about to do **any** of the following, you MUST first run the 11-phase Pre-Submit Gate and emit the `Gatekeeper Report` block ending in `Verdict: READY | BLOCKED`:

- Type the word "done", "complete", "finished", "ready", "all set", or "shipped".
- Run `git commit`, `git push`, or open a PR.
- Hand control back to the user after a code, test, doc, or config change.
- Declare a task closed in any todo tracker.

**No Gatekeeper Report → no "done".** Only a `Verdict: READY` permits closing the loop. A `Verdict: BLOCKED` means stop, surface the blockers, and hand back to the owning Council member.

The full gate, its 11 phases, the owning member per phase, and the report format live in `council/the-gatekeeper/SKILL.md` and `procedures/code-change-pre-submit-sop.md`. The "Pre-Submit Skill — Hard Rules" section below restates the contract.

This rule applies whether or not the user explicitly mentioned the Council. The Council is the *how*; the Gatekeeper is the *gate*.

## What This Repo Is

A library of **15 expert AI personas** plus a **Pre-Submit Quality Gate**. Drop it into any workspace and your AI assistant gains a virtual senior engineering team.

- 15 Council members → `council/the-*/SKILL.md`
- 11-phase Pre-Submit SOP → `procedures/code-change-pre-submit-sop.md`
- Slash command → `prompts/pre-submit.prompt.md`
- Routing snippet (drop into your own `AGENTS.md` / `copilot-instructions.md`) → `prompts/council-routing.snippet.md`

See `README.md` for the full member roster and philosophy.

## Routing: How to Invoke the Council

The Council is invoked by `@`-mention. When the user writes any of the phrases below, load the named skill file and follow its instructions before responding.

> **Reminder:** Even if no phrase below matches, the Gatekeeper still runs implicitly before "done" — see the ALWAYS-ON GATEKEEPER rule at the top.

| User phrase | Skill to load |
|---|---|
| `@TheCouncil` / `@Council` / `the council` | Choose the right member for the topic; default to `council/council.md` for a routing decision |
| `@TheCouncil use pre-submit skill` | `council/the-gatekeeper/SKILL.md` + `procedures/code-change-pre-submit-sop.md` (explicit invocation — the same gate that runs implicitly before any "done") |
| `@TheCouncil pre-submit ...` / `@TheCouncil gatekeeper ...` / `@TheGatekeeper ...` | Same as above |
| `@TheArchitect ...` | `council/the-architect/SKILL.md` |
| `@TheCoder ...` | `council/the-coder/SKILL.md` |
| `@TheBuilder ...` | `council/the-builder/SKILL.md` |
| `@TheCodex ...` | `council/the-codex/SKILL.md` |
| `@TheCurator ...` | `council/the-curator/SKILL.md` |
| `@ThePipelineer ...` | `council/the-pipelineer/SKILL.md` |
| `@TheProvisioner ...` | `council/the-provisioner/SKILL.md` |
| `@TheProver ...` | `council/the-prover/SKILL.md` |
| `@ThePurifier ...` | `council/the-purifier/SKILL.md` |
| `@TheRelay ...` | `council/the-relay/SKILL.md` |
| `@TheRenderer ...` | `council/the-renderer/SKILL.md` |
| `@TheSentinel ...` | `council/the-sentinel/SKILL.md` |
| `@TheTimekeeper ...` | `council/the-timekeeper/SKILL.md` |
| `@TheWatcher ...` | `council/the-watcher/SKILL.md` |

**Skill resolution order** (for projects that adopt this Council elsewhere):

1. `<workspace-root>/.claude/skills/council/the-member/SKILL.md`
2. `<workspace-root>/council-of-mikes/council/the-member/SKILL.md`

If neither resolves, ask the user where the Council lives in this workspace.

## Pre-Submit Skill — Hard Rules

These rules apply to **every** pre-submit run — whether the user explicitly invoked `pre-submit skill` / `gatekeeper` / `@TheGatekeeper`, or the Gatekeeper fired implicitly before "done".

1. The input is either (a) **task mode**: a TODO the Council must perform end-to-end, or (b) **audit mode**: existing code, a diff, or a defect description. Either way, run the gate.
2. Run all 11 phases in order: **Brainstorm → Implement → Purify → Static analysis → Unit tests → Coverage → Regression → Diff-vs-behavior → Integration & build → Copilot PR-review simulation → Documentation update**.
3. **Phase 8 is a reading exercise** — fetch the file's prior version, read the original method end-to-end, read the new method end-to-end, verify nullability / fallback behavior / partition keys / ID semantics.
4. **Phase 10 is a Copilot PR-review simulation** — read the diff as a hostile reviewer, not as a test runner.
5. **Phase 11 is documentation** — update `README.md`, `docs/`, `AGENTS.md`, `CHANGELOG.md`, XML docs, diagrams; or state explicitly "no doc surface affected" with reasoning.
6. End the response with the structured **Gatekeeper Report** block (all 11 phases + `Verdict: READY | BLOCKED`). Do not declare "done" unless every phase is ✅ or n/a-with-justification.

**Auto-fail anti-rationalizations** — if you catch yourself thinking any of these, the answer is **BLOCKED**:

- "Tests passed, shipping"
- "Only changed one line"
- "Failing test was unrelated"
- "Copilot's PR review will catch it"
- "Disabled the analyzer, was noisy"
- "Docs are out of date anyway"
- "I'll update README later"
- "The user didn't ask for the gate this time"
- "It's just a doc change"
- "It's just a rename"

Slash-command equivalent: `/pre-submit` (see `prompts/pre-submit.prompt.md`).

## Adopting the Council in Another Project

There are two integration paths:

**Path A — git submodule (recommended for sharing one Council across many repos):**

```bash
cd <your-workspace>
git submodule add https://github.com/underwms/council-of-mikes.git council-of-mikes
```

Then paste the contents of `prompts/council-routing.snippet.md` into your workspace's `AGENTS.md` and/or `.github/copilot-instructions.md`. The routing block uses relative paths that work as soon as the submodule is present, and **carries the ALWAYS-ON GATEKEEPER rule with it** so adopters inherit the same default.

**Path B — direct copy (recommended for a frozen snapshot):**

Copy `council/`, `procedures/`, and `prompts/` into your workspace under `.claude/skills/council/` (or any path you prefer). Update the routing snippet's resolution order to point at your chosen location.

## House Rules for Agents Working in This Repo

When making changes to this repo itself:

- **Public-safe:** No employer/customer names, no internal hostnames, no proprietary identifiers. Tool names that are public OSS (Testcontainers, Mockoon, SonarQube, etc.) are fine.
- **Pre-Submit applies recursively:** Any non-trivial edit to this repo must pass the 11-phase gate. Even Council skill files get reviewed by the Gatekeeper before merge. The ALWAYS-ON rule applies here too.
- **Cross-link discipline:** When you add a new Council member or procedure, update `README.md`, `council/council.md`, and this `AGENTS.md`. Phase 11 of the SOP is not optional.

## Companion Repo

The orchestration / workspace-management counterpart lives at **[MemoryForge](https://github.com/underwms/MemoryForge)** (morning sync, repo onboarding, graph audit, handoffs, docs maintenance). MemoryForge handles *where context lives*; the Council handles *who does the work*.
