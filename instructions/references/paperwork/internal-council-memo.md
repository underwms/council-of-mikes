# Internal Council Memo

Use the [Council Paperwork shared core](CONTEXT.md) for assignments, decisions, findings and handoffs between Council roles.
Use this template within an existing task artifact when possible. Do not create a second summary of the same result.
Suggested private location: selected task/namespace paperwork/{memo_id}.md, unless an existing artifact already owns the record.

## Template

```markdown
# Internal Council Memo

ID: <task-local memo ID>
Version: <version or content fingerprint>
Task/namespace: <selected identity>
Purpose: <assignment | decision | finding | handoff>
From: <actual actor and role; inline or separate actor>
To: <intended consumer>
Status: <assigned | ready-for-review | reviewed | blocked | handed-off>

## Request and authority
<Purpose, approved scope, applicable rule references, allowed changes and approval limits.>

## Inputs
| Source | Exact version | Required section | Reason |
|--------|---------------|------------------|--------|
| <path or location> | <revision or SHA-256> | <scope> | <why needed> |

## Work and result
<Requested action and completion checks. On return, link the saved output and exact version.>
<Separate observed facts, proposals and approved decisions. Mark unfinished work explicitly.>

## Review and evidence
<Exact version reviewed, checks actually run, findings and result. Use not-run when applicable.>

## Open items and handoff
<Unknowns/blockers, next action, current responsible role and intended recipient.>
<Record ownership acceptance when observed. Preserve paused work and approval requirements.>
```

## Short form

For small work, use one compact record with ID/version, from/to, purpose/authority, versioned inputs, result/evidence and next action.
Required information can be linked from an existing artifact. Omit empty sections, not material constraints or uncertainty.
An assignment can leave result/review pending. Complete those fields when returning the work.

## Review return

A reviewer can return a memo that references the writer's artifact by path and exact version.
Use stable finding IDs and record outstanding, resolved, withdrawn or superseded findings with reasons.
Follow the existing [review contract](../review-knowledge.md) for revision-bound findings and evidence.
No findings in an inspected scope does not establish exhaustive correctness.
