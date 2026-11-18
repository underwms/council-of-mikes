# MemForge ICM Forms

Use the [Council Paperwork shared core](CONTEXT.md) with the existing [MemForge workflow](../../memoryforge/CONTEXT.md).
These are names and completion rules for existing records. They do not add a JSON wrapper, required schema fields or duplicate files.
Commands, paths, validated fields, ownership, approvals and terminal attempt rules remain defined by each stage contract.

## Form catalogue

| Form | Stage contract | Existing authoritative records | Intended consumer |
|------|----------------|--------------------------------|-------------------|
| ICM-00 Mainline Refresh | [00](../../memoryforge/stages/00-mainline-refresh/CONTEXT.md) | mainline-packet, staged replacements, review receipt and refresh execution record | Document scan, then screening |
| ICM-01 Knowledge Impact Screening | [01](../../memoryforge/stages/01-screen/CONTEXT.md) | Assigned packet and stages/01-screen/output/{item_id}.json | Reevaluation for potential impact; otherwise no-impact completion |
| ICM-02 Knowledge Reevaluation | [02](../../memoryforge/stages/02-reevaluate/CONTEXT.md) | Reevaluation packet, stages/02-reevaluate/output/{item_id}.json and consumed-screening snapshot | Proposal review when proposed; otherwise terminal result |
| ICM-03 Proposal Review and Decision | [03](../../memoryforge/stages/03-accept-proposal/CONTEXT.md) | Frozen review/preview and proposal decision/application history | User decision and scoped application; configured propagation queue |
| ICM-04 Parent Knowledge Review | [04](../../memoryforge/stages/04-propagate/CONTEXT.md) | Assigned propagation packet, ordinary ICM-01/02 outputs and parent-review qualification | Separate parent proposal review when needed |

## Shared-core field mapping

| Shared part | Use existing information |
|-------------|--------------------------|
| Identity/version | Workspace/collection, run/item/refresh/review IDs, stage and source/output fingerprints |
| Responsibility | Assigned daily owner or actual proposal-review actor; intended next stage and recorded decision authority |
| Inputs | Packet snapshots/revisions, current saved prior-stage output, relevant knowledge and consulted fingerprints |
| Authority | Current assignment or exact explicit user decision plus the selected stage procedure |
| Work/result | Stage decision, rationale, output paths, evidence, uncertainty and validation result |
| Handoff | Consumed screening_sha256, frozen review identity or other stage-defined version binding |

The linked packet, editable output and script-owned receipt can jointly supply the shared core.
Do not add fields to a validated payload unless its schema explicitly permits them.
Record any necessary extra explanation in the existing permitted rationale/uncertainty fields or one linked task memo.
Do not create a memo when the existing form records already supply the needed information.

## Completion and review rules

- ICM-00 cites pinned integrated source. Publish only registered documentation through its existing command.
- ICM-01 records an evidence-based impact assessment. It does not draft a knowledge revision.
- ICM-02 reads the current saved ICM-01 output and binds the exact screening_sha256 consumed.
- ICM-02 distinguishes proposed revisions from no-revision-needed. Neither outcome self-accepts knowledge.
- ICM-03 requires user approval of the exact reviewed proposal version before acceptance.
- ICM-04 uses accepted child evidence and reviews only the assigned parent collection. Child approval does not approve parent content.

Human edits to permitted work surfaces remain supported before consumption or a fresh review.
A stale fingerprint follows the stage's existing validation and failure rules.
Missing or invalid required evidence prevents dependent completion; preserve the specific gap.
Unresolved uncertainty must remain visible in the proposal and review.
Frozen reviews, consumed snapshots and terminal receipts remain immutable.
No form creates retries, recovery, lock repair, historical replay or automatic approval.
