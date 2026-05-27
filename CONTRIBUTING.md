# Contributing to the Council of Mikes

Thanks for wanting to make the Council better. This repo is a documentation /
skill-template library, not a runtime — but the rules below still apply because
**the Council holds itself to its own gate**.

---

## The Recursive Rule

> Any non-trivial change to this repo must pass [The Gatekeeper's 11-phase
> Pre-Submit Gate](./procedures/code-change-pre-submit-sop.md).
> Even Council skill files get reviewed by the Gatekeeper before merge.

If you wouldn't ship the change in a production codebase without running the
gate, don't ship it here.

---

## Workflow

1. **Open an issue first** for anything beyond a typo or link fix. Use the
   [issue templates](./.github/ISSUE_TEMPLATE/) — they're structured to surface
   the right context.
2. **Branch from `main`.** Use a descriptive name (`feat/the-cartographer`,
   `fix/sop-phase-numbering`, `docs/quickstart`).
3. **Make the change.** Keep edits surgical — no opportunistic refactors of
   unrelated SKILL.md files.
4. **Run the doc-lint locally** before pushing:

   ```powershell
   pwsh ./scripts/validate-council.ps1
   ```

   The same script runs in CI via `.github/workflows/doc-lint.yml`. Fix
   anything it flags.
5. **Run the Gatekeeper.** Use `@TheGatekeeper` or `/pre-submit` against your
   diff and paste the resulting Gatekeeper Report into the PR description.
6. **Open the PR.** The [PR template](./.github/PULL_REQUEST_TEMPLATE.md)
   already includes the Gatekeeper Report block — fill it out, don't delete it.

---

## Adding a New Council Member

A "member" is a domain-expert persona with its own `council/the-<name>/SKILL.md`.
Before adding one, ask whether an existing member already owns the domain — the
Council errs toward depth, not breadth.

### Required structure for `council/the-<name>/SKILL.md`

1. **YAML frontmatter** (mandatory — the doc-lint enforces it):

   ```yaml
   ---
   name: the-<kebab-case-name>
   description: "Use when ... <one to three sentences describing the trigger conditions and explicit non-responsibilities>."
   ---
   ```

2. **H1 header** matching the persona name and role:
   `# The <Name> — <Role Lead-style label>`

3. **Role / Knows / Does NOT block** — three short paragraphs:
   - `> **Role:** <one sentence>`
   - `**Knows:** <comma-separated list of concrete domain knowledge>`
   - `**Does NOT:** <hand-off list referencing other members in Title Case>`

4. **`## When to Invoke`** — bullet list of trigger phrases.

5. **`## Collaboration Protocol`** — table of `Working with… | the-member's job`.

6. **`## Best Prompts`** — 3–5 example invocations.

7. **`## Cross-References`** — links to related members and procedures.

A reference template is in [`templates/new-member.SKILL.md`](./templates/new-member.SKILL.md) —
copy it, fill in the placeholders, and run `pwsh ./scripts/validate-council.ps1` to verify
structure before opening your PR.

### Required updates when adding a member

- `README.md` member table and count
- `council/council.md` member table, count, routing tables, Best Prompts section
- `AGENTS.md` routing table
- `.github/copilot-instructions.md` (if the new member needs Hard Rules)
- `CHANGELOG.md` Unreleased section
- The doc-lint script (the expected member count check)

The doc-lint workflow will fail your PR if any of these drift.

---

## Style & Voice

- **Personas are proper nouns.** Always `The Architect`, never `the architect`,
  in any cross-reference or routing line.
- **Role label = short "Lead" style** that matches the SKILL.md `# Header`.
  Don't introduce "Senior X Engineer / Y Architect" variants.
- **No employer/customer names.** This repo is public-safe. Public OSS tool
  names (Testcontainers, Mockoon, SonarQube, xUnit, Moq, etc.) are fine.
- **Markdown only** — no HTML, no rendered diagrams that aren't also Mermaid
  source.
- **No emoji in member names or role labels.** Headers stay clean.

---

## Reporting Bugs / Requesting Features

Use the issue templates in `.github/ISSUE_TEMPLATE/`:
- **Bug report** — a member is giving wrong guidance or the SOP has an error.
- **Feature request / new skill** — propose a new companion skill or routing
  improvement.
- **New Council member proposal** — propose a new persona, with domain
  boundaries and overlap analysis.

Security issues: see [`SECURITY.md`](./SECURITY.md). Do **not** open public
issues for vulnerabilities.

---

## Code of Conduct

Be excellent. Disagreements are fine; condescension is not. The Council itself
documents "Members defer to specialists, never freelance" as Operating Principle
#4 — apply the same rule to human contributors.
