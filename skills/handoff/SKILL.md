---
name: handoff
description: Save a checkpoint or progress summary and maintain selected task state, durable preferences and historical milestones. Use for checkin, handoff, save-progress or contextual pause/pin requests.
---

# Handoff - selected task memory

Read the [startup and task-selection contract](../../instructions/references/startup-context.md) for identity, selection, status and storage. Use the [review and knowledge contract](../../instructions/references/review-knowledge.md) for candidate evidence and daily knowledge follow-through.

Use [Council Paperwork](../../instructions/references/paperwork/CONTEXT.md) for role handoffs. The selected task snapshot remains the canonical startup summary; a memo must not become a competing current-state record. Link exact artifact versions, evidence, blockers and the next responsible role. Saved memos do not authorize resumed work.

At a meaningful milestone or explicit checkpoint, save a concise summary: date, objective, current status, verified results and evidence paths, limitations, pending work and next actions. Keep separately stopped work explicit. Capture pending PR record paths, reviewed revisions, triggers and owners. Saved history is not permission to resume.

For a registered task, write a complete private record (id, title, summary, state and project fields) and use tasks save. The catalogue snapshot is its canonical startup summary, at most 5,000 UTF-8 bytes. Bind the current observed chat ID when the user selects that task. If Start fresh led to meaningful work, save a new task and bind it; do not re-use an unrelated old task. For an explicitly selected workspace/session namespace, maintain current_state.md there instead; preserve existing active_handoff.md and append verified history. Do not default to the legacy global handoff or another session's state.

Keep stable user-confirmed preferences in the shared preferences.md, with task-specific detail in task state. Store private scratch/evidence in the selected namespace; never in service repositories. Record semantic milestones rather than one model-authored line for every tool action. Generic native lifecycle hooks remain separate and cannot infer test success or write semantic state.

When the user says pause/park/put aside, checkpoint first and explicitly mark paused with the reason. In this user's agreed conversational usage, "pin it" checkpoints/pauses work when that intent is clear. Explicit sidebar pinning only changes visibility; ask if ambiguous. A saved checkpoint does not otherwise change status. App closure, chat switching and inactivity do not pause. Selecting a paused task restores context only; explicit resume is required before continuing it.

Read back the saved record/summary and verify the intended namespace, task status, binding and evidence. Run checks appropriate to changed artifacts before reporting success; do not claim application, hook-runtime or workspace qualification from a successful write. If storage is unavailable, report the specific gap without writing private state into a repository or silently switching namespace.

Follow the [shared Council instructions](../../instructions/shared.md) and active adapter. Use native thread tools for actual sidebar operations only when requested; task status operations do not pin, archive or message a chat.
