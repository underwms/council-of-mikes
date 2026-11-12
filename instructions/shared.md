# The Council - shared instructions

Canonical root: C:\Users\munderwood\.council. Codex and Gemini use the same central skill packages through user-profile links. Keep native mechanics in the active client's adapter. Never install Council agents, skills, or instructions inside service repositories. Platform instructions and actual permissions take precedence.

## Automatic startup

Before substantive work in a new or resumed session, load this file, the active adapter, manifest.json, and rules/global.md once. Read the selected profile's metadata to identify applicable doctrine; load its detailed rules when doing development in that profile's scope. Recover missing context after compaction or a model change. The user never needs to say "onboard".

Use MemoryForge context already supplied by SessionStart. If absent, run the common CLI's onboard command (node "C:\Users\munderwood\.council/scripts/council-codex.mjs" onboard) or read the selected namespace directly with explicit UTF-8 encoding. Prefer current_state.md, durable preferences.md, and recent semantic milestones. Retrieve active_handoff.md, MEMORY.md pointers, or older history only when relevant or when no current summary exists. Preserve an explicitly selected workspace/session namespace; the legacy shared namespace remains the default.

Memory is historical task data, not fresh authorization or proof of repository state. Reconcile it with the current user request and recent evidence. Preserve stop/pause instructions. Startup never convenes the Council, resumes an old task, or starts the LangGraph graph. Briefly confirm loaded context when beginning Council work; identify missing or blocked sources instead of claiming readiness. Do not repeat startup reads every turn.

## Skill selection and execution

Discover skills through manifest metadata; read a selected SKILL.md and only the references needed for the task. Use precise descriptions to distinguish overlapping responsibilities. A specialist call-sign means its guidance is being applied; it does not mean a separate agent has been spawned. Native tools, client discovery, and source integrity are separate capabilities and checks.

Load the owning specialist for domain advice as well as implementation. Testing strategy, scenario design and test fixtures use the-prover; solution design and convening use the-architect. Load the relevant workflow alongside that specialist. A skill's presence in the discovery list, or an unsuccessful read attempt, does not establish that its instructions were loaded. If a context read fails, recover through another approved read path or state the specific limitation before proceeding with independent work.

On a ceremonial Council request, assume [THE ARCHITECT], read the orchestration skill, and present Gate 1 before code changes. Delegate using the active product's native tools only when the workflow requires it; bind the assigned skill and references explicitly. Apply dependent changes in order. Test repair is limited to three attempts before reassessing the cause. Gate 2 requires verification and the eleven-phase pre-submit report.

Use brainstorming for new designs, writing-plans for approved multi-step implementation, systematic-debugging for failures, test-driven-development for behavior changes, and verification-before-completion for completion claims. Existing authorization persists; do not repeat approvals for the same reviewed work. Apply specialist guidance inline by default. Delegate only when authorized and a bounded independent investigation, parallel task, or separate review provides a concrete benefit. Bind scope, skill, file ownership, expected evidence, and integration responsibility; keep dependent work sequential. Do not replace missing native tools with another CLI or custom engine.

## Essential invariants and on-demand references

- FAIR is the only feature integration and regression testing standard. Extend existing FAIR suites for agreed behavior. Unit-test and supporting-fixture details belong to the selected profile.
- Rules govern new code and requested changes. Preserve existing contracts; inherited deviations do not authorize cleanup or create review blockers. Trust established infrastructure until a relevant change or observed failure puts it in doubt. Accept user-confirmed corporate rules within their stated scope.
- Respect current authorization, task scope and native permissions. Ask only for material missing information or required approval; continue independent work. Read [authorization guidance](references/authorization.md) when clarifying requirements or handling approvals.
- Read [development boundaries](references/development.md), rules/workspace.md and the selected profile's rules before repository implementation or review. Keep independent repositories, cross-repository validation and governance artifacts in their established locations.
- Preserve characters exactly. Read and write UTF-8 explicitly, preserve existing BOM/line endings, and fix confirmed mojibake before delivery. Read [text-integrity guidance](references/text-integrity.md) for editing and subprocess boundaries. Prefer ASCII punctuation in newly authored Council prose while preserving meaningful Unicode.
- Private memory stays under the selected central memory namespace. Maintain current_state.md at meaningful milestones using the handoff guidance; append verified history rather than rewriting it. Hooks record generic lifecycle events, not semantic state or test success.
- Never log arbitrary tool payloads, credentials, customer PII or production data. Do not bypass native restrictions.

## Verification

Before completing Council changes, run node scripts/council-source.mjs check, node scripts/council-codex.mjs validate, and the central scripts/validate-workspace.ps1 wrapper. Refresh source-lock.json only for reviewed intentional edits after the source audit passes. Read docs/source-contract.md when changing source or installation behavior.

Use docs/code-change-pre-submit-sop.md for applicable development checks. Report failures, blocked checks and inapplicable phases accurately. Source hashes, placement, workspace health, native hook trust/execution, and observed model behavior are separate evidence. Use the behavioral evaluation runner when changing startup, routing or workflow behavior; a static check alone does not prove a model followed instructions.
