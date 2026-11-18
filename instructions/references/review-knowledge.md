# PR review and knowledge follow-through

Read this contract for PR reviews, Council planning/review, and knowledge capture or daily follow-through. Use only the sections relevant to the task. It governs manual, model-followed work; it installs no watcher, automatic learning, scheduler, or merge hook.

## Review the current revision

1. Establish repository identity, PR URL/number when available, purpose and acceptance criteria, target branch/base SHA and reviewed head SHA. For local work, record branch, HEAD and a diff fingerprint including relevant dirty/untracked scope. If only a pasted excerpt is available, label the review excerpt-only and request missing context only when it affects the conclusion. Never invent repository identities or verification.
2. Retrieve relevant knowledge through the selected private namespace's knowledge index and retrieve contract. Check current-source freshness where that collection requires it. Missing knowledge is a coverage limit, not a reason to invent a prerequisite or block independent review.
3. Inspect the change and enough surrounding code, callers, contracts and tests to explain its behavior. Prioritize defects introduced by the requested change and material unmet requirements. Inherited deviations do not create cleanup blockers. Load the owning specialist for relevant domain questions, including The Prover for test adequacy.
4. Give each substantive finding a stable task-local ID, severity, current location, concrete trigger, consequence, supporting evidence and smallest useful correction or question. Distinguish blocking defects, evidence questions and optional suggestions. Unconfirmed concerns remain questions; do not invent findings to fill a quota. Missing execution is not proof of a defect.
5. On a new head/base or dirty diff, recheck affected conclusions. Record each finding as outstanding, resolved, withdrawn or superseded, with revision and reason. Preserve IDs for the same underlying defect; do not repeat resolved findings under new wording. Reuse unaffected observations only with an explicit applicability reason. Do not silently carry old test passes forward.
6. Lead the result with actionable findings, then review scope, checks actually observed, material gaps and knowledge-capture disposition. If none were found, say no substantive findings in the inspected scope. Do not predict that another reviewer will find zero issues. A review is not authorization to comment externally, approve a hosted PR, merge, push or deploy.

## What deserves durable knowledge

Daily architecture drift detection replaces the developer PR reconciliation step. Use the [daily maintenance procedure](daily-maintenance.md) for configured workspaces. Review candidates can guide later investigation, but cannot establish integrated behavior or approved knowledge. Do not require `icm investigate` or `icm reconcile` to complete a new PR review. Retain useful review evidence in private task state, with its source revision and scope.

Retain a claim when it answers a plausible future question, has reusable consequences, is scoped precisely and has evidence appropriate to its wording. One strong primary source can suffice; repeated comments do not establish truth. Useful families include:

- Domain rules and constraints, including relevant exceptions.
- Ownership boundaries, contracts, dependencies and cross-service behavior.
- Consequential decisions with recorded rationale and accepted trade-offs. Do not infer rationale from code alone.
- Testing or operational discoveries that change future decisions, with fixture and environment limits.

Keep ordinary implementation details, temporary task state, review chatter, untested guesses and redundant copies of canonical rules out of the durable collection. A reusable failure lesson may qualify; the whole failed transcript does not. Record an explicit 'none: reason' when a meaningful review/capture pass yields no candidate; do not create empty notes for every trivial edit.

Separate source observations, observed execution, user-confirmed policy, historical reports and derived interpretations. User-confirmed corporate rules are authoritative in their stated scope without demanding ADR links. Code establishes source behavior at a revision, not business intent or deployment. A merge establishes integration into a target branch, not production behavior. Test results establish only what their assertions and exercised dependencies demonstrate.

## Capture selected candidates

Keep private evidence and records in the selected MemoryForge namespace, never in a service repository or distributable skill. Use that namespace's knowledge index and capture/retrieve/maintain contracts when present. The default collection is memory/knowledge under the central root; do not silently switch an explicitly selected namespace. If no collection exists, preserve bounded candidates in private task state and report the missing destination; do not initialize a knowledge system or use unrelated memory without scope.

