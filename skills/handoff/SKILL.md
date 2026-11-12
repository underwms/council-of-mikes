---
name: handoff
description: Save a checkpoint or progress summary and maintain current MemoryForge state, durable preferences and historical milestones. Use for checkin, handoff or save-progress requests.
---

# Handoff - Session Memory Management

## Overview
This skill governs the generation of incremental checkpoint summaries and final developer handoffs to prevent context loss and maintain token efficiency between supported client sessions.

---

## 1. Local Cache Target Path
When generating a handoff or session checkpoint, the AI MUST write the summary exclusively to:
- **Local Workstation Cache (Read explicitly at session onboarding)**:
  `C:\Users\munderwood\.council/memory/active_handoff.md`

---

## Current state and durable memory

Maintain current_state.md in the selected private MemoryForge namespace at meaningful task milestones and explicit checkpoints. Keep it concise (about one page, within 5,000 UTF-8 bytes): updated date, current user objective, active/stopped status, verified results with evidence pointers, unresolved items, and relevant next steps. Separate older paused tasks from the current objective. Preserve existing active_handoff.md and append-only history; do not silently overwrite another selected session's state. Never infer permission to resume from saved notes.

Store stable user-confirmed preferences in preferences.md. Keep one-off task outcomes in the backlog and historical handoff. Startup reads current state and bounded preferences first; retrieve older history only when relevant. Lifecycle hooks do not generate or overwrite the semantic summary. When a task completes, update the state to say so rather than leaving an obsolete active objective.

## 2. When to Trigger
*   Whenever the user asks to "checkin," "checkpoint," or "do a progress update."
*   At the end of a session before closing the CLI terminal.
*   Upon completing a major milestone (e.g., refactoring a solution, writing tests, passing validation).

---

## 3. Dynamic Session Heartbeat (Rolling Log)
To guard against abrupt CLI terminal closures (such as clicking the `[X]` button), the AI should maintain a background **Rolling Session Heartbeat** file:
*   **Path**: `C:\Users\munderwood\.council/memory/active_session_backlog.md`
*   **Action**: Every time a file is modified, a test runs, or an API is successfully validated, the AI MUST write a single chronological line describing the action to this file.
*   **Onboarding Integration**: At automatic session startup, read this backlog file to reconstruct the session progress.

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
All products share one private cache and handler. Read the active adapter: Codex uses SessionStart/Stop/Interrupt/PostToolUse, Gemini uses SessionStart/AfterAgent, with client-specific schemas. SessionStart loads bounded current state, preferences and recent semantic milestones, with historical handoff fallback. Heartbeats record lifecycle events and confirmed generic tool outcomes; they do not infer a semantic checkpoint or a test result from assistant prose.

Write the handoff yourself using the format above. Record concise milestones when their facts are known. If the cache is not writable under the current permission profile, report that limitation and do not save private state into a repository. Do not bypass the protected path through another tool.

For manual recovery with a working native shell, use `node "C:\Users\munderwood\.council/scripts/council-codex.mjs" onboard --workspace "C:\Users\munderwood\workspace_root"`. Do not parse Codex private databases or treat its transcript format as a stable API.
