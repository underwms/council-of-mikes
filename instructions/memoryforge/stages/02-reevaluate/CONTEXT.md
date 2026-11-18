# 02 Reevaluate and propose knowledge revisions

Council Paperwork form: **ICM-02 Knowledge Reevaluation**. Follow the [shared form mapping](../../../references/paperwork/memforge-icm-forms.md). Use the existing records below; preserve their schemas, authority and attempt rules.

## Inputs

| Source | File/Location | Section/Scope | Why |
|--------|---------------|---------------|-----|
| Policy | ../../../references/daily-maintenance.md | Execution policy and commands | Assignment, submission and failure rules |
| Quality reference | ../../references/reevaluation.md | Full file | Investigation and proposal rules |
| Previous stage | Domain maintenance stages/01-screen/output/{item_id}.json, via daily packet stage reevaluate | Current saved assessment and fingerprint | Authoritative handoff, including human edits |
| Working evidence | Packet before/after snapshots | Cited lines; expand only as needed | Verify source change |
| Knowledge | Packet knowledge index and routed domain/pod notes | Relevant sections and evidence only | Assess existing explanation |
| Primary evidence | Sources referenced by affected knowledge | Relevant contract/code sections when necessary | Resolve questions architecture summaries cannot establish |

## Process

1. Obtain a reevaluate packet. Stop if screening is missing, invalid or none. Use the persisted assessment, never recollection from chat.
2. Investigate relevant knowledge and evidence. Record consulted file fingerprints and remaining uncertainties.
3. Produce proposed revisions or explain why no revision is needed. Do not force an edit merely because screening found potential impact.
4. Run the audit below and submit daily finish once, binding the exact screening_sha256 read. Output remains a proposal; [acceptance](../03-accept-proposal/CONTEXT.md) requires a separate explicit user decision. If execution fails, record failed once and continue independent items.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Reevaluation | Domain maintenance stages/02-reevaluate/output/{item_id}.json | JSON; decision, rationale, evidence identities, proposal when applicable |
| Consumed handoff evidence | Domain maintenance snapshots/{screening_sha256}.json | Exact bytes consumed, script-preserved |
| Terminal execution receipt | Domain maintenance work/{item_id}.json and .final | Script-owned; never edit or reclaim |

## Checkpoints

| After Step | Agent Presents | Human Decides |
|------------|----------------|---------------|
| 4 | Reviewable proposal or no-revision-needed explanation | Whether to accept a knowledge change in a separate explicit action; no automatic pause/resume queue |

## Audit

| Check | Pass condition |
|-------|----------------|
| Handoff | Current persisted screening was read and its exact hash is recorded |
| Investigation | Relevant existing knowledge and necessary primary evidence were consulted |
| Scope | Targets are knowledge documents; maintenance state and application code are excluded |
| Accuracy | Proposed behavior, observed source behavior and deployed behavior remain distinct |
| Proposal | Exact create/revise/retire edits, reasons and uncertainties are included, or no revision is justified |
