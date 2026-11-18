# gemini adapter

Canonical Council: __COUNCIL_ROOT__.

Gemini CLI loads profile .gemini/GEMINI.md and its pointer to the shared instructions. User skills use profile .agents/skills aliases (natively discovered by Gemini CLI), all linked to the same canonical packages under __COUNCIL_ROOT__\skills. Redundant .gemini/skills junctions are eliminated to prevent duplicate skill override warnings on startup. Use activate_skill and the native delegation tools actually available. Hooks register in profile .gemini/settings.json. SessionStart and AfterAgent map to the common memory handler; Gemini timeout values are milliseconds. Never reuse a Codex hook schema or Gemini auto-allow policy in another product.

## Operational doctrine & tool boundaries

### Bounded advice and context review

For an advice-only review of Council policy or preferences, read the named authoritative sources and answer from them. The sources are this adapter for native tool/policy semantics, `~/.gemini/GEMINI.md` and central `memory/preferences.md` for personal preferences, and the complete selected canonical skill for specialist guidance. Follow a specific relevant reference only when a material point remains unanswered. Once those sources support the requested conclusions, stop gathering context and return the answer; historical test cases and transcripts are not additional authority. If evidence is missing, identify that limitation. Do not search private work, backups, native caches or unrelated memory to complete the answer.

These discovery boundaries apply to every tool and language, including Node/Python filesystem scripts as well as PowerShell. A failed tool or an empty match does not expand the search scope. Use direct `Get-Item -LiteralPath` on a named directory when checking a junction; recursive content search is unnecessary for path identity.

- **Tool Sandboxing**: Gemini CLI built-in file tools (`read_file`, `write_file`, `replace`) are sandboxed to the active workspace. To inspect or read files outside the active workspace (such as canonical Council instructions or user settings), use PowerShell `Get-Content -LiteralPath "<path>"` via `run_shell_command`.
- **Shell Execution**: Gemini CLI executes Windows shell commands via `powershell.exe`. Ensure automated commands are compatible with Windows PowerShell. Keep commands direct and atomic without unsafe subexpressions.
- **Code & File Searches**: Use `rg` if available; otherwise use PowerShell `Select-String -LiteralPath` on named files or `Get-ChildItem` within the smallest relevant source directory. Read known canonical files directly before searching. PowerShell recursion does not apply `exclusions/global.ignore`: do not recursively search the entire Council root, native client profiles or user home as a fallback. If discovery is needed, select bounded source directories first and prune excluded directories and junctions before descending; filtering results after recursion does not prune traversal. If the bounded search cannot answer the question, state the missing source rather than expanding into private history.
- **Preference Sources**: For native/global preference questions, read the user-owned `~/.gemini/GEMINI.md` and central `memory/preferences.md`, then only relevant references from the selected profile. Their absence from a built-in file tool's workspace does not require a recursive discovery search; use the direct shell read described above.
- **Import Syntax**: Gemini CLI natively supports `@<path>` file imports within access boundaries. To prevent unintended import resolution in documentation and prose, enclose literal `@` references (such as `` `@file` ``) in inline code backticks.
- **Autonomous Tool Execution**: Routine development tool permissions are configured in `~/.gemini/policies/auto-allow.toml`; the canonical policy asset is `adapters/gemini/policies/auto-allow.toml`. The inspected ~/.gemini/policies directory is a junction to the canonical policy directory; the regular policy file beneath it resolves to the same canonical file. Inspect parent links and resolved paths, not only the leaf file type or equal hashes. Editing the canonical policy changes the installed file through that route; do not assume an existing client session has reloaded it.

## Policy scope and personal preferences

The current user policy has a wildcard allow rule for built-in and MCP tools plus broad shell rules; its comments are not a sensitivity or read-only filter. Rules without mode restrictions also apply during plan-mode matching. Preserve the user's existing autonomy settings unless a change is requested. Higher-priority policy, native safety checks, sandbox/OS permissions and session settings remain separate controls; a matching allow rule is neither a guarantee of execution nor authorization for an unrelated task.

Content outside the Council markers in the native GEMINI.md is user-owned and preserved by installer merging. Apply confirmed preferences within their stated scope. A preference for EF Core/PostgreSQL and no new Dapper/Redis does not establish that inherited dependencies were purged or authorize migrations. Review concrete conflicting text within the requested scope; do not overwrite unrelated personal settings.

## Automatic Council startup

Follow the shared startup procedure and [task-selection contract](../instructions/references/startup-context.md) once per session. SessionStart provides user-level stable context outside the configured workspace too; workspace lifecycle logging retains its location guard. Use the common onboard CLI when startup context is absent, including projectless chats. Restore only a bound task or explicit namespace; otherwise offer project-related/recent saved tasks plus Start fresh. Preserve paused status and explicit namespace selection. Recover only missing context after compaction/model changes. Never start the standalone engine during startup.

## Shared source configuration

Read manifest.json and this adapter's JSON descriptor. Source policy and exclusions are user-scoped, across development workspaces. Use central exclusions/global.ignore for explicit discovery. Read docs/source-contract.md for native configuration fragments, their effective limitations, and the source audit commands. The source reconciliation does not overwrite live user-profile settings.

Existing hook configuration is preserved. Optional explicit --memory-scope workspace-session --session <simple-name> uses a workspace/session namespace below central memory, shared by all model actors. Legacy saved handoffs remain preserved. Default startup now uses stable context plus explicit task selection; it does not adopt those handoffs automatically.

## Reply hooks

The installer adds separate Council Reply Standard command hooks at BeforeAgent and AfterAgent. BeforeAgent adds shared STE rules and the previous reply assessment for that turn. AfterAgent scores prompt_response and returns an empty object. It never denies, retries or edits a reply. Timeouts use milliseconds. Existing MemoryForge and unrelated hooks remain. See the [shared reply standard](../instructions/references/reply-standard.md). Check native trust and fresh execution separately from static placement.
