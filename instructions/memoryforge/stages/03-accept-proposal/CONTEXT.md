# 03 Explicit proposal acceptance

Council Paperwork form: **ICM-03 Proposal Review and Decision**. Follow the [shared form mapping](../../../references/paperwork/memforge-icm-forms.md). Use the existing records below; preserve their schemas, authority and attempt rules.

## Inputs

| Source | Location | Section/Scope | Why |
|--------|----------|---------------|-----|
| User request | Current chat | Exact proposal/version or displayed set and decision | Acceptance authority |
| Procedure | ../../../references/proposal-acceptance.md | Full file | Review, version, publication and failure rules |
| Working proposal | Daily finalized proposed work item and stages/02-reevaluate/output/{item_id}.json | Selected item only | Reviewable candidate, including requested amendments |
| Frozen review | proposal-review response and preview_path | All affected targets, proposed content, history links and issues | Concrete result for user review |
| Evidence | Referenced snapshots, relevant notes and mainline freshness | Applicable source/target versions only | Confirm eligibility before applying |

## Process

1. On a user request, list pending proposals or select the named item. Opening a chat, daily onboarding, retrieving knowledge or implementing acceptance tools is not approval of a proposal.
2. Prepare a review. Present its summary, all target operations, material before/after changes, uncertainties and any validation issues. The preview contains exact resulting content and prior-version links; read the relevant content rather than inferring it from hashes.
3. The user accepts, rejects or requests amendments. Amend the editable stage-02 proposal only within the user's request, then prepare a fresh review. Get approval of the resulting content unless the user already explicitly approved that precise amendment and application. A displayed set may be approved together; unknown future proposals are never included.
4. Submit proposal-decide with the exact review identity/fingerprint and explicit-user authorization assertion. Accept rechecks source, applicable integrated-mainline freshness, consulted knowledge, targets and routing, then applies only the approved plan. Reject changes no knowledge.
5. Report the actual disposition. Failed attempts remain failed; do not retry, reclaim locks or repair partial application. Report the acceptance result and its separate propagation scheduling disposition. Configured successful acceptance queues parent work automatically; never execute that parent review immediately or infer parent approval. Stop after this item and continue independent work.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Review and preview | Local proposals/reviews/{review_id}.json and stages/03-accept-proposal/output/{review_id}.md | Frozen version and readable presentation |
| Decision/application history | Local proposals/decisions/{item_id}.json | One-shot default-failed receipt, authority assertion, hashes and progress |
| Historical versions | Local snapshots/{sha256}.md or .json | Content-addressed prior/proposed versions |
| Accepted knowledge | Reviewed Markdown targets and index edits | Exact approved resulting text; retirement is a reviewed tombstone |

## Checkpoints

| After Step | Agent Presents | Human Decides |
|------------|----------------|---------------|
| 2 or amended review | Concrete target/content changes and evidence/validation limits | Accept this version, reject it, or amend before deciding |

## Audit

| Check | Pass condition |
|-------|----------------|
| Authority | User explicitly approved this proposal version or the specified displayed set |
| Identity | Workspace, proposal version and review fingerprint match the reviewed result |
| Source | Relevant evidence and integrated-mainline freshness checks pass; feature edits are not a source |
| Scope | Only knowledge Markdown/index targets; no application code, tools, workflow instructions or baseline history |
| Routing/history | New notes are reachable from their owner index; prior content and decisions remain inspectable |
| Outcome | Accepted only after all writes verify; partial application stays failed and visible |
