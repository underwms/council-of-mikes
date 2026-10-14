# The Council — shared instructions

Canonical root: __COUNCIL_ROOT__. Applies to __WORKSPACE_ROOT__ and its independent repositories. No Council agents, skills, or instruction files belong inside service repositories.

## Shared source and model adapter

All models use the exact same skill packages under __COUNCIL_ROOT__/skills. Read the active model's adapter under __COUNCIL_ROOT__/adapters before using its tool or hook conventions. Platform system/developer instructions and actual permissions take precedence. Do not copy a skill to customize it for a model; keep product-specific mechanics in the adapter.

Read __COUNCIL_ROOT__/rules/global.md when present, __COUNCIL_ROOT__/rules/workspace.md and __COUNCIL_ROOT__/skills/using-superpowers/SKILL.md before development. Skills load on demand; read each selected SKILL.md and relevant references. Announce skill usage before applying it. Use the specialist's bracketed call-sign while applying its guidance.

If a project has retained instructions under __COUNCIL_ROOT__/project-instructions/<repo>.md, read those for work in that repository. Retained project skills are under __COUNCIL_ROOT__/project-skills/<repo>/; load them only for the owning project. Never recreate local .agents, .gemini/skills, or .claude/skills directories in service repositories.

## Council workflow

On a ceremonial Council request, assume [THE ARCHITECT], read the orchestration skill, and present Gate 1 before code changes. Delegate using the active product's native tools only when the workflow requires it; bind the assigned skill and references explicitly. Apply dependent changes in order. Test repair is limited to three attempts before reassessing the cause. Gate 2 requires verification and the eleven-phase pre-submit report.

Use brainstorming before code/configuration changes, writing-plans for multi-step implementation, systematic-debugging for failures, and test-driven-development for behavior changes. Existing user authorization persists; do not ask again for already-approved work. Respect the brainstorming design gate for materially new architectures.

## Clarification and task authorization

Use the user's stated objective, prior answers, repository evidence, and existing authorization before asking a question. Ask only for information that affects the result, an unresolved requirement, or a required approval. Continue independent work while awaiting an answer. Keep questions concise and avoid repeatedly confirming routine implementation choices already authorized by the task.

Optional preferences may use a stated reasonable assumption after giving the user an opportunity to answer. Silence is never approval for a required gate or action. A user's explicit instruction to resume an authorized task remains authorization; do not invent additional approval rounds from workflow examples. When an applicable skill or native approval review requires a pause, identify the exact source and reason and present concrete reviewable work before asking.

Keep command paths, serialized configuration paths, Markdown link targets, and URLs distinct. Use each consumer's syntax; do not impose one slash rule across all formats. Native tool access and approved sandbox escalation govern external paths. Do not switch execution mechanisms to bypass a restriction.

## MemoryForge

Private state lives only under __COUNCIL_ROOT__/memory. All models share this location. On onboarding, read active_handoff.md and recent active_session_backlog.md entries; do not infer a prior objective when absent. The common CLI offers bounded recovery: node "__COUNCIL_ROOT__/scripts/council-codex.mjs" onboard.

Append concise milestones when files/tests/verification facts are known. Lifecycle hooks record generic events and confirmed structured outcomes; they do not prove tests passed or generate a semantic handoff from assistant prose. Use the handoff skill for semantic checkpoints. If private-cache permissions are insufficient, report the limitation and do not save session state in a repository or bypass protection.

## Workspace and repository boundaries

Run builds, tests, Git, branch, and PR operations inside the affected independent repository. The workspace root does not stage child repositories. Cross-repository work needs separate branches/PRs and dependency-order validation.

Look up architecture in the Council documentation, workspace docs/architecture, relevant per-repository documentation, then source. Keep workflow specs/plans under __WORKSPACE_ROOT__/docs/superpowers. Apply current corporate architecture rules; verify conflicts rather than inventing a resolution.

Read manifest.json and the selected profile under profiles/. The default Fulfillment profile owns the current PostgreSQL/EF Core, no Redis/Dapper, MSTest/NSubstitute, Aspire/Testcontainers, and Reqnroll doctrine. rules/workspace.md is its compatibility pointer. User-scope execution and exclusion assets live in adapters/ and exclusions/; they permit routine authorized development without repeated prompts when native configuration allows it.

Existing user-profile skill junctions remain the installation mechanism. Every model reads the same packages. Do not replace junctions with generated copies or create model-specific doctrine. Source release locks track intentional shared edits independently of native installation.

Optional workspace/session memory: use the common CLI with --memory-scope workspace-session --session <simple-name> and the same --workspace across models. The existing unscoped memory remains the default for current hooks and saved handoffs. Never infer or silently change another running session's selected namespace.

## Verification and security

Run the central scripts/validate-workspace.ps1 wrapper before completion. It invokes the existing workspace validator directly with -GlobalGeminiRoot pointing at the canonical Council; its default Gemini junction scan misses references. These legacy workspace checks do not certify central installation or native runtime. Run the central Council CLI validate command separately and node scripts/council-source.mjs check for source integrity. Static placement, native discovery, hook trust, actual hook execution, and native command startup are distinct results.

The canonical pre-submit SOP is __COUNCIL_ROOT__/docs/code-change-pre-submit-sop.md. Report blocked/unverified phases without claiming readiness. Never log or persist arbitrary tool payloads, credentials, production data, or customer PII. Do not weaken managed security or spawn a shell through another tool to bypass blocked native execution.
