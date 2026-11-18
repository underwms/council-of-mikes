---
name: brainstorming
description: Explore requirements, alternatives and design before implementing new behavior or architecture. Use for design discussions; wording-only edits and explanations do not start a design ceremony.
---

# Brainstorming Ideas Into Designs

Turn unresolved requirements and design choices into a concrete, reviewable approach. Scale the discussion to the uncertainty, consequences and existing authorization. A small decision can need a few sentences; a cross-service design can need a written spec.

## Scope and approval

- Start from the user's objective, current evidence and decisions already approved in this task. A request to implement an approved design does not restart brainstorming.
- For a new or materially changed design, present the proposed behavior, scope, relevant alternatives/trade-offs and verification before implementation. Obtain the required design approval once. Do not treat silence as approval.
- An approval covers the reviewed design; recording it in a spec or plan does not create another approval gate. Ask again only for materially new scope, a consequential unresolved decision or an independently required approval.
- Wording-only corrections, explanations and reviews do not require a design ceremony. A request for a proposal authorizes investigation and drafting, not implementation of unapproved behavior.
- When the Council is explicitly convened, preserve its separate Gate 1 and Gate 2 contract. Existing approval satisfies Gate 1 for the same reviewed work; this skill neither adds gates nor removes required sign-off.

## Explore and decide

1. Inspect enough current files, contracts and task context to understand the problem. Use Git history when available and relevant; do not require a Git repository, fetch or clean branch merely to discuss a design.
2. Identify material unknowns. Ask a focused question only when the answer affects the result and cannot be established from existing context. Continue independent work while waiting. Do not invent questions to fill a checklist.
3. For meaningful choices, explain viable approaches and recommend one with its trade-offs. Do not manufacture alternatives for a mechanical correction or an already settled decision.
4. Present one coherent design, scaled to the task. Include behavior, boundaries, dependencies, failure handling and verification where relevant. Complex designs can be discussed in sections, without requiring approval after every section.
5. Once approved, carry that decision into execution. Use writing-plans for approved multi-step implementation; a small change can proceed from its concise approved design when a separate plan adds no useful coordination.

## Preserve scope and engineer discretion

Define the outcomes, shared contracts, ownership and integration order that constrain execution. Leave routine fixture organization, helper structure, cleanup mechanics and individual test examples to the implementing engineer unless an exact choice is material to correctness.

Preserve established contracts needed by the requested change. Inherited deviations, mixed patterns and large files are context; they do not authorize migrations, refactoring, renames or cleanup. Split a large initiative into independently verifiable pieces only when that improves delivery, rather than requiring separate ceremonies for each small change.

## Record and review

- Use an existing task design when it already records the approved decision. For substantial or multi-step work, save a concise spec at the authorized artifact destination, conventionally {artifact_root}/specs/YYYY-MM-DD-<topic>-design.md. Honor user-specified destinations and keep private Council state in the selected central namespace.
- Review the whole design for missing decisions, contradictions, ambiguous scope and verification gaps. Fix drafting errors directly. Return to the user only if resolving a material issue changes the approved design or requires their decision.
- A spec records approval; it does not require a second user approval of unchanged content. Report its location and proceed within existing authorization.
- Commit only when explicitly authorized and the destination is Git-tracked. Never initialize Git or require a commit as a condition of finishing a design.

## Visual Companion

A browser-based companion for showing mockups, diagrams, and visual options during brainstorming. Available as a tool — not a mode. Accepting the companion means it's available for questions that benefit from visual treatment; it does NOT mean every question goes through the browser.

**Offering the companion:** When you anticipate that upcoming questions will involve visual content (mockups, layouts, diagrams), offer it once for consent:
> "Some of what we're working on might be easier to explain if I can show it to you in a web browser. I can put together mockups, diagrams, comparisons, and other visuals as we go. This feature is still new and can be token-intensive. Want to try it? (Requires opening a local URL)"

**This offer MUST be its own message.** Do not combine it with clarifying questions, context summaries, or any other content. The message should contain ONLY the offer above and nothing else. Wait for the user's response before continuing. If they decline, proceed with text-only brainstorming.

**Per-question decision:** Even after the user accepts, decide FOR EACH QUESTION whether to use the browser or the terminal. The test: **would the user understand this better by seeing it than reading it?**

- **Use the browser** for content that IS visual — mockups, wireframes, layout comparisons, architecture diagrams, side-by-side visual designs
- **Use the terminal** for content that is text — requirements questions, conceptual choices, tradeoff lists, A/B/C/D text options, scope decisions

A question about a UI topic is not automatically a visual question. "What does personality mean in this context?" is a conceptual question — use the terminal. "Which wizard layout works better?" is a visual question — use the browser.

If they agree to the companion, read the detailed guide before proceeding:
`skills/brainstorming/visual-companion.md`
