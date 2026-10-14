# The Council â€” Catalog

One source, 15 specialist packages. Invoke a member by name, say council meeting, or Convene the Council. Host adapters supply native invocation syntax.

## Operating principles

Load only the relevant members and workflows. Match established repository patterns. The Purifier reviews code and the Gatekeeper reports applicable verification evidence. Reuse existing task authorization; do not request approval for every development command.

The [Fulfillment profile](../profiles/fulfillment/rules.md) preserves the current contracts: PostgreSQL with EF Core, no Redis or Dapper, MSTest.Sdk with NSubstitute, Aspire/Testcontainers integration tests, and Reqnroll acceptance tests. Earlier catalog recommendations are superseded.

Use the [11-phase SOP](code-change-pre-submit-sop.md) with the selected profile.

## Members (15)

| Member and responsibility | Skill ID |
|---|---|
| [The Architect â€” Solutions Architecture Lead](../skills/the-architect/SKILL.md) | `the-architect` |
| [The Builder â€” Backend API Lead](../skills/the-builder/SKILL.md) | `the-builder` |
| [The Coder â€” C# Development Lead](../skills/the-coder/SKILL.md) | `the-coder` |
| [The Codex â€” Documentation & Knowledge Lead](../skills/the-codex/SKILL.md) | `the-codex` |
| [The Coordinator â€” Agile Systems & Delivery Lead](../skills/the-coordinator/SKILL.md) | `the-coordinator` |
| [The Curator â€” Database & Persistence Lead](../skills/the-curator/SKILL.md) | `the-curator` |
| [The Gatekeeper â€” Pre-Submit Quality Gate Lead](../skills/the-gatekeeper/SKILL.md) | `the-gatekeeper` |
| [The Pipelineer â€” DevOps & CI/CD Lead](../skills/the-pipelineer/SKILL.md) | `the-pipelineer` |
| [The Prover â€” Testing & Validation Lead](../skills/the-prover/SKILL.md) | `the-prover` |
| [The Provisioner â€” Platform Hosting Lead](../skills/the-provisioner/SKILL.md) | `the-provisioner` |
| [The Purifier â€” Code Quality & Static Analysis Lead](../skills/the-purifier/SKILL.md) | `the-purifier` |
| [The Relay â€” Distributed Messaging Lead](../skills/the-relay/SKILL.md) | `the-relay` |
| [The Renderer â€” Frontend UI Lead](../skills/the-renderer/SKILL.md) | `the-renderer` |
| [The Sentinel â€” InfoSec & Authentication Lead](../skills/the-sentinel/SKILL.md) | `the-sentinel` |
| [The Watcher â€” Observability & Telemetry Lead](../skills/the-watcher/SKILL.md) | `the-watcher` |

## Routing

Architecture â†’ Architect; API â†’ Builder; language implementation â†’ Coder; persistence â†’ Curator; testing â†’ Prover; code quality â†’ Purifier; final review â†’ Gatekeeper; docs â†’ Codex; delivery â†’ Coordinator; frontend â†’ Renderer; security â†’ Sentinel; messaging â†’ Relay; telemetry â†’ Watcher; CI/CD â†’ Pipelineer; hosting â†’ Provisioner.

Temporal or other unfamiliar workflow technology routes to the Architect and appropriate existing domain specialists; there is no Timekeeper package in this catalog.
