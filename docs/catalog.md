# The Council - Catalog

One source, 15 specialist packages. Invoke a member by name, say council meeting, or Convene the Council. Host adapters supply native invocation syntax.

## Operating principles

Load only the relevant members and workflows. Match established repository patterns. The Purifier reviews code and the Gatekeeper reports applicable verification evidence. Reuse existing task authorization; do not request approval for every development command.

The [Fulfillment profile](../profiles/fulfillment/rules.md) defines PostgreSQL with EF Core, no Redis or Dapper, and MSTest.Sdk with NSubstitute for new work within scope. FAIR is the only standard for feature integration and regression testing. Extend the existing FAIR suites for the agreed feature behavior; do not introduce a parallel feature-testing framework. Aspire, Testcontainers, and real PostgreSQL fixtures are optional supporting fixture choices. Preserve existing contracts and dependencies needed for integration; pre-existing deviations do not authorize cleanup or block the feature. Corporate rules confirmed by the user are authoritative without external provenance checks. Earlier catalog recommendations are superseded.

Use the [11-phase SOP](code-change-pre-submit-sop.md) with the selected profile.

## Members (15)

| Member and responsibility | Skill ID |
|---|---|
| [The Architect - Solutions Architecture Lead](../skills/the-architect/SKILL.md) | `the-architect` |
| [The Builder - Backend API Lead](../skills/the-builder/SKILL.md) | `the-builder` |
| [The Coder - C# Development Lead](../skills/the-coder/SKILL.md) | `the-coder` |
| [The Codex - Documentation & Knowledge Lead](../skills/the-codex/SKILL.md) | `the-codex` |
| [The Coordinator - Agile Systems & Delivery Lead](../skills/the-coordinator/SKILL.md) | `the-coordinator` |
| [The Curator - Database & Persistence Lead](../skills/the-curator/SKILL.md) | `the-curator` |
| [The Gatekeeper - Pre-Submit Quality Gate Lead](../skills/the-gatekeeper/SKILL.md) | `the-gatekeeper` |
| [The Pipelineer - DevOps & CI/CD Lead](../skills/the-pipelineer/SKILL.md) | `the-pipelineer` |
| [The Prover - Testing & Validation Lead](../skills/the-prover/SKILL.md) | `the-prover` |
| [The Provisioner - Platform Hosting Lead](../skills/the-provisioner/SKILL.md) | `the-provisioner` |
| [The Purifier - Code Quality & Static Analysis Lead](../skills/the-purifier/SKILL.md) | `the-purifier` |
| [The Relay - Distributed Messaging Lead](../skills/the-relay/SKILL.md) | `the-relay` |
| [The Renderer - Frontend UI Lead](../skills/the-renderer/SKILL.md) | `the-renderer` |
| [The Sentinel - InfoSec & Authentication Lead](../skills/the-sentinel/SKILL.md) | `the-sentinel` |
| [The Watcher - Observability & Telemetry Lead](../skills/the-watcher/SKILL.md) | `the-watcher` |

## Routing

Architecture -> Architect; API -> Builder; language implementation -> Coder; persistence -> Curator; testing -> Prover; code quality -> Purifier; final review -> Gatekeeper; docs -> Codex; delivery -> Coordinator; frontend -> Renderer; security -> Sentinel; messaging -> Relay; telemetry -> Watcher; CI/CD -> Pipelineer; hosting -> Provisioner.

Temporal or other unfamiliar workflow technology routes to the Architect and appropriate existing domain specialists; there is no Timekeeper package in this catalog.
