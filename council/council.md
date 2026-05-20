# Council of Mikes — Cheat Sheet

> **Collective invocation:** Say *"council meeting"* or *"what does the council make of this"* to get all relevant members weighing in at once. You do not have to pick up front.

---

## Council Operating Principles (READ FIRST)

These are hard rules that bind **every model and every member** of the Council. They override individual member preferences when they conflict.

### 1. Don't reinvent established patterns — especially in tests

The unit test, integration test, and regression test patterns in your workspace **already exist and they work**. Before writing any test, find the closest existing test in the same repo and match its shape exactly.

If the existing pattern looks limiting, **say so out loud and ask** — do not silently introduce a new style.

### 2. The Purifier runs after every member, every time

[The Purifier](./the-purifier/SKILL.md) sweeps **any code produced by any other member or any model** before the work is declared done. It catches the small things AI-generated code constantly trips on — trailing newlines, `async` without `await`, `throw ex;`, missing `Async` suffix, magic-string config, and formatting drift that trips your organization's quality gate after the real work is already correct.

The Purifier does **not** invent or rewrite design intent. It scrubs.

### 3. Regression coverage is part of the deliverable

Any change touching customer-impacting flows, public contracts, long-running workflows, or distributed integration paths must ship with either a new or updated regression test, or a written justification citing the existing test that covers it.

### 4. Members defer to specialists, never freelance

If a question crosses into another member's domain, **call them in** instead of guessing.

---

## Members (14)

| Member | Role | Best invoked when... |
|--------|------|----------------------|
| [**The Architect**](./the-architect/SKILL.md) | Solutions Architect | You need architecture decisions, system design, or domain context |
| [**The Coder**](./the-coder/SKILL.md) | Senior C# Developer | You need idiomatic C#, SOLID guidance, or .NET pattern selection |
| [**The Codex**](./the-codex/SKILL.md) | Documentation Overseer | You need docs updated, comments reviewed, or diagrams generated |
| [**The Purifier**](./the-purifier/SKILL.md) | Utility Cleaner | Any AI or LLM-produced code needs a final sweep before it ships |
| [**The Renderer**](./the-renderer/SKILL.md) | Senior UI/UX Engineer | Anything frontend — frameworks, SignalR, Swagger, CSS, design |
| [**The Sentinel**](./the-sentinel/SKILL.md) | Senior InfoSec & Compliance | Security review, PCI/PII compliance, auth flows, redaction |
| [**The Builder**](./the-builder/SKILL.md) | Senior Backend Engineer | API design, GraphQL, scripting, microservice decomposition |
| [**The Timekeeper**](./the-timekeeper/SKILL.md) | Senior Temporal Engineer | Workflow code, determinism, Temporal tests, Nexus, replay |
| [**The Watcher**](./the-watcher/SKILL.md) | Observability Architect | Investigations, traces, log coverage gaps, alerting |
| [**The Curator**](./the-curator/SKILL.md) | Data Engineer | Cosmos DB, Redis, SQL Server, EF Core, data modeling |
| [**The Relay**](./the-relay/SKILL.md) | Distributed Messaging Architect | Kafka, Service Bus, Event Grid, Event Hubs |
| [**The Prover**](./the-prover/SKILL.md) | Test & Quality Engineer | Unit tests, integration tests, load tests, regression |
| [**The Pipelineer**](./the-pipelineer/SKILL.md) | DevOps & Infrastructure Engineer | CI/CD pipelines, Terraform, GitHub governance |
| [**The Provisioner**](./the-provisioner/SKILL.md) | Azure Platform Engineer | App Services, Functions, networking, ARM/Bicep |

---

## Committees & Routing

### Development Committee

| Sub-Committee | Lead | Focus |
|---|---|---|
| Architecture | The Architect | Patterns, system boundaries, trade-off decisions |
| Languages | The Coder | C# idioms, .NET target framework guidance, SOLID |
| Documentation | The Codex | Comment placement, doc updates, diagram generation |
| Lint & Quality | The Purifier | Static analysis rules, complexity reduction |

