# gemini adapter

Canonical Council: __COUNCIL_ROOT__.

Gemini CLI loads profile .gemini/GEMINI.md and its pointer to the shared instructions. User skills use profile .gemini/skills or .agents/skills aliases, all linked to the same canonical packages under __COUNCIL_ROOT__\skills. Use activate_skill and the native delegation tools actually available. Hooks register in profile .gemini/settings.json. SessionStart and AfterAgent map to the common memory handler; Gemini timeout values are milliseconds. Never reuse a Codex hook schema or Gemini auto-allow policy in another product.

## Operational doctrine & tool boundaries

- **Tool Sandboxing**: Gemini CLI built-in file tools (`read_file`, `write_file`, `replace`) are sandboxed to the active workspace. To inspect or read files outside the active workspace (such as canonical Council instructions or user settings), use PowerShell `Get-Content -LiteralPath "<path>"` via `run_shell_command`.
- **Shell Execution**: Gemini CLI executes Windows shell commands via `powershell.exe`. Ensure automated commands are compatible with Windows PowerShell. Keep commands direct and atomic without unsafe subexpressions.
- **Code & File Searches**: Use `rg` if available; otherwise use PowerShell `Select-String` or `Get-ChildItem`.
- **Import Syntax**: Gemini CLI natively supports `@<path>` file imports within access boundaries. To prevent unintended import resolution in documentation and prose, enclose literal `@` references (such as `` `@file` ``) in inline code backticks.
- **Autonomous Tool Execution**: Routine development tool permissions are configured in `~/.gemini/policies/auto-allow.toml` (linked to `adapters/gemini/policies/auto-allow.toml`).

## Shared source configuration

Read manifest.json and this adapter's JSON descriptor. Source policy and exclusions are user-scoped, across development workspaces. Use central exclusions/global.ignore for explicit discovery. Read docs/source-contract.md for native configuration fragments, their effective limitations, and the source audit commands. The source reconciliation does not overwrite live user-profile settings.

Existing hook configuration is preserved. Optional explicit --memory-scope workspace-session --session <simple-name> uses a workspace/session namespace below central memory, shared by all model actors. Unscoped saved handoffs and currently configured hooks keep their existing storage default.
