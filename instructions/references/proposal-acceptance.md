# Explicit user acceptance of knowledge proposals

The user chose explicit approval of each proposal. The daily agent may propose revisions but must never accept them automatically. These commands operate on a saved finalized proposal across chats/days without reopening its completed daily run. They do not authorize external messages or Git operations. With [upward propagation](upward-propagation.md) configured, a completed acceptance saves parent-review work for the next daily check; it does not execute parent model work or approve a parent revision.

## Human workflow

The user can ask to see pending proposals, review a named one, accept/reject the displayed version, or amend it. Present a concrete review before an acceptance request: all target paths/operations, material changes, exact resulting content, uncertainty and validation issues. Use the preview/history links and opened evidence. Do not claim a hash proves interpretation or that merely displaying a summary proves the user reviewed every word.

Approval covers the shown version or a precisely specified amendment the user explicitly asked to apply. Otherwise prepare an amended version and obtain approval once for that content. Explicit approval of a displayed set can cover each listed version; it does not become standing approval of future proposals. Implementing this workflow is not approval of live knowledge changes.

The CLI requires authorization: explicit-user and a matching review_sha256. This is the invoker's recorded assertion of user approval, not independent human authentication or a signed approval service. The agent must derive it from the actual user instruction, never invent it or treat an earlier maintenance authorization as content approval.

## Commands

Use node scripts/council-codex.mjs daily ACTION --workspace WORKSPACE --chat OBSERVED_CHAT_ID --model codex|gemini --record ABSOLUTE_UTF8_JSON_PATH.

| Action | Record | Result |
|--------|--------|--------|
| proposal-list | Optional status pending/accepted/rejected/failed/all, limit (1-200), offset | Bounded page plus total and unreadable-record failures; pending is default |
| proposal-review | run_id, item_id | Frozen review_id/review_sha256, proposal, target plan, validation issues and preview_path |
| proposal-decide | review_id, review_sha256, decision accept/reject, reason, authorization explicit-user | One-shot decision receipt and, for a valid accept, approved knowledge writes |
| proposal-status | target | Direct-target pending/failed review and accepted-version drift; no-pending-review is not a truth/freshness certificate |

Reviews are bound to workspace, proposal bytes and observed target/source state. A changed draft or materially changed review inputs produce a fresh review identity. Previously generated source artifacts stay editable before decision; the approval binds a frozen snapshot. Editing the preview or frozen files does not amend the executable proposal. Amend stage-02 content and prepare a new review. Original generated proposals and original target content are archived going forward; older records may have only the version captured during review preparation.

## Validation and application

Before accepting, the tool verifies the current proposal matches the reviewed bytes, the changed architecture document still matches its recorded version, source/screening snapshots and consulted knowledge remain valid, targets match their proposed before hashes, and applicable mainline-status is current. No local feature branch/dirty-source check is substituted for integrated-mainline freshness. A stale proposal cannot overwrite newer knowledge. Rejection can close an otherwise well-formed proposal with stale supporting sources or targets, because it applies no knowledge content.

Targets in this local pass are Markdown knowledge documents and CONTEXT indexes under domain/pod .memory, or the existing central memory/knowledge collection. Maintenance state, application files, executable files and central collection tools/workflows/baseline history are excluded. Use separate authorized maintenance for tooling or source-inventory format changes. The agent includes necessary index edits in the proposal; scripts never invent unapproved routing changes. New notes must be reachable from their owning CONTEXT index via existing/proposed index links. This checks structural discoverability, not semantic classification.

Accept writes the exact reviewed text. Retire preserves the prior content by hash and writes the reviewed Status: retired tombstone at the existing path. It does not delete history or silently keep the retired claim as current. Index placeholder statements and active/historical labels should be corrected in the proposed text where needed. Source/proposal/target identities, actor/chat digest, approval assertion and per-file progress are retained in the decision receipt. No footer is appended to approved text without appearing in the review.

## Failure and concurrency policy

A proposal item gets one terminal decision attempt, persisted as failed/completion-not-recorded before any knowledge writes. Accepted, rejected or failed items are not automatically retried, reopened or replayed. Preparing/reading a review is not an acceptance attempt. Amendments are supported before a terminal decision; editing a terminal item's old output does not reopen it.

Per-target locks protect overlapping writes; they are never reclaimed as stale. Only locks owned by the current completed/failed invocation are released normally. Other independent target sets can proceed. Several document replacements are not a filesystem-wide transaction: a failure may leave some approved text applied and other files untouched. The receipt remains failed, preserves intended targets/progress and archives, and retrieval qualifies those targets. There is no automatic rollback or recovery. If final receipt storage is unavailable, the earlier default-failed record remains; the tool must not claim success.

A later distinct explicitly accepted version can supersede an older failed target qualification when its resulting hash matches the current file. Old receipts remain history. Pending proposals are not silently closed by another acceptance. Conflicting equal-time accepted versions remain qualified conservatively. Rejected proposals do not establish that existing knowledge is correct.

## Use during retrieval

For knowledge participating in the configured workspace maintenance collection, call proposal-status for the relevant Markdown note/index before relying on it. Needs-review means a pending proposal, incomplete acceptance, ledger problem or mismatch with the latest accepted version needs qualification. Inspect relevant primary evidence or explain the gap; do not present a proposal or partial application as established knowledge. Routing indexes can still be used to navigate supported unaffected material. Continue the user's task within supported scope; do not start an acceptance conversation merely because a note was retrieved.

Proposal status does not replace source/mainline freshness, scope, correction history or the note's own retired/superseded/candidate status. Explicit namespaces with their own nonparticipating collection follow their own retrieval contract. Direct-target status remains distinct from parent_review returned by proposal-status. Configured upward propagation persists and qualifies collection-level parent review through its separate procedure. It does not implement arbitrary claim dependencies.

## Approval across entry points

Evidence confirmation and knowledge publication are separate decisions. Review candidates, direct capture and legacy PR records cannot bypass exact-version approval of maintained knowledge changes. Prepare a draft and use the supported proposal path. If that path cannot represent the change, report application as pending; do not write accepted notes through another route. Daily architecture drift is the current configured source of knowledge proposals, not a requirement for a developer to perform PR reconciliation.

After successful application, follow the [daily completion checks](daily-maintenance.md#completion-evidence). Record retrieval verification separately from the immutable application receipt. A failed retrieval check leaves a new open issue; it does not reopen the acceptance attempt.