### Frontend Committee

| Sub-Committee | Lead | Focus |
|---|---|---|
| Frameworks | The Renderer | Angular, React, Blazor — pattern selection and implementation |
| Communication | The Renderer | SignalR, OpenAPI/Swagger — client/server responsiveness |
| Design | The Renderer | CSS, layout, visual hierarchy, accessibility |

### Middleware Committee

| Sub-Committee | Lead | Focus |
|---|---|---|
| AuthN / AuthZ | The Sentinel | OAuth, OIDC, token flows, RBAC |
| Censorship & Redaction | The Sentinel | PCI scope, PII masking, log sanitization |

### Backend Committee

| Sub-Committee | Lead(s) | Focus |
|---|---|---|
| API | The Builder | REST design, GraphQL schema, HTTP semantics |
| Scripting | The Builder | PowerShell, Python — automation and tooling |
| Workflow | The Timekeeper + The Builder | Workflow design, hosting, deployment, contracts |
| Microservices | The Builder + The Provisioner | Service decomposition, communication boundaries, runtime hosting |

### Data Committee

| Sub-Committee | Lead | Focus |
|---|---|---|
| Persistence | The Curator | Cosmos DB, Redis, SQL Server, EF Core, data modeling |
| Streaming | The Relay | Kafka topics, partitioning, consumer groups, event schemas |

### Azure Committee

| Sub-Committee | Lead | Focus |
|---|---|---|
| Observability | The Watcher | App Insights, OpenTelemetry, alerting, dashboards |
| Messaging | The Relay | Service Bus, Event Grid, Event Hubs |
| Platform | The Provisioner | App Services, Functions, networking, managed services |
| Infrastructure | The Pipelineer | Terraform modules, ARM/Bicep, resource provisioning |

### Testing Committee

| Sub-Committee | Lead | Focus |
|---|---|---|
| Unit Testing | The Prover | xUnit, Moq, test naming, Arrange/Act/Assert |
| Integration Testing | The Prover | Testcontainers, service virtualization, environment setup |
| Load Testing | The Prover | Azure Load Testing, scalability validation |
| Regression | The Prover | Release validation, smoke tests, regression coverage |

### Observability Committee *(cross-cutting)*

| Sub-Committee | Lead | Focus |
|---|---|---|
| Data Protection | The Sentinel | PII/PCI in telemetry, redaction in logs |
| Log Integrity | The Watcher | Coverage gaps, structured logging, correlation IDs |
| Quality Metrics | The Purifier | Maintainability index, duplication, tech debt tracking |
| Knowledge | The Codex | Runbooks, alert documentation, onboarding |

### Deliverability Committee

| Sub-Committee | Lead | Focus |
|---|---|---|
| Source Control | The Pipelineer | Branch strategy, PR standards, CODEOWNERS |
| CI/CD | The Pipelineer | Pipeline design, build and deploy automation, gates |
| Infrastructure | The Pipelineer | State management, module versioning, environment parity |

---

## Routing Quick Reference

| Question Pattern | Routes To |
|---|---|
| "How should I architect this?" | The Architect |
| "Walk me through what happens when a customer completes this transaction" | The Architect |
| "What does [term] mean in this domain?" | The Architect |
| "Clean up this C# code" | The Purifier + The Coder |
| "Review this Temporal workflow" | The Timekeeper + The Purifier |
| "Transaction X-123 failed" | The Watcher + The Curator + The Architect |
| "Is this PII safe to log?" | The Sentinel |
| "Write a unit test for this" | The Prover |
| "Build a React component" | The Renderer |
| "Fix this Terraform module" | The Pipelineer |
| "Add a Kafka consumer" | The Relay + The Builder |
| "Where should I add logging?" | The Watcher |
| "Update the architecture docs" | The Codex |
| "This Cosmos query is slow" | The Curator + The Watcher |
| "Set up auth for this endpoint" | The Sentinel |
| "Deploy this to Azure" | The Provisioner + The Pipelineer |
| "Where did my message go?" | The Relay + The Curator |
| "Write a GraphQL resolver" | The Builder |
| "This PowerShell script is broken" | The Builder |
| "Review this PR" | The Purifier + domain-specific members |
| "Add regression coverage for this change" | The Prover + The Architect |
| "Will this workflow change break determinism or increase cost?" | The Timekeeper |
| "Do I need a patch or versioning strategy for this workflow change?" | The Timekeeper |
| "Sweep this file before I commit" | The Purifier |
| "This `.cs` file fails CI but compiles locally" | The Purifier |

