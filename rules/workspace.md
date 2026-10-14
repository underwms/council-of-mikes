# Selected Workspace Profile

Read manifest.json and the selected workspace profile. The default is the [Fulfillment profile](../profiles/fulfillment/rules.md), with [corporate architecture guidance](../profiles/fulfillment/corporate-architecture-rules.md).

Current contracts: EF Core/PostgreSQL, no Redis or Dapper, MSTest.Sdk/NSubstitute, real PostgreSQL integration tests, and Reqnroll acceptance tests. The profile owns the detailed doctrine; this compatibility entry point does not duplicate it.

Use the explicit task scope and configured workspace paths. Existing authorization remains valid. Read the central [11-phase SOP](../docs/code-change-pre-submit-sop.md); report source, installation, workspace, and native runtime results separately.