Use stable review IDs and candidate IDs (for example F1 and C1 within one PR record). They are separate: a finding may yield no reusable claim, and a candidate may come from correct code. A candidate record under knowledge/candidates/ holds:

- Identity: candidate ID, repository/PR or local-task identity, capture date and responsible role/person.
- Claim: proposed reusable statement, likely future question, scope/exceptions, evidence type and uncertainty.
- Evidence: original location, base/head or source version, file and selected lines; opened excerpt/snapshot with digest where needed. Record command, result, time, tested revision/diff identity and environment/fixture scope for execution evidence. Preserve only non-secret evidence needed for the claim.
- State: candidate, confirmed, needs-review, rejected or superseded; related finding/claim IDs and links. These describe knowledge, not release or review approval.
- Follow-through: merge/review trigger, responsible person/role, next action, and intended note/architecture destination or reason none is needed.

Capture before merge stays candidate for claims about the proposed change. Independently supported existing rules can be recorded as source-confirmed evidence. This does not approve a maintained knowledge write. Keep their evidence separate from the unmerged proposal. Unopened primary evidence must be labeled; historical summaries are leads, not current verification. Never promote every review comment, a passing test name or an approval into fact. Link canonical preferences/rules instead of copying them into notes.

## Daily route to a checked result

1. The daily owner checks configured integrated revisions and refreshes affected architecture documents through the mainline procedure.
2. Document drift starts screening. Potential knowledge impact starts reevaluation against current saved evidence and relevant notes.
3. Reevaluation produces a proposal or an evidence-backed no-revision-needed result. Source confirmation is not user approval.
4. Show the exact proposed content and obtain explicit version-bound approval. Apply knowledge changes only through the proposal acceptance procedure.
5. Verify resulting content, links, evidence identities and a retrieval walkthrough for the affected question. Report incomplete checks separately from successful writes.
6. Queue configured parent review after acceptance. Parent proposals require separate approval. A local completion does not establish parent completion.

The [daily procedure](daily-maintenance.md) owns failure disposition and completion evidence. Missing configuration, unchanged monitored documents, or an unregistered repository does not establish that all PR candidates were assessed. State the coverage gap. Do not invent a daily assignment or silently treat PR records as a second publication route.

## Legacy PR records

The [legacy command reference](icm-pr-hooks.md) supports historical inspection and explicit bounded compatibility work. It is not the current developer workflow. Preserve original candidate states, evidence and receipts. Do not mark old candidates confirmed, rejected or completed merely because the workflow changed. A later relevant daily proposal can cite their evidence after fresh source review. This update does not migrate or backfill old records.

## Role responsibilities

- Architect: retrieve relevant constraints during planning; capture boundaries, decisions and explicitly recorded rationale; report daily knowledge coverage and pending proposals in Council outcomes.
- Gatekeeper: bind findings to the current candidate, challenge evidence and scope, and report daily knowledge disposition separately from readiness.
- Prover: record the behavior actually asserted, tested revision, fixture/dependency scope, command/result and limitations. Distinguish designed scenarios, observed failure, observed pass and unexecuted tests. A substitute-backed test cannot prove unexercised database or deployment behavior. Capture reusable test constraints; retain applicability limits on historical passes. FAIR remains the feature integration/regression standard.
- Coordinator: distinguish story proposals, agreed acceptance criteria and observed implementation. Capture reusable domain constraints, not every story; preserve follow-through ownership without sending issue updates by implication.
- Codex and repository-documentation: maintain one current explanation with evidence and history, assess actual architecture impact, and preserve authorized workspace/child-repository boundaries.
- Handoff: preserve pending record paths, revision identities, daily coverage gaps, owners and next actions; do not promote a candidate or resume stopped work merely because it was saved.

Other specialists use this contract when their scoped work produces reusable discoveries. No candidate is required when nothing merits retention.
