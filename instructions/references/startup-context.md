# User startup and task selection

## Startup contract

Every supported chat receives stable user preferences and the shared knowledge index. Task state is selected for that chat; a new chat must not inherit the legacy shared current_state.md, handoff or backlog automatically. The context service supplies data, not authorization to resume old work.

For user chats, run node "__COUNCIL_ROOT__/scripts/council-codex.mjs" onboard when native startup context was not supplied. For Codex the current CODEX_THREAD_ID/CODEX_SESSION_ID is the fallback binding identity; use --chat with an observed native ID when necessary. Other clients need an observed ID supplied explicitly. Never infer a chat ID from a folder name or another chat. Explicit --memory-scope workspace-session --session NAME remains authoritative and bypasses task binding.

On new unbound chats, present up to three relevant saved tasks with title, project, status, last activity and brief summary, plus Start fresh. Read the metadata supplied by onboard/tasks list. Prefer a native project ID (--project) or registered project-root match; projectless/no-match chats get recent saved tasks across projects. Do not load candidate state before selection. If the user has already named the task or explicitly starts a new unrelated assignment, treat that as the choice rather than interrupting with a redundant menu. Never silently adopt another task based on recency.

When available, the native app list_threads tool can enrich the suggestions with recent chats and project IDs. Preserve returned titles verbatim and distinguish app chat activity from Council task status: idle is not paused. Native app metadata is not ingested by a shell hook. Do not scrape native databases, automatically import every transcript, or claim CLI access to app-only tools. If the user selects an unregistered chat, inspect it through read_thread before creating a bounded task record; do not mark a task paused from an idle flag.

After selection, tasks select stores a per-client/chat binding and onboard loads only that task snapshot. Start fresh stores a persistent fresh binding so resumes/compaction do not reopen the menu or restore old work. A fresh meaningful assignment can then be saved as a new open task and bound to the chat. Preserve any explicitly selected namespace.

## Delegated worker startup

A delegated worker already has an assignment. It does not choose a saved task. Start a fresh native worker without inherited chat history when the assignment requires an isolated conversation. Required system, developer and host rules remain present; this is not file access control.

Use the stable-only worker startup path. It reads shared preferences and the shared knowledge index. Task inputs come from the declared assignment. It does not inspect task bindings/catalogues, suggest tasks, restore snapshots or legacy handoffs, or run daily maintenance. Read the assigned specialist and relevant knowledge references on demand.

Codex SubagentStart supplies this context through the existing native hook merger. Its session_id is the parent identity; never use that value to retrieve a worker task. No worker binding or startup receipt is written by this path. User-chat SessionStart keeps its current binding and task-selection behavior.

If native worker startup context is absent, run node "__COUNCIL_ROOT__/scripts/council-codex.mjs" onboard --startup-mode worker. Keep the actual workspace/home/model options when needed. This explicit fallback uses the same stable-only reader. It does not require a chat ID. Do not use generic onboard or ask the user to select a task for a delegated assignment.

Supported startup modes are user (default) and worker. The worker mode rejects task/project/session selectors and workspace-session memory. Declare any required namespace paths as assignment inputs instead of silently replacing the selected scope. Missing required assignment inputs block dependent work.

Native hook trust and actual execution remain separate checks. If automatic worker startup is unavailable, use the worker fallback and report that limit. Do not bypass native trust. Shared helper availability does not verify Gemini native worker startup.

## Persistence and commands

Private memory/task-context.json is the versioned task catalogue. Each record has id, title, summary, state (at most 5,000 UTF-8 bytes), optional project_id/project_root, status, updated_at and bounded transition history. Bindings use hashed chat IDs and distinguish a selected task from Start fresh. Mutations lock and atomically replace this file; corrupt or full catalogues fail closed without replacing historical state.

CLI entry point: node "__COUNCIL_ROOT__/scripts/council-codex.mjs".

- onboard [--startup-mode user|worker] [--chat ID] [--cwd ABSOLUTE_PATH] [--project PROJECT_ID]: bounded startup context. Worker mode rejects project/session/task selectors.
- tasks list [--project PROJECT_ID] [--cwd ABSOLUTE_PATH] [--limit 1-10]: metadata-only suggestions; default three.
- tasks save --record ABSOLUTE_JSON_PATH: create/checkpoint an allowlisted record containing id, title, summary, state and optional project_id/project_root. Preserve project fields in a complete checkpoint. Status cannot be changed through this command.
- tasks select --task TASK_ID --chat CHAT_ID: bind a selected existing task; does not resume it.
- tasks fresh --chat CHAT_ID: persist Start fresh for that chat.
- tasks status --task TASK_ID --status paused --reason USER_REASON: explicit pause.
- tasks status --task TASK_ID --status open --resume true: explicit user-authorized resume of a paused/completed task. Also support blocked and completed statuses; blocked requires a reason.
- tasks receipt [--chat CHAT_ID]: inspect the latest startup-handler receipt, or report not-observed.

Use --model codex or --model gemini for client-specific bindings. With --memory-scope workspace-session, catalogue mutation commands reject instead of silently modifying that selection. Task lifecycle logs and pending artifacts can live under memory/tasks/TASK_ID/. The task snapshot in the catalogue is the canonical selected startup state; do not maintain competing current summaries by accident. The global knowledge index remains shared durable knowledge, distinct from another task's private state.

## Status and pinning

New tasks are open. Closing the app, changing chats or inactivity does not pause them. Mark paused only on an explicit user request to pause/park/put work aside. In the agreed conversational usage, "pin it" means checkpoint and pause when clearly about the work; explicit sidebar pinning changes sidebar visibility only. Ask when ambiguous.

Selecting a paused task restores its context and retains paused status until the user explicitly asks to resume. A checkpoint preserves existing status. Blocked means a specific unmet dependency, not inactivity. Completed records remain historical and are excluded from default recent suggestions. Saving/restoring context never authorizes graph execution, external messages or other historical actions.

## Hook scope and evidence

SessionStart recovers user-level context regardless of cwd, including projectless UI chats. Codex startup/resume/clear/compact/fork match the owned startup hook. Workspace lifecycle logging remains restricted to the configured real workspace subtree; a selected task gets its own lifecycle log there. A Start fresh binding suppresses unrelated lifecycle logging. Generic hooks never author semantic checkpoints or status transitions.

The latest minimal receipt under memory/runtime/ records source, client, time, hashed chat identity and context mode. It establishes that the handler ran; caller surface is not attested. Manually invoking a hook does not prove desktop execution. Keep native trust and source/placement/test evidence separate. Do not bypass native hook trust or replace absent hooks with a background watcher. If receipt writing is blocked, recover context without claiming receipt evidence.