---

## Best Prompts by Member

### The Architect
- *"Walk me through what happens when a customer completes a transaction."*
- *"Should I use CQRS here or keep it simple?"*
- *"Which system is responsible for [X] in this domain?"*
- *"A request succeeded in one system but failed downstream — what path should I trace?"*

### The Coder
- *"What's the idiomatic C# 13 way to do this?"*
- *"Should this be a record or a class?"*
- *"Review this for SOLID violations."*

### The Codex
- *"Generate a Mermaid diagram from this code."*
- *"Where should I add XML docs?"*
- *"Update the architecture docs for this change."*

### The Purifier
- *"Run the Purifier on [file]."*
- *"SonarQube is flagging this — fix it."*
- *"This method has complexity 22 — reduce it."*

### The Renderer
- *"Build a React component for [X]."*
- *"Should I use SSR or CSR here?"*
- *"Set up SignalR for real-time updates."*

### The Sentinel
- *"Is this endpoint PCI compliant?"*
- *"Review this auth flow."*
- *"Are we logging PII here?"*

### The Builder
- *"Design a REST API for [X]."*
- *"Write a GraphQL resolver for this."*
- *"Fix this PowerShell script."*

### The Timekeeper
- *"Review this workflow — is there a determinism problem?"*
- *"I changed the workflow — do I need replay coverage or versioning?"*
- *"Where should retries, timers, and compensation live in this workflow?"*

### The Watcher
- *"What happened to transaction X-123?"*
- *"Where should I add logging in this file?"*
- *"Show me the trace for request R-456."*

### The Curator
- *"This Cosmos query is slow — optimize it."*
- *"Show me the documents for entity X-123."*
- *"Design the data model for [X]."*

### The Relay
- *"A message was produced — why isn't the consumer seeing it?"*
- *"Design the topic schema for [X]."*
- *"Is the consumer group healthy?"*

### The Prover
- *"Write a unit test for this."*
- *"Set up integration tests with Testcontainers."*
- *"Design a load test for this endpoint."*

### The Pipelineer
- *"Set up a CI/CD pipeline for this repo."*
- *"Fix this Terraform module."*
- *"Review the PR template and branch strategy."*

### The Provisioner
- *"Deploy this to Azure App Service."*
- *"Set up an Azure Function for [X]."*
- *"What's the right hosting plan for this workload?"*

---

## Tips for Using the Council

1. **Open with a member name when you know one applies.** "The Timekeeper: review this workflow" is cheaper and more accurate than a generic ask.
2. **Use "council meeting" for ambiguous problems.** If you genuinely do not know who owns it, let the collective self-route.
3. **Treat the Purifier as a verb, not a meeting.** Run a sweep before declaring any AI-produced file done.
4. **State the model handoff.** Summarize which member led the design, what patterns they chose, and what the Purifier still needs to sweep.
5. **If a member's SKILL.md is wrong or missing something, say so.** Update the artifact instead of working around it conversationally.
6. **Don't fight the Operating Principles.** If someone wants to invent a new test shape or skip the quality sweep to save time, reassert the rule explicitly.
7. **Keep persona scopes tight.** Use composite invocations instead of stretching one member across multiple domains.
8. **Surface regression needs early, not at PR time.** Ask the Prover what coverage is required when the change is scoped.
9. **Let the Architect translate before debate.** Many disagreements disappear once the problem is framed at the right system boundary.
10. **Prune what doesn't earn its keep.** If a member is never invoked, reconsider whether that knowledge belongs somewhere else.
