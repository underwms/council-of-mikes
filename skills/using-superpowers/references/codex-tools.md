# Codex Tool Mapping

Use tools actually exposed by the current session:

| Skill reference | Codex equivalent |
| --- | --- |
| Skill / activate_skill | Read applicable SKILL.md and relevant references; native discovery lists metadata |
| Read / Write / Edit | Native filesystem tools or apply_patch |
| Bash | Native shell execution; use PowerShell on this Windows workspace |
| Task | Native spawn_agent when the workflow requests delegation and it is available |
| Wait for agents | Native agent waiting tool; exec-cell wait is a separate operation |
| TodoWrite | Native plan tracking when available; otherwise maintain a concise checklist |

Do not assume a feature flag or unavailable tool exists. Check the current runtime before using delegation. Council skills represent specialist instructions; merely installing them does not start agents.

Use each independent repository's directory for builds, tests, and Git commands. Read Git/worktree state before branch operations. Follow the session's permissions; do not bypass a blocked shell or protected path through another execution mechanism.


## Council lifecycle and validation

Use `node "__COUNCIL_ROOT__/scripts/council-codex.mjs" onboard` for bounded cache recovery and `validate` for the Codex static audit when the native shell works. Run the required PowerShell workspace validator separately. A hook definition requires Codex trust review and real runtime verification.

Skill metadata enables discovery; full instructions require a file read. Node filesystem tools may read permitted files and test JavaScript modules directly. They must not spawn a shell to bypass blocked native command execution or write protected paths. Read central `rules/workspace.md` under the configured Council root; it supplies guidance rather than Codex executable policy. Question-tool availability and clickable file-reference syntax are defined in the central Codex adapter.
