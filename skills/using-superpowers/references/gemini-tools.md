# Gemini CLI Tool Mapping

Skills use Claude Code tool names. When you encounter these in a skill, use your platform equivalent:

| Skill references | Gemini CLI equivalent |
|-----------------|----------------------|
| `Read` (file reading) | `read_file` |
| `Write` (file creation) | `write_file` |
| `Edit` (file editing) | `replace` |
| `Bash` (run commands) | `run_shell_command` (runs via PowerShell on Windows; Unix commands/Bash are not natively available) |
| `Grep` (search file content) | `grep_search` |
| `Glob` (search files by name) | `glob` |
| `TodoWrite` (task tracking) | `write_todos` |
| `Skill` tool (invoke a skill) | `activate_skill` |
| `WebSearch` | `google_web_search` |
| `WebFetch` | `web_fetch` |
| `Task` tool (dispatch subagent) | `invoke_agent` (see [Subagent support](#subagent-support)) |

## Subagent support

Gemini CLI supports subagents natively via the `invoke_agent` tool. Use the built-in `generalist` agent to dispatch any task — it has access to all tools and follows the prompt you provide.

When a skill says to dispatch a named agent type, call `invoke_agent` with the `agent_name` set to `"generalist"` (or specialized subagent like `"codebase_investigator"`) with the full prompt from the skill's prompt template:

| Skill instruction | Gemini CLI equivalent |
|-------------------|----------------------|
| `Task tool (superpowers:implementer)` | `invoke_agent` with `agent_name="generalist"` using the filled `implementer-prompt.md` template |
| `Task tool (superpowers:spec-reviewer)` | `invoke_agent` with `agent_name="generalist"` using the filled `spec-reviewer-prompt.md` template |
| `Task tool (superpowers:code-reviewer)` | `invoke_agent` with `agent_name="generalist"` (or specialized codebase_investigator/bundled agent) using the filled review prompt |
| `Task tool (superpowers:code-quality-reviewer)` | `invoke_agent` with `agent_name="generalist"` using the filled `code-quality-reviewer-prompt.md` template |
| `Task tool (general-purpose)` with inline prompt | `invoke_agent` with `agent_name="generalist"` using your inline prompt |

### Prompt filling

Skills provide prompt templates with placeholders like `{WHAT_WAS_IMPLEMENTED}` or `[FULL TEXT of task]`. Fill all placeholders and pass the complete prompt as the `prompt` parameter to `invoke_agent`. The prompt template itself contains the agent's role, review criteria, and expected output format — the subagent will follow it.

### Parallel dispatch

Gemini CLI supports parallel subagent dispatch. When a skill asks you to dispatch multiple independent subagent tasks in parallel, invoke the `invoke_agent` tool multiple times in the same turn. Keep dependent tasks sequential (using the `wait_for_previous` parameter), but do not serialize independent subagent tasks.

## Additional Gemini CLI tools

These tools are available in Gemini CLI but have no Claude Code equivalent:

| Tool | Purpose |
|------|---------|
| `list_directory` | List files and subdirectories |
| `save_memory` | Persist facts to GEMINI.md across sessions |
| `ask_user` | Request structured input from the user |
| `tracker_create_task` | Rich task management (create, update, list, visualize) |
| `enter_plan_mode` / `exit_plan_mode` | Switch to read-only research mode before making changes |
