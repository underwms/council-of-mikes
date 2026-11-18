# Upward knowledge propagation

An explicitly accepted child version can affect a parent explanation. Propagation persists a request to evaluate that possibility; it does not automatically copy text or establish parent truth. Follow [04-propagate](../memoryforge/stages/04-propagate/CONTEXT.md) for assigned semantic work. The user approved this local design on 2026-11-16.

## Routes and ownership

Optional maintenance config propagation contains enabled: true and collections: [{root, parent}]. Each root is a workspace-relative collection directory ending in /.memory. Parent is another registered root or null for a terminal collection. Roots are explicit ownership metadata, not an ontology of facts or inferred service dependencies. Duplicate/overlapping roots, unregistered parents and cycles fail validation. Council private pilot notes have no invented pod identity: unmapped accepted targets are reported by propagation-list and the acceptance result.

The local configured hierarchy is Shipping, Administration/Utilities, Processing and Sourcing -> Order Management domain -> stop. Domain/pod .memory owns knowledge; domain .memory/maintenance owns queue, receipts and snapshots. Council owns canonical facilitator scripts/contracts.

## Acceptance and persistence

After a complete accepted decision is durably stored, scripts/council-propagation.mjs records a one-shot enqueue receipt at propagation/enqueues/{source_item_id}.json, initially failed/completion-not-recorded. It saves an immutable event under propagation/events/{event_id}.json for each accepted target with a configured parent. Event identity binds source acceptance bytes, target and parent; each event carries accepted before/after snapshot identities. Rejected/failed/partial acceptances create no accepted propagation work. Index edits can require screening too; they do not promote a claim automatically.

Acceptance returns propagation disposition separately. An enqueue failure does not undo or relabel accepted knowledge. A missing/failed enqueue receipt for an acceptance marked propagation_expected remains visible through status/listing, including a crash between acceptance and enqueue. Never repair, requeue or backfill those failures. Repeated enqueue invocation does not create another attempt. Storage failure before any marker can be written must be reported by the caller; it cannot promise durable work was created.

No network access or model work starts during acceptance. No historical accepted proposals are backfilled when enabling this feature.

## Daily processing

The first chat's existing daily claim assigns events queued on an earlier Eastern calendar day. A same-day acceptance waits for the next eligible daily claim even if the daily check has not yet run. A late acceptance is not appended to an already running/completed claim. With no chat, work waits. Assignment happens regardless of architecture document changes and is retained through mainline refresh/document scan. Finish those source stages before semantic processing.

The assignment creates propagation/attempts/{event_id}.json as a default-failed attempt before publishing its normal work item. The daily receipt lists propagation_items alongside document items. Source_kind propagation packets route to their parent index and this contract, then reuse ordinary stages 01-screen and 02-reevaluate. A missing parent index or stale/unavailable evidence is a failed investigation; do not fabricate a route or conclusion. No-impact and no-revision-needed preserve rationale without changing knowledge.

Scripts validate accepted source bytes, receipt identity, current child bytes, immutable snapshots, configured routes, original architecture-document identity and applicable current integrated-mainline freshness. Recursing source lineage is bounded and rejects cycles. They do not decide semantic impact. Parent screening/reevaluation must record the owning parent index among consulted knowledge. Proposed targets must remain in the configured parent collection, including after an editable proposal is amended.

Each event has at most one processing attempt. Failed/interrupted assignments or semantic work are not dispatched again. Default-failed historical attempt markers remain; the work/decision receipts show subsequent terminal disposition where recorded. There is no recovery worker, automatic retry, rollback or lock reclamation.

## Parent proposals and later acceptance

Parent proposals use the existing [explicit acceptance procedure](proposal-acceptance.md): show concrete content, obtain the user's decision and apply only the reviewed version. Revalidate child/source lineage and consulted/target versions before publication. Child approval never implies parent approval. A parent acceptance can queue its own configured parent; terminal roots enqueue nothing. Current local configuration terminates at Order Management. Sibling propagation, arbitrary dependencies, new fact schemas and project-level collections are outside this implementation.

Proposed parent content should preserve inspectable provenance: link the accepted child note and its pinned evidence/version, and cite relevant primary sources for the higher-level explanation. Distinguish the observed child behavior from the parent's synthesis and its scope/uncertainties. A queue entry, acceptance hash or model-generated summary alone is not evidence for a broader domain claim. Scripts enforce identities and scope; the agent remains responsible for this reasoning and evidence quality.

## Inspection and retrieval

Use the common Council CLI daily actions with --workspace, --chat, --model and --record ABSOLUTE_UTF8_JSON_PATH:

| Action | Record | Result |
|--------|--------|--------|
| propagation-list | Optional limit 1-200 and offset | Event page, total, invalid-record failures and failed/unmapped enqueue notices |
| propagation-status | target knowledge Markdown path | Parent-review qualification for that collection |
| proposal-status | target knowledge Markdown path | Existing direct-target status plus parent_review |

Waiting, uncompleted same-day work and unaccepted proposed revisions qualify parent review. Interrupted past-day work and failed investigations/enqueues qualify it as failed. No-impact/no-revision-needed and explicit accepted/rejected parent decisions close that event's review. Rejection does not prove the existing parent explanation correct. An index with pending review may still navigate unaffected supported material; do not declare every claim false or stale solely from a collection-level queue item. Check relevant source evidence and explain the qualification when material.

Do not infer specific claim dependencies from this status. Existing direct-target drift and pending proposal checks remain separate. Terminal old failed events remain historical qualifications in this local pass; a later correction does not silently close them. Unreadable queue/history is a qualification, not evidence that nothing is pending. Listing/status commands inspect records; they never reexecute them.

## Unresolved failures

Apply the [daily failure disposition procedure](daily-maintenance.md#failure-disposition-and-replacement-investigation). A separately authorized replacement can resolve an evidence question, but cannot replay an old event or erase its failed status. Report successful correction and remaining historical status separately. New recovery tooling requires its own approved design and verification.
