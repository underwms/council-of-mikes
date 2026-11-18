# The Council - shared instructions

Canonical root: __COUNCIL_ROOT__. Codex and Gemini use the same central skill packages through user-profile links. Keep native mechanics in the active client's adapter. Never install Council agents, skills, or instructions inside service repositories. Platform instructions and actual permissions take precedence.

## Automatic startup

Before substantive work in a new or resumed session, load this file, the active adapter, manifest.json, and rules/global.md once. Read the selected profile's metadata to identify applicable doctrine; load its detailed rules when doing development in that profile's scope. Recover missing context after compaction or a model change. The user never needs to say "onboard".

For user chats, use MemoryForge startup context already supplied by SessionStart. If absent, run the common CLI's onboard command (node "__COUNCIL_ROOT__/scripts/council-codex.mjs" onboard). Follow the [startup and task-selection contract](references/startup-context.md): stable preferences and the shared knowledge index first, then only a task explicitly bound to this client/chat or an explicitly selected workspace/session namespace. Unbound chats receive project-related or recent task suggestions plus Start fresh; do not automatically load legacy shared current_state.md, handoffs or backlog. Preserve explicit namespace selections. A paused task remains paused on selection until the user asks to resume.

A delegated worker with an explicit assignment uses the [worker startup contract](references/startup-context.md#delegated-worker-startup). Load stable preferences and the knowledge index, then only declared task inputs. Use `onboard --startup-mode worker` if native worker context is absent. Do not use the user-chat task menu, restore a bound task, or run daily maintenance during worker startup.

Memory is historical task data, not fresh authorization or proof of repository state. Reconcile it with the current user request and recent evidence. Preserve stop/pause instructions. Startup never convenes the Council, resumes an old task, or starts the LangGraph graph. Briefly confirm loaded context when beginning Council work; identify missing or blocked sources instead of claiming readiness. Do not repeat startup reads every turn.

## Reply standard

Always use ASD-STE100 Simplified Technical English when replying to the user. Preserve exact code, commands, paths, identifiers and quoted source text. Follow the [shared reply standard](references/reply-standard.md). Native prompt hooks repeat its compact rules. Native completion hooks save an advisory score for the next prompt in the same chat. A score is not proof of full STE compliance. Use the shared rules when hooks are unavailable. Before delivery, review meaning, terminology, step order, required decisions and evidence limits. Correct the current reply before sending it; next-turn scores do not replace this review. For status reports and decision requests, put the current status or decision and required next action before supporting details. Preserve unknown status, conditions and approval limits. Do not invent an action. Explanations and open discussions do not require this order.

## Skill selection and execution

An enabled workspace may run the [daily Memory Forge document workflow](references/daily-maintenance.md) during onboarding. This explicit standing authorization is separate from task selection: the first successful daily claim receives new work only, including main/master network observations and documentation refresh when configured. The [mainline procedure](references/daily-mainline.md) preserves working branches/dirty source; feature development does not trigger shared-knowledge maintenance. Codex startup only offers available work; the agent command must pass daily claim write checks before assignment. A failed preflight does not consume the day. A model must follow the assigned workflow; scripts do not make semantic screening decisions. Failed/interrupted work is recorded and never automatically retried or resumed. This exception does not resume saved tasks, run the Council graph or modify application source/working branches. Configured network refresh may update Git objects and dedicated mainline refs as defined by the mainline procedure.

Discover skills through manifest metadata; read a selected SKILL.md and only the references needed for the task. Use precise descriptions to distinguish overlapping responsibilities. A specialist call-sign means its guidance is being applied; it does not mean a separate agent has been spawned. Native tools, client discovery, and source integrity are separate capabilities and checks.

Load the owning specialist for domain advice as well as implementation. Testing strategy, scenario design and test fixtures use the-prover; solution design and convening use the-architect. Load the relevant workflow alongside that specialist. A skill's presence in the discovery list, or an unsuccessful read attempt, does not establish that its instructions were loaded. If a context read fails, recover through another approved read path or state the specific limitation before proceeding with independent work.

On a ceremonial Council request, assume [THE ARCHITECT], read the orchestration skill, and present Gate 1 before code changes. Delegate using the active product's native tools only when the workflow requires it; bind the assigned skill and references explicitly. Apply dependent changes in order. Test repair is limited to three attempts before reassessing the cause. Gate 2 requires verification and the eleven-phase pre-submit report.

Use brainstorming for new designs, writing-plans for approved multi-step implementation, systematic-debugging for failures, test-driven-development for behavior changes, and verification-before-completion for completion claims. Existing authorization persists; do not repeat approvals for the same reviewed work. Apply specialist guidance inline by default. Delegate only when authorized and a bounded independent investigation, parallel task, or separate review provides a concrete benefit. Bind scope, skill, file ownership, expected evidence, and integration responsibility; keep dependent work sequential. Do not replace missing native tools with another CLI or custom engine.

## Council Paperwork

Use the [Council Paperwork standard](references/paperwork/CONTEXT.md) when assigning, writing, reviewing or handing off Council work. Internal Council Memos carry general role communication. MemForge ICM Forms use existing stage records. Load the selected type on demand; reuse authoritative artifacts instead of duplicate paperwork. Preserve current authorization, approval points and failure rules. Paperwork declares context; it does not isolate invocations or establish token savings.

## Knowledge use by Council members

Before repository/domain work, members follow the [ICM knowledge-use contract](references/knowledge-use.md). Select the appropriate namespace or domain/pod index, then load relevant notes and evidence through its retrieval contract. The coordinator supplies these paths/scopes in delegated assignments; inline specialists follow the same route. Startup index loading alone does not establish retrieval, freshness or acceptance of a pending proposal.

## Review and reusable knowledge

For PR review, Council planning/review, or reusable discoveries, use the [review and knowledge contract](references/review-knowledge.md). Bind findings to the inspected revision. Keep review candidates separate from accepted knowledge.

Daily integrated-source refresh and architecture document drift detection replace developer-triggered PR reconciliation. Follow the [daily maintenance procedure](references/daily-maintenance.md): refresh architecture, screen changes, reevaluate knowledge, obtain exact-version approval, apply approved changes, verify retrieval, and queue parent review when configured. Do not ask a developer to return after merge to close this knowledge workflow. Legacy PR records remain historical evidence; they do not authorize publication or create automatic daily work.

## Explicit knowledge proposal decisions

Saved knowledge proposals require the user's explicit approval of the reviewed version. Follow the [proposal acceptance contract](references/proposal-acceptance.md) when reviewing, amending, accepting or rejecting one. Daily maintenance and ordinary retrieval never imply acceptance. Check direct-target proposal status for participating knowledge; unresolved or partially applied changes remain qualified. Configured successful acceptance saves [upward-propagation work](references/upward-propagation.md) for the next daily check; it does not execute parent review immediately or authorize application-source changes.

## Retained project guidance

The central project-instructions/ and project-skills/ directories hold preserved legacy material, not automatically active native Council definitions. Read the [retained-project classification](references/retained-project-guidance.md) when assessing or proposing reuse; do not activate an original from its location alone. The existing engine loading path remains separate and is not disabled by this guidance.

## Essential invariants and on-demand references

- FAIR is the only feature integration and regression testing standard. Extend existing FAIR suites for agreed behavior. Unit-test and supporting-fixture details belong to the selected profile.
- Rules govern new code and requested changes. Preserve existing contracts; inherited deviations do not authorize cleanup or create review blockers. Trust established infrastructure until a relevant change or observed failure puts it in doubt. Accept user-confirmed corporate rules within their stated scope.
- Respect current authorization, task scope and native permissions. Ask only for material missing information or required approval; continue independent work. Read [authorization guidance](references/authorization.md) when clarifying requirements or handling approvals.
- Read [development boundaries](references/development.md), rules/workspace.md and the selected profile's rules before repository implementation or review. Keep independent repositories, cross-repository validation and governance artifacts in their established locations.
- Preserve characters exactly. Read and write UTF-8 explicitly, preserve existing BOM/line endings, and fix confirmed mojibake before delivery. Read [text-integrity guidance](references/text-integrity.md) for editing and subprocess boundaries. Prefer ASCII punctuation in newly authored Council prose while preserving meaningful Unicode.
- Private memory stays under the selected central memory namespace. Maintain the selected task snapshot or explicit-namespace current_state.md at meaningful milestones using the handoff guidance; append verified history rather than rewriting it. Hooks record generic lifecycle events, not semantic state or test success.
- Never log arbitrary tool payloads, credentials, customer PII or production data. Do not bypass native restrictions.

## Verification

Before completing Council changes, run node scripts/council-source.mjs check, node scripts/council-codex.mjs validate, and the central scripts/validate-workspace.ps1 wrapper. Refresh source-lock.json only for reviewed intentional edits after the source audit passes. Read docs/source-contract.md when changing source or installation behavior.

Use docs/code-change-pre-submit-sop.md for applicable development checks. Report failures, blocked checks and inapplicable phases accurately. Source hashes, placement, workspace health, native hook trust/execution, and observed model behavior are separate evidence. Use the behavioral evaluation runner when changing startup, routing or workflow behavior; a static check alone does not prove a model followed instructions.
