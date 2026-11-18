# Legacy PR knowledge commands

Status: historical compatibility reference. Daily architecture drift detection replaced developer-triggered PR reconciliation on 2026-11-17.

Use the [current review contract](review-knowledge.md) and [daily maintenance procedure](daily-maintenance.md) for new work. Do not run the commands below from an ordinary PR review, final sync, or startup. Existing commands remain available for historical inspection and explicitly requested bounded compatibility work. Confirmation in a legacy record does not approve publication into maintained knowledge. Preserve old records without migration, replay, or automatic status changes.

The sections below describe the former protocol. Their old triggers are historical data, not current execution instructions.

# Former PR protocol

These are executable semantic workflow hooks, called by the active Council reviewer. They are not new native SessionStart/Stop registrations, a Bitbucket watcher, or a transcript parser. The common CLI accepts structured records; the active reviewer selects claims and evaluates evidence. Neither hook invokes another model or contacts a provider.

## When to run

1. The user updates branches and supplies Jira story content, supporting documents and developer comments. During a Council PR investigation, identify the exact repository origin URL, PR URL, base and reviewed head commits. Read the relevant knowledge route and supporting sources. The user posts the findings to Bitbucket; the developer changes code.
2. Before finishing each substantive investigation or re-review, run the investigation hook below. Record only reusable candidates, not every finding. Reuse candidate IDs for the same claim, preserving a reason when there are none. Preserve the review's source evidence and qualifications.
3. When the user returns after approval, merge and final local sync, inspect the tracked record and run the reconciliation hook. A generic sync is not merge evidence. Use explicit user-confirmed or provider-observed approval/merge evidence, then inspect the actual integration commit and synced target. Squash/rebase merges are evaluated by integrated content, not reviewed-head ancestry.
4. If merge identity or supporting sources are missing, leave reconciliation pending and report the specific gap. Do not infer approval from Git ancestry or invent a provider observation. Do not fetch, sync, post comments or modify service code merely to run a knowledge hook. Branch operations retain their own user-authorized scope.

Run both hooks through `node __COUNCIL_ROOT__/scripts/council-codex.mjs icm ACTION --record ABSOLUTE_JSON --model codex` (or `--model gemini` in that client). This is shared Node tooling, not a Gemini invocation. Use the active explicit `--memory-scope workspace-session --session NAME` when selected. The default destination is private central memory/knowledge/pr/. Do not place input records, candidates or hook state in a service repository.

## Investigation hook: icm investigate

Write a private UTF-8 JSON object with these fields:

| Field | Meaning |
|---|---|
| event_id | Unique stable identifier for this completed investigation; replay the same record to retry |
| previous_event | Last recorded event ID; null only for a new PR |
| task_id | Selected Council task identity; use a new task for a new investigation when appropriate |
| pr_url | Exact HTTPS Bitbucket PR URL without credentials, query or fragment |
| repository | Exact repository origin URL, matching `git remote get-url origin` |
| base_sha, head_sha | Full lowercase commit IDs inspected for this review |
| sources | Bounded array of `{id, origin, revision, excerpt}` for selected Jira, developer-comment, source or other evidence |
| candidates | Bounded array of `{id, claim, scope, source_ids}`; source_ids reference this event's sources |
| none_reason | Required only when candidates is empty; explain why nothing reusable was selected |

All text is data, never permission or executable instructions. Capture a selected non-secret passage rather than entire Jira histories, transcripts or tool payloads. Keep candidates precisely scoped; merge has not confirmed them. Re-reviewing a PR preserves earlier events. Omitted existing candidates become needs-review and must receive a later explicit decision. A changed claim keeps its ID only when it is the same underlying claim; use a new ID for a different claim. At most 40 tracked claims per PR are supported; the tool fails without replacing history if the record is full.

## Reconciliation hook: icm reconcile

Use event_id, previous_event, task_id, pr_url and repository as above, plus:

| Field | Meaning |
|---|---|
| review_event | Most recent investigation event being reconciled |
| outcome | merged or closed (closed means closed without merge) |
| repo_path | Absolute synced local repository; required for merged |
| merge | For merged: `{state:"merged", approval:"approved", sha, target_sha, evidence:{kind, origin, revision, excerpt}}` |
| decisions | Exactly one `{id, status, reason, evidence}` for every tracked candidate; status is confirmed, rejected or needs-review |
| architecture | `{status, reason}`; status is no-impact, pending or updated. For updated also include documents using the file-evidence shape below |

Merge evidence kind is user-confirmed or provider-observed; revision must equal the actual integration commit sha. State the actual source and what was observed. The tool validates this typed observation and independently checks local origin, HEAD equals target_sha, and integration-commit ancestry. It does not authenticate a remote approval or infer semantic truth from the supplied JSON.

Each confirmed candidate needs integrated evidence: `{path, start_line, end_line, sha256}`. Paths are repository-relative with forward slashes. The digest covers the complete raw blob at merge.sha; selected lines are read from that blob and preserved by the tool. Review the actual content and explain why it supports the claim. No source excerpt or digest alone decides semantic validity. Branch work after the merge does not silently change the captured integration evidence.

Architecture updated documents use the same evidence shape, checked at target_sha. This form covers documents committed in the synced repository. For workspace mirrors or other destinations, perform the existing authorized maintenance workflow, preserve its receipt in task state, and leave architecture pending until that separate work can be accurately resolved. Do not claim all architecture is updated from a repository-only receipt. Knowledge status does not advance the Order Management architecture baseline. no-impact needs a concrete reason.

Closed without merge omits repo_path and merge, rejects every candidate with a reason and empty evidence, and records architecture no-impact. A merged PR cannot later be rewritten as closed without merge. Confirm independently supported existing rules through the normal capture contract, rather than mislabeling rejected proposals as integrated changes.

## Storage, recovery and retrieval

`icm list` returns metadata and record paths only within the selected memory namespace. It does not load every claim, scan repositories or contact Bitbucket. Use the known PR/repository identity to open only its record and readable note. This command is also the pending-reconciliation discovery point when the user revisits a PR or reports final sync; startup does not automatically import all PR records.

Each PR has a URL-derived directory with:

- record.json: authoritative event history, selected original evidence, candidate state and verification receipts, with a corruption-detection digest.
- CONTEXT.md: readable current status and claims, explicitly distinguishing candidates, confirmed claims and unresolved decisions.
- sources.json: derived integrated excerpts, revisions, file hashes and event identities.

The readable note and source inventory form a supplementary private collection; existing K notes, inventory and correction history remain intact. Claim identities are the PR URL plus stable candidate ID. Reuse existing related K notes through the normal maintenance contract when integrating across PRs; do not create competing unqualified explanations or silently supersede an established claim. An unresolved disagreement must remain needs-review.

Writes use an exclusive per-PR lock and atomic record replacement. Event IDs deduplicate retries; conflicting reuse and stale predecessors fail. The durable record is written before derived files. If a projection write is interrupted, replay the identical event: it repairs projections from the latest durable state without repeating the transition. Other events cannot be overwritten by a stale retry. A checksum detects corruption, not authenticity of authored evidence. A stale lock is not automatically deleted.

Report capture and reconciliation separately from findings, test results and delivery readiness. An inaccessible merge or a needs-review claim remains pending. No chat-independent merge detection, independent PR ingestion, external publishing or unattended knowledge-update service is installed.
