# 01 Screen for knowledge impact

Council Paperwork form: **ICM-01 Knowledge Impact Screening**. Follow the [shared form mapping](../../../references/paperwork/memforge-icm-forms.md). Use the existing records below; preserve their schemas, authority and attempt rules.

## Inputs

| Source | File/Location | Section/Scope | Why |
|--------|---------------|---------------|-----|
| Policy | ../../../references/daily-maintenance.md | Execution policy and commands | Once-only assignment and failure handling |
| Quality reference | ../../references/screening.md | Full file | Decision and evidence rules |
| Working evidence | daily packet response, stage screen | Assigned identity and before/after lines only | Compare actual change |
| Knowledge routing | Packet knowledge_index or domain .memory/CONTEXT.md | Relevant route only, then affected note sections as needed | Judge possible knowledge impact |

## Process

1. Obtain the assigned packet. Compare meaning and scope using the quality reference.
2. Write a screening assessment with evidence and consulted knowledge identities. Do not draft revisions.
3. Run the audit below, then submit daily screen once. This writes the local stages/01-screen/output/{item_id}.json handoff.
4. For none, submit daily finish with no-impact. For potential, load the next stage contract and its saved handoff. No automatic human pause is required by this configured workflow. If any step fails, record failed once and continue independent items.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Impact assessment | Domain maintenance stages/01-screen/output/{item_id}.json | JSON; identity and screening object |
| Attempt receipt | Domain maintenance work/{item_id}.screen | Script-owned marker; never edit |

## Audit

| Check | Pass condition |
|-------|----------------|
| Scoped comparison | Assessment discusses the observed change, not merely its hash or keywords |
| Evidence | Quotes match the identified snapshot lines |
| Separation | No revision text or proposed knowledge mutations |
| Honest conclusion | None has a concrete explanation; potential identifies what needs investigation |
