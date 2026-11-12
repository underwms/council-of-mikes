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

- Workspace integrity: `C:\Users\munderwood\.council\scripts\validate-workspace.ps1`.
- Council placement: `node "C:\Users\munderwood\.council\scripts\council-codex.mjs" validate --workspace "<workspace-path>"`.
- Canonical source integrity when shared Council files change: `node "C:\Users\munderwood\.council\scripts\council-source.mjs" check`.

Run checks under the existing native policy. If a check is blocked, identify the command and reason without bypassing restrictions or claiming it passed. Source integrity and static placement do not prove native discovery, hook trust, hook execution, or live model access.

At **Gate 2 (Pre-Submit Approval)**, present the resulting changes, verification evidence, unresolved issues, and any concrete next action requiring user sign-off. This review does not authorize committing, pushing, merging, publishing, deploying, or messaging others; follow the user's actual authorization for those actions.

