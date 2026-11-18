# codex adapter

Canonical Council: __COUNCIL_ROOT__.

Codex loads the profile .codex/AGENTS.md pointer. It does not expand @file imports; explicitly read the shared instructions. Skill discovery uses profile .agents/skills junctions to the canonical root. Use native spawn_agent only when authorized by the Council workflow; normal filesystem reads load skills. Hooks register in profile .codex/hooks.json. Review/trust exact definitions, then verify actual events and native sandbox startup. Permission profiles and .codex/rules policy are distinct from shared Markdown guidance.

## Automatic Council startup

Follow the shared startup procedure and [task-selection contract](../instructions/references/startup-context.md) once per session. SessionStart provides user-level stable context outside the configured workspace too; workspace lifecycle logging retains its location guard. For user chats, use the common onboard CLI when startup context is absent, including projectless chats. Restore only a bound task or explicit namespace; otherwise offer project-related/recent saved tasks plus Start fresh. Preserve paused status and explicit namespace selection. Recover only missing context after compaction/model changes. Never start the standalone engine during startup.

For native loading qualification, follow [behavior evaluation](../docs/behavior-evaluation.md). In particular, a nested Windows sandbox can fail at CreateDesktopW before a command starts; classify that host failure separately from skill selection. Keep Codex's native sandbox enabled when using approved host-level test execution. Native structured skill injection and full file-read delivery are distinct evidence paths.

## Delegated worker startup

For an explicit delegated assignment, follow the [worker startup contract](../instructions/references/startup-context.md#delegated-worker-startup). The Codex SubagentStart hook returns stable preferences and the knowledge index. It does not load the parent task, present suggestions, run daily maintenance, or write bindings/receipts.

SubagentStart session_id is the parent identity, not the worker identity. The handler must route to stable-only startup before any binding lookup. If worker context is absent, run the common onboard command with --startup-mode worker. Do not use ordinary onboard for a worker. This fallback also works without a native chat ID.

Review changed hook definitions through normal native trust. A fresh-agent observation and a script fixture establish different evidence. Do not claim hook execution from installation or a manual handler invocation.

## Shared source configuration

Read manifest.json and this adapter's JSON descriptor. Source policy and exclusions are user-scoped, across development workspaces. Use central exclusions/global.ignore for explicit discovery. Read docs/source-contract.md for native configuration fragments, their effective limitations, and the source audit commands. The source reconciliation does not overwrite live user-profile settings.

Existing hook configuration is preserved. Optional explicit --memory-scope workspace-session --session <simple-name> uses a workspace/session namespace below central memory, shared by all model actors. Legacy saved handoffs remain preserved. Default startup now uses stable context plus explicit task selection; it does not adopt those handoffs automatically.

## Questions and file references

Apply the shared clarification and authorization rules. Use `request_user_input_async` for missing information when available; continue useful independent work while a question is pending. Use `request_user_input` only in a mode that exposes it. Do not invoke plan-only tools in an ordinary session. If no question tool is available, ask one focused question in chat. A preselected option or elapsed time is not a submitted answer. Required approvals must remain pending until explicitly answered.

For local file references in Codex responses, use clickable Markdown links with an absolute target, forward slashes, and an optional single line number: `[shared.md](C:/Users/Developer/.council/instructions/shared.md:1)`. For paths containing spaces, enclose the target in angle brackets. Do not use `file://`, editor-specific URI schemes, backslashes in the link target, or backticks around the link. Repository documentation uses valid relative links; JSON uses its required escaping; PowerShell uses native paths and `-LiteralPath`. Follow the current client's rendering requirements if they differ.

Profile instruction files remain thin pointers. Read shared instructions and this adapter explicitly, then applicable central rules and skills. Native skill discovery metadata is not a substitute for reading the selected package. If an existing junction cannot be resolved inside the sandbox, report an access limitation and use an approved read-only escalation to distinguish it from a broken link; do not recreate or relink a healthy package based on that error alone.

## User defaults

The Council installer merges the three root keys in `adapters/codex/config.toml` into the user's `.codex/config.toml`: `approval_policy = "on-request"`, `approvals_reviewer = "auto_review"`, and `sandbox_mode = "workspace-write"`. This makes Approve for me the starting mode for new Codex sessions, subject to native availability, configuration overrides, and managed requirements. Automatic review applies to eligible requests that cross the sandbox boundary; it does not remove the sandbox or guarantee approval.

Installation backs up a changed native config and preserves unrelated text, model settings, MCP servers, network settings, writable roots, plugins, and trust state. The owned keys must be single-line root string assignments; scoped or non-scalar forms and duplicate logical keys reject installation before writes. Existing session overrides are not rewritten. Confirm the effective configuration in a fresh client with `/status` and `/debug-config`.

The `workspace_write_roots` binding in `adapters/codex.json` adds only the recipient's canonical Council root to native `[sandbox_workspace_write].writable_roots`. Existing roots remain. Network access, Windows sandbox selection, model settings, project trust, and managed permissions are preserved. Dotted or inline forms of this table, duplicate tables/keys, and non-string root arrays require reconciliation before writes. Session-specific command approvals in `.codex/rules/default.rules` are not distributable Council defaults.

Use `setup-council.ps1 -WorkspaceRoot <path> -NativeOnly` for client setup without the standalone Python engine; use the same flag with `-ValidateOnly`. Static placement does not attest fresh native discovery or hook trust/execution. Managed restrictions can still require approval even when native writable roots are configured.

## Reply hooks

The installer adds separate Council Reply Standard command hooks at UserPromptSubmit and Stop. UserPromptSubmit adds shared STE rules and the previous reply assessment as additional context. Stop scores last_assistant_message and returns an empty object. It never blocks, retries or edits a reply. Existing MemoryForge and unrelated hooks remain. See the [shared reply standard](../instructions/references/reply-standard.md) for storage, checks and runtime limits. Review/trust changed hooks through the native client; static installation does not prove execution in this desktop session.
