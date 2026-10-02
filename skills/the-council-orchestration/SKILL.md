---
name: the-council-orchestration
description: Use when receiving ceremonial phrases like "Convene the Council", "I would like to convene the Council to address...", or when orchestrating complex multi-specialist tasks.
---

# The Council Orchestration — Multi-Specialist Agentic Workflow

## Overview
This skill implements **Multi-Persona Agentic Orchestration**. When the user calls upon the Council, a single master agent acting as `[THE ARCHITECT]` ingests the challenge, decomposes it across Onion Architecture boundaries, and coordinates execution across the Council's 15 specialized personas.

---

## Ceremonial Invocation Triggers

The Council is convened whenever the user employs ceremonial phrasing in chat:
* *"I would like to convene the Council to address the following challenge: [details]"*
* *"I need the Council to convene to tackle this problem: [details]"*
* *"Convene the Council: [details or user story]"*

### Dual Execution Modes
1. **Interactive Session Orchestration Mode (Default in Chat)**:
   - `[THE ARCHITECT]` assumes the floor, ingests the prompt, and presents the task decomposition table at **Gate 1 (Plan Approval)**.
   - Upon developer confirmation, coordinates execution using specialized subagents or Python file tools.
   - Automatically executes test repair loops (up to 3 retries) with compiler error feedback.
   - Hands off to `[THE GATEKEEPER]` at **Gate 2 (Pre-Submit Approval)** with the 11-Phase Done checklist.
2. **Autonomous Engine Mode (Standalone CLI / CI)**:
   - Invoked directly in terminal or batch jobs:
     ```bash
     python scripts/convene.py "I would like to convene the Council to address: <task>"
     python scripts/convene.py --story temp/userstories/sprint3/ORDER-185.md
     python scripts/convene.py --auto-approve
     ```

---

## Workflow Checklist

You MUST create and complete these tasks in sequence:

- [ ] **Phase 1: Architecture Parsing & Synthesis** — Act as `[THE ARCHITECT]` and ingest the challenge prompt.
- [ ] **Phase 2: Generate Specification & Multi-Specialist Plan (Gate 1)** — Present task table with specialist assignments and await developer approval.
- [ ] **Phase 3: Specialist Execution & Test-Repair Loop** — Dispatch tasks to assigned Council specialists, running tests after changes with up to 3 repair retries.
- [ ] **Phase 4: Integrity Validation & Pre-Submit SOP (Gate 2)** — Run `validate_workspace.py` / `validate-workspace.ps1` and present the 11-Phase Pre-Submit Gate summary.

---

## Detailed Execution Guidelines

### Phase 1: Architecture Parsing & Synthesis
1. **Assume Callsign**: Immediately prefix all orchestration responses with `[THE ARCHITECT]`.
2. **Analyze Challenge**: Parse the challenge string or user story. Identify target repositories, database impacts (strict EF Core, no Redis), security scopes, and API contracts.

### Phase 2: Design and Plan (Gate 1: Plan Approval)
1. **Multi-Specialist Plan**: Decompose the work into independent, chronological tasks mapped to specialists:
   * `[THE ARCHITECT]`: System designs, Clean/Onion boundaries, CQRS, and subagent orchestration plans.
   * `[THE BUILDER]`: Minimal APIs, OpenAPI/Scalar, REST semantics, and host automation scripts.
   * `[THE CODER]`: C# classes, primary constructors, collection expressions, pattern matching, async purity.
   * `[THE CODEX]`: Architecture wikis, Mermaid sequence diagrams, ADR chronologies, and XML docs.
   * `[THE COORDINATOR]`: JIRA issue lifecycles, sprint backlogs, INVEST user stories, DoD/DoR verification.
   * `[THE CURATOR]`: PostgreSQL relational schemas, strict Entity Framework Core, migrations (No Dapper / No Redis).
   * `[THE GATEKEEPER]`: 11-Phase Pre-Submit Gate SOP, workspace integrity validation, PR simulation.
   * `[THE PIPELINEER]`: TeamCity builds, Octopus Deploy gates, GitHub Actions, and Git branching strategies.
   * `[THE PROVER]`: Unit testing (MSTest.Sdk / NSubstitute), Reqnroll BDD, native .NET Aspire Testing, Testcontainers.
   * `[THE PROVISIONER]`: GKE cluster hosting, Kubernetes manifests, HPA autoscaling, container ingress.
   * `[THE PURIFIER]`: Roslyn static analysis, SonarQube tripwires, dead code pruning, formatting compliance.
   * `[THE RELAY]`: Apache Kafka topic partitioning, CloudEvents schemas, consumer groups, dead-letter queues.
   * `[THE RENDERER]`: React components, TypeScript typing, CSS modules, Kiwi design system implementations.
   * `[THE SENTINEL]`: Okta preview OIDC token flows, dynamic `IAuthorizationPolicyProvider`, secret isolation.
   * `[THE WATCHER]`: OpenTelemetry tracing, Serilog structured logging, Grafana Loki queries, correlation IDs.
2. **Present Plan at Gate 1**: Pause for developer review and confirmation before modifying any code.

### Phase 3: Specialist Execution & Test-Repair Loop
For each task in the plan:
1. Dispatch specialist persona binding the relevant instructions from:
   `%USERPROFILE%\.gemini\skills\<specialist>\SKILL.md`
2. Apply surgical changes using sandboxed file tools.
3. Run tests via `[THE PROVER]`. If tests fail, feed compiler diagnostics back to the specialist for up to 3 repair loops.

### Phase 4: Quality Gate & Validation (Gate 2: Pre-Submit Approval)
1. **Validate Workspace Integrity**:
   - Universal Python runner: `python scripts/validate_workspace.py`
   - PowerShell runner: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/validate-workspace.ps1`
   - Must achieve 100% green PASS with 0 errors and 0 warnings.
2. **Execute Pre-Submit SOP**: Compile the 11-Phase checklist from `docs/procedures/code-change-pre-submit-sop.md`.
3. **Present Gate 2 Report**: Present the compliance summary for final developer sign-off.

---

## Anti-Patterns
* ❌ **Proceeding without Gate 1 approval**: Always confirm the plan before modifying files unless `--auto-approve` is explicitly requested.
* ❌ **Guessing specialist rules**: Always bind the target specialist's package under `~/.gemini/skills/<specialist>/SKILL.md`.
* ❌ **Skipping the workspace validator**: A task is never finished until `validate_workspace.py` returns 100% PASS.
