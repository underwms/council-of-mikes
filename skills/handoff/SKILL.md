---
name: handoff
description: Expertise in session memory management, checkpoint generation, and cross-session developer handoffs. Use when asked to checkpoint, checkin, or save progress.
---

# Handoff - Session Memory Management

## Overview
This skill governs the generation of incremental checkpoint summaries and final developer handoffs to prevent context loss and maintain token efficiency between Gemini CLI sessions.

---

## 1. Local Cache Target Path
When generating a handoff or session checkpoint, the AI MUST write the summary exclusively to:
- **Local Workstation Cache (Ingested on startup by onboard.py)**: 
  `%USERPROFILE%\.gemini\tmp\%USERNAME%\memory\active_handoff.md`

---

## 2. When to Trigger
*   Whenever the user asks to "checkin," "checkpoint," or "do a progress update."
*   At the end of a session before closing the CLI terminal.
*   Upon completing a major milestone (e.g., refactoring a solution, writing tests, passing validation).

---

## 3. Dynamic Session Heartbeat (Rolling Log)
To guard against abrupt CLI terminal closures (such as clicking the `[X]` button), the AI should maintain a background **Rolling Session Heartbeat** file:
*   **Path**: `%USERPROFILE%\.gemini\tmp\%USERNAME%\memory\active_session_backlog.md`
*   **Action**: Every time a file is modified, a test runs, or an API is successfully validated, the AI MUST write a single chronological line describing the action to this file. 
*   **Onboarding Integration**: If Gemini is closed abruptly, `onboard.py` will read this backlog file to reconstruct the session progress.

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
After writing the handoff file, the AI MUST run `validate-workspace.ps1` to ensure no broken relative links or wikilinks were introduced in the markdown files, guaranteeing 100% environment health.
