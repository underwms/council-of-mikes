---
name: handoff
description: Expertise in session memory management, checkpoint generation, and cross-session developer handoffs. Use when asked to checkpoint, checkin, or save progress.
---

# Handoff - Session Memory Management

## Overview
This skill governs the generation of incremental checkpoint summaries and final developer handoffs to prevent context loss and maintain token efficiency between Codex sessions.

---

## 1. Local Cache Target Path
When generating a handoff or session checkpoint, the AI MUST write the summary exclusively to:
- **Local Workstation Cache (Read explicitly at session onboarding)**:
  `__COUNCIL_ROOT__/memory/active_handoff.md`

---

## 2. When to Trigger
*   Whenever the user asks to "checkin," "checkpoint," or "do a progress update."
*   At the end of a session before closing the CLI terminal.
*   Upon completing a major milestone (e.g., refactoring a solution, writing tests, passing validation).

---

## 3. Dynamic Session Heartbeat (Rolling Log)
To guard against abrupt CLI terminal closures (such as clicking the `[X]` button), the AI should maintain a background **Rolling Session Heartbeat** file:
*   **Path**: `__COUNCIL_ROOT__/memory/active_session_backlog.md`
*   **Action**: Every time a file is modified, a test runs, or an API is successfully validated, the AI MUST write a single chronological line describing the action to this file.
*   **Onboarding Integration**: At Codex session onboarding, read this backlog file to reconstruct the session progress.

---

## 4. Checkpoint Standard Format
The generated `active_handoff.md` file MUST adhere strictly to the following structure:

```markdown
# Active Developer Handoff & Session State
**Last Updated**: YYYY-MM-DD
**Current Target Objective**: [Summary of the main objective]

---

## 1. Summary of Completed Work (Session Victories)
- [Chronological bullet points of completed files, tests, and configurations]

## 2. Current Project State & Core Metrics
*   **Repository status**: [Clean/Dirty, Branch Name]
*   **Testing Status**: [Unit, Integration, and Validation statuses]
*   **Environment Integrity**: [Pass/Fail from validate-workspace.ps1]

## 3. Next Session Dev Targets
1.  [Step 1 to continue immediately]
2.  [Step 2]
```

---

## 5. Write Verification
Read back the saved handoff to confirm the intended content. Run the workspace validator directly and the Codex audit; report their actual results. A prior PASS or a successful write does not establish current environment health.

## 6. Model lifecycle integration
All products share one private cache and handler. Read the active adapter: Codex uses SessionStart/Stop/Interrupt/PostToolUse, Gemini uses SessionStart/AfterAgent, and Claude uses SessionStart/Stop. SessionStart loads bounded handoff and backlog context. Heartbeats record lifecycle events and confirmed generic tool outcomes; they do not infer a semantic checkpoint or a test result from assistant prose.

Write the handoff yourself using the format above. Record concise milestones when their facts are known. If the cache is not writable under the current permission profile, report that limitation and do not save private state into a repository. Do not bypass the protected path through another tool.

For manual recovery with a working native shell, use `node "__COUNCIL_ROOT__/scripts/council-codex.mjs" onboard --workspace "__WORKSPACE_ROOT__"`. Do not parse Codex private databases or treat its transcript format as a stable API.
