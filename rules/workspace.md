# Selected Workspace Profile

Read manifest.json and the selected workspace profile. The default is the [Fulfillment profile](../profiles/fulfillment/rules.md), with [corporate architecture guidance](../profiles/fulfillment/corporate-architecture-rules.md).

Current contracts: EF Core/PostgreSQL, no Redis or Dapper, MSTest.Sdk/NSubstitute, and integration/acceptance verification using repository-appropriate tooling and agreed feature requirements. Aspire, Testcontainers, real PostgreSQL fixtures, and Reqnroll/Gherkin are optional testing choices, with no blanket adoption requirement. The profile owns the detailed doctrine; this compatibility entry point does not duplicate it.

Rules govern new code and requested changes. Preserve existing contracts, mappings, dependencies, and layouts needed for integration; pre-existing deviations do not authorize cleanup or create review blockers. Corporate rules confirmed by the user are authoritative without external provenance checks.

Use the explicit task scope and configured workspace paths. Existing authorization remains valid. Read the central [11-phase SOP](../docs/code-change-pre-submit-sop.md); report source, installation, workspace, and native runtime results separately.
