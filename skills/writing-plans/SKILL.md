---
name: writing-plans
description: Turn approved requirements or design into an executable implementation plan with dependencies and verification. Use for multi-step implementation; unresolved design belongs to brainstorming.
---

# Writing Plans

Write a plan that another skilled engineer can execute and verify without reconstructing the task. Preserve engineer discretion over routine implementation details. Plan from the approved requirements; return only material unresolved design decisions to brainstorming.

Announce that this skill is being used. For multi-step work, save the plan at the authorized artifact destination, conventionally {artifact_root}/plans/YYYY-MM-DD-<feature-name>.md. Honor user preferences; keep private Council state in its selected central namespace. Do not require a child-repository write, Git repository or commit to save a plan.

## Establish scope and boundaries

- State the goal, approved behavior, constraints, relevant source baseline and acceptance evidence.
- Identify affected files/components, shared contracts and dependencies. Use exact known paths; when investigation must determine a path, name that bounded discovery task and its expected evidence rather than inventing a file or signature.
- Order dependent changes. Separate independent pieces only when their ownership and integration evidence are clear. Do not require a new spec or plan per small task.
- Preserve existing contracts, mappings and infrastructure. Existing deviations or large files do not authorize cleanup, splitting, migration or fixture replacement.
- Use a worktree only if isolation is useful and available through the active adapter. Do not depend on an absent execution skill or spawn agents merely because a plan has multiple tasks.

## Council Paperwork

Use [Council Paperwork](../../instructions/references/paperwork/CONTEXT.md) for assignments and handoffs. An existing plan can serve as an [Internal Council Memo](../../instructions/references/paperwork/internal-council-memo.md) when it provides the shared core. Bind required inputs to exact versions, state authority and output expectations, and identify consumer checks. Do not create a duplicate memo for an adequate plan.

## Plan detail

Each task should describe:

1. The outcome and affected scope.
2. Material contract/algorithm decisions and dependencies that must be preserved.
3. Verification that demonstrates the behavior, including relevant failure/boundary cases and commands when known.
4. Completion evidence and integration responsibility where work crosses boundaries.

Scale task size to meaningful, verifiable progress; no universal minute target applies. Use code snippets for exact interfaces, non-obvious algorithms or a decision whose correctness depends on the code. Complete production implementations and every test body are not required in a plan. Routine helper structure, fixture organization and local mechanics belong to the implementer.

Be precise about material decisions. Empty instructions such as "handle edge cases" do not replace the specific behavior to verify. A bounded investigation can remain a task with an owner, working assumption and exit evidence; it need not block unrelated work or pretend the answer is known.

## Suggested plan structure

~~~markdown
# [Feature Name] Implementation Plan

Goal: [observable result]
Approved scope and constraints: [contracts, boundaries and exclusions]
Source baseline: [inspected revision/current changes or recorded source identity]

## Task 1: [verifiable outcome]
- [ ] Change: [affected paths/components and material decisions]
- [ ] Dependencies: [prior tasks/contracts, or none]
- [ ] Verify: [specific behavior and suitable command/check]
- [ ] Evidence: [what establishes completion]

## Integration and completion
[cross-component checks, known limits and required review]
~~~

This is a structure, not a requirement to repeat settled context in every task. A concise plan may use prose or a task table when those express the same contract clearly.

## Verification and self-review

- Check the whole plan against the approved requirements. Every material outcome needs implementation and verification coverage somewhere; equivalent wording is sufficient.
- Check shared names, types and dependencies for consistency. Do not invent signatures or exact test counts unsupported by source.
- Apply test-driven-development to executable behavior changes. Documentation-only edits do not require code tests; select checks from the actual changed surface. FAIR remains the feature integration/regression standard.
- Record real environment limits and prerequisite owners. Do not add generic readiness harnesses or new external configuration as permission-to-start gates without evidence of a concrete gap.
- Review for scope expansion, contradictory instructions and repeated approval gates. Correct routine drafting errors directly; seek a decision only for a material new issue.

## Execute within authorization

Report the plan location and next concrete task. If implementation is already authorized, continue without another execution-choice approval. Keep the separate Council convening gates when invoked; prior approval of the same reviewed plan satisfies its Gate 1.

Execute inline by default. Delegate only when authorized and useful, using native tools with bounded ownership, specialist guidance, expected evidence and integration review. Missing native capabilities are not a reason to launch another CLI or custom engine for delegation.

Commit only when explicitly authorized and the destination is Git-tracked. Do not add a commit to every task, switch branches or initialize Git by implication. Preserve existing task status and checkpoint meaningful milestones through handoff guidance.
