---
name: the-council-orchestration
description: Coordinate Council work when the user asks to convene the Council or requests Council coordination. Discussing, quoting or editing this skill does not invoke it; never launches the custom graph.
---

# The Council Orchestration

## Purpose and invocation boundary

Act as `[THE ARCHITECT]` to coordinate relevant Council expertise using the active model's own planning, task tracking, and available orchestration tools. This skill is a workflow guide for the current session.

An actual request such as "Convene the Council: [task]" invokes this workflow. A quoted example, a question about the Council, or an audit of this skill does not. Complexity alone does not require convening the Council. If the skill is selected without a Council coordination request, stay within the user's task; do not introduce a Council ceremony, delegation, or extra approval rounds.

This skill does not provide a standalone engine execution mode. Never launch, install, configure, or modify the custom LangGraph engine as a consequence of invoking or discovering this skill. Any future use of that engine is a separate manual user action outside this workflow.

## Host-native coordination

- Read the shared Council instructions, active host adapter, manifest, and selected profile. Use the host's actual capabilities and permissions; skill instructions do not grant tool access.
- Select only specialists relevant to the task. Read their canonical `SKILL.md` and applicable references before applying their guidance. Find packages through the manifest rather than copying definitions into a repository.
- Use native subagents when useful, available, and authorized by the active host and task. Give each delegated task its specialist instructions, references, scope, file ownership, expected result, and verification requirements. Keep dependent changes sequential and review results before integrating them.
- Inline work is a normal alternative when delegation is unnecessary or unavailable. Apply the relevant specialist guidance directly and describe who is doing the work accurately. Do not launch another CLI, external model session, or custom orchestration engine to replace missing native tools.

## Worker context boundary

For an isolated assignment, start a fresh native worker without inherited chat history. Supply the task identity, role, current authority, allowed changes, exact versioned inputs, expected saved output and consumer checks. Required host instructions remain present.

Use the [worker startup contract](../../instructions/references/startup-context.md#delegated-worker-startup). A worker reads stable preferences and the knowledge index through native worker context or onboard --startup-mode worker. It must not use generic onboard, open a task-choice menu, restore unrelated task state or run daily maintenance. Required namespace evidence is an explicit assignment input.

Use a new native worker for a new isolated assignment. A bounded follow-up within the same assignment retains that worker context and is not a fresh-context sample. A reviewer receives the saved result and required source evidence. Record missing or stale inputs before dependent work. No declaration proves universal context absence or token savings.

## Council Paperwork

Use the [shared paperwork standard](../../instructions/references/paperwork/CONTEXT.md) for role assignments, decisions, findings and handoffs. An [Internal Council Memo](../../instructions/references/paperwork/internal-council-memo.md) can be part of the existing plan or review artifact. Declare versioned inputs, applicable rules, allowed changes, expected output and consumer checks. Use [MemForge ICM Forms](../../instructions/references/paperwork/memforge-icm-forms.md) for ICM work. Do not duplicate existing records or treat a memo as approval, delegation authority or a new execution boundary.

## Workflow

### 1. Understand and plan

Use `[THE ARCHITECT]` while coordinating Council work. Establish the requested outcome, affected repositories, constraints, and existing authorization. Follow the applicable design and planning workflows, scaled to the task. Apply technology doctrine from the selected profile only where relevant.

Apply rules to new code and requested changes; preserve existing contracts, mappings, dependencies, and layouts needed for integration. Pre-existing deviations do not create cleanup tasks, migrations, or review blockers. Treat corporate rules supplied or confirmed by the user as authoritative without requiring provenance links. Do not expand the plan to reconcile inherited code with current standards.

At **Gate 1 (Plan Approval)**, present the scope, proposed changes, relevant specialist assignments, dependencies, and verification plan for review before implementation. A reviewed plan already approved in the active task satisfies this gate; do not ask again for approval of the same work. Pause for materially new scope or an approval actually required by the applicable workflow.

### 2. Execute and verify

Carry out approved work using native tools or inline specialist guidance. Run appropriate checks in each affected independent repository. Use `[THE PROVER]` guidance where testing applies; do not route every change through every specialist.

If checks fail, investigate the cause and use diagnostic evidence for at most three repair attempts before reassessing the approach. Do not repeat unchanged commands or weaken checks to manufacture a pass. Report remaining failures and blockers.

### 3. Review and present evidence

Use `[THE GATEKEEPER]` guidance for the applicable pre-submit review. Read `docs/code-change-pre-submit-sop.md` under the canonical Council root; distinguish passed, failed, blocked, unverified, and inapplicable phases.

Use the central validation entry points with the actual workspace path:

- Workspace integrity: `__COUNCIL_ROOT__\scripts\validate-workspace.ps1`.
- Council placement: `node "__COUNCIL_ROOT__\scripts\council-codex.mjs" validate --workspace "<workspace-path>"`.
- Canonical source integrity when shared Council files change: `node "__COUNCIL_ROOT__\scripts\council-source.mjs" check`.

Run checks under the existing native policy. If a check is blocked, identify the command and reason without bypassing restrictions or claiming it passed. Source integrity and static placement do not prove native discovery, hook trust, hook execution, or live model access.

At **Gate 2 (Pre-Submit Approval)**, present the resulting changes, verification evidence, unresolved issues, and any concrete next action requiring user sign-off. This review does not authorize committing, pushing, merging, publishing, deploying, or messaging others; follow the user's actual authorization for those actions.

## Review and knowledge follow-through

During planning, retrieve relevant constraints using the [shared review and knowledge contract](../../instructions/references/review-knowledge.md). During execution/review, retain only reusable, evidence-backed candidates. Gate 2 reports daily knowledge coverage and pending proposals separately from readiness. Daily architecture drift detection replaces developer PR reconciliation. Preserve evidence paths, reviewed revisions, coverage gaps, owners and next actions in private task state. Convening does not start a watcher or the custom engine.

Before repository/domain work, follow the [ICM knowledge-use contract](../../instructions/references/knowledge-use.md): route to the applicable collection, open relevant notes and evidence, and preserve status/freshness qualifications. Use it inline and include its scope and paths in any authorized delegated assignment.
