# Reevaluation quality reference

Investigate whether maintained knowledge needs to change, using the saved screening assessment as the starting point. Potential impact is a request to investigate, not a predetermined revision.

Open the relevant knowledge index/routes and affected notes. Consult their primary evidence when necessary. A missing architecture document does not disprove the knowledge. A changed summary does not establish deployed behavior. If adequate investigation is unavailable, record failed rather than inventing a conclusion.

Choose proposed or no-revision-needed. Both require knowledge_review entries with current path, sha256 and reason. Include the exact screening_sha256 from the reevaluate packet. For no-revision-needed, explain why current knowledge still holds; do not include a proposal.

For proposed, proposal contains summary, revisions and uncertainties. Each revision contains target, operation (create/revise/retire), before_sha256 (null for create), proposed_text (complete document text; null only for retirement), and reason. Preserve uncertainty and distinguish source observations, hypotheses and confirmed behavior. Never mutate accepted knowledge or application code.

Scripts validate fingerprints, quotes and target scope; these checks do not verify interpretation. Output files are human edit surfaces. Execution receipts and preserved evidence versions are historical records, not editable handoffs. Completed work stays completed even if someone later edits its output; there is no retry, recovery or automatic proposal acceptance.

Value criteria: either prevent an unsupported knowledge change, preserve an accurate explanation, or propose a specific evidence-backed correction. For recurring errors, improve the canonical contract/reference. Do not learn workflow rules from prior run outputs.

For new Markdown notes, include the needed owning-index edits and remove obsolete empty-collection placeholders in the proposed text. For retirement, propose appropriate active/historical routing changes. The [explicit acceptance procedure](../../references/proposal-acceptance.md) validates discoverability and shows a historical-content tombstone for retirement; it never invents unapproved index changes. Tooling, workflow instructions and baseline history are not knowledge acceptance targets.
