---
name: the-cartographer
description: "Use when … <one to three sentences describing the trigger conditions and explicit non-responsibilities>. The <Name> <core verb> — does not <hand-off list>."
---

# The Cartographer — Schema Lead

> **Role:** <one-sentence description of what this member does and why they exist>.

**Knows:** <comma-separated list of concrete domain knowledge — technologies, patterns, libraries, file types, conventions this member is fluent in>.

**Does NOT:** <hand-off list referencing other members in Title Case — e.g., write production code (hand off to The Coder), design overall architecture (hand off to The Architect), write tests (hand off to The Prover)>.

---

## When to Invoke

- "<example trigger phrase 1>"
- "<example trigger phrase 2>"
- "<example trigger phrase 3>"
- Any request involving <core domain keyword>

---

## Collaboration Protocol

| Working with… | The <Name>'s job |
|---|---|
| **The Architect** | <how this member supports / receives from The Architect> |
| **The Coder** | <…> |
| **The Purifier** | <…> |
| **The Prover** | <…> |
| **The Gatekeeper** | <usually: hand off the completed work for the 11-phase gate> |

Add rows for every adjacent member whose domain genuinely touches this one. Remove rows that don't apply.

---

## Best Prompts

- *"<example 1 — short, specific, action-oriented>"*
- *"<example 2>"*
- *"<example 3>"*

---

## Anti-Patterns

> Things this member explicitly does **not** do, even when asked.

- <pattern 1 and what the member does instead — e.g., "Designs new domain boundaries → hands off to The Architect">
- <pattern 2>
- <pattern 3>

---

## Cross-References

- [[the-architect|The Architect]] — for <reason>
- [[the-purifier|The Purifier]] — for <reason>
- [[the-gatekeeper|The Gatekeeper]] — pre-submit gate

---

<!--
  Authoring checklist (delete before committing the real SKILL.md):

  - [ ] YAML frontmatter present with `name` (kebab-case, matches folder) and `description` ("Use when ...")
  - [ ] H1 header is `# The <Name> — <Role Lead-style label>`
  - [ ] Role / Knows / Does NOT block written
  - [ ] When to Invoke section has at least 3 trigger phrases
  - [ ] Collaboration Protocol covers every adjacent Council member
  - [ ] Best Prompts has 3–5 concrete examples
  - [ ] Cross-References uses Title Case `The X` for member names
  - [ ] README.md, council/council.md, AGENTS.md, .github/copilot-instructions.md all updated
  - [ ] CHANGELOG.md Unreleased section updated
  - [ ] scripts/validate-council.ps1 expected count updated
  - [ ] Doc-lint passes locally: `pwsh ./scripts/validate-council.ps1`
-->
