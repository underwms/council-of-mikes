# 00 Daily mainline documentation refresh

Council Paperwork form: **ICM-00 Mainline Refresh**. Follow the [shared form mapping](../../../references/paperwork/memforge-icm-forms.md). Use the existing records below; preserve their schemas, authority and attempt rules.

## Inputs

| Source | Location | Section/Scope | Why |
|--------|----------|---------------|-----|
| Daily assignment | Domain maintenance runs/{run_id}.json | This run only | Ownership, observations and refresh identities |
| Refresh procedure | ../../../references/daily-mainline.md | Full file | Commands, pinned source and publication rules |
| Documentation skill | ../../../../skills/repo-documentation/SKILL.md | Mainline refresh mode, source review and documentation standards | Interpret changes and refresh affected sections |
| Working packet | daily mainline-packet | One assigned refresh item | Exact main/master commit, changed paths and document identities |
| Existing explanations | Packet documents | Relevant sections only | Preserve structure and assess impact |
| Integrated evidence | daily mainline-source | Changed paths and necessary committed context | Read fetched mainline, independently of feature work |

## Process

1. Run mainline-scan once for the assigned run. It fetches advertised origin/main and origin/master into dedicated refs. Process each returned refresh identity sequentially once; failures in one repository do not stop others.
2. Obtain its mainline-packet. Apply repo-documentation using the pinned commit source reader. Never substitute working-tree source, feature commits or uncommitted files.
3. Decide updated, no-doc-change or failed. For updates, write only affected document replacements beneath local stages/00-mainline-refresh/output/. Preserve unchanged documents, dates and wording. Documentation judgment belongs to this agent, not Git.
4. Audit and submit mainline-finish once. It validates evidence and all original document identities, then publishes only registered workspace documentation. It does not commit, push, accept knowledge or promote the legacy local-working-tree baseline.
5. Once every refresh item has a terminal record, call scan-documents once. Continue to 01-screen for the returned document work. Do not reclaim interrupted work or retry submissions. Failed/unrefreshed documents do not feed screening through this run.

## Outputs

| Artifact | Location | Format |
|----------|----------|--------|
| Staged replacements and review receipt | Local stages/00-mainline-refresh/output/ | Markdown files and {refresh_id}.json |
| Execution record | Local refresh/{refresh_id}.json and .final | Script-owned status, identity and source/document fingerprints |
| Mainline observations/checkpoints | Local run receipt and mainline-checkpoints.json | Network observation, last attempted and successfully documented revisions |
| Document work | Existing local work/ | Changed successful documentation only |

## Audit

| Check | Pass condition |
|-------|----------------|
| Integration boundary | Evidence comes from the assigned fetched main/master revision or its recorded prior documented revision |
| Working copy | No checkout, merge, reset, commit, push or feature-source edits |
| Judgment | Exact affected explanations updated, or concrete no-doc-change reason; no rewrite forced by commit/date alone |
| Evidence | Inspected paths, revision and SHA-256 values come from the source reader |
| Publication | Only registered document paths and expected original fingerprints are submitted |
