# Sourcing & Fulfillment Pod Architecture Rules (Tier 2)

> **Profile:** Opinionated Fulfillment example; adapt for your organization.
> **Workspace Scope:** `workspace_root\` (Cross-cutting microservices: `orderapi`, `inventoryservice`, `warehouseapi`, `paymentservice`, etc.)  
> **Owner:** The organization that adopts this profile.

## Applicability to feature work

These rules govern newly introduced code and the changes requested by the task. Existing code, mappings, APIs, dependencies, and layouts are integration context, including pre-existing deviations. Preserve the existing contracts needed by the feature. Do not require migrations, renames, refactoring, framework replacement, or unrelated cleanup to reconcile inherited code with these rules. Touching a file does not make all its existing code part of the task. Apply naming rules to identifiers being created, while using existing mapped identifiers exactly as they exist.

Corporate rules supplied or confirmed by the user are authoritative within their stated scope; accepting them does not require ADR links, external verification, or proof of provenance. A pre-existing deviation alone is not a review blocker. Evaluate the requested change and concrete correctness problems it introduces.

---

## 1. Clean / Onion Architecture Boundaries

1. **Inward Dependencies Only**:
   - Dependencies must flow strictly inward toward the Core Domain model.
   - The Domain layer must have zero external dependencies, zero framework couplings, and zero database infrastructure references.
2. **Separation of Concerns**:
   - Application logic orchestrates use cases via Commands and Queries (CQRS).
   - Infrastructure handles persistence, external client HTTP calls, and message brokers via adapter implementations.

---

## 2. 2026 Persistence Doctrine (Strict Relational Standard)

1. **Strict Entity Framework Core**:
   - Entity Framework Core is the **exclusive ORM** for all data reads, writes, transactions, and relational queries.
   - Raw SQL queries via Dapper or manual `DbConnection` queries are **strictly prohibited**.
2. **Zero Redis Caching**:
   - New work must not introduce Redis caching decorators, distributed cache layers, or in-memory cache synchronization mechanisms. Existing deviations remain integration context under the scope rule above.
   - New state, rating matrices, and lookups use PostgreSQL persistence within the requested scope; do not migrate inherited storage merely to reconcile it with this rule.
3. **ANSI PostgreSQL Standards**:
   - All database schemas, tables, columns, indexes, constraints, and query parameters MUST strictly adhere to ANSI standard `lower_snake_case`.

---

## 3. Testing Standards & Quality Gates

1. **Unit Testing**:
   - Framework: MSTest using modern `MSTest.Sdk`.
   - Mocking: `NSubstitute` is the pod-wide mocking library.
2. **Integration Testing**:
   - FAIR is the only standard for feature integration and regression testing. Extend the existing FAIR suites for the agreed feature behavior; do not introduce a parallel feature-testing framework.
   - Aspire, Testcontainers, and real PostgreSQL fixtures are optional. Do not require adopting them, replacing existing fixtures, or migrating a test suite as a blanket completion gate.
   - Describe what the selected tests actually exercise; do not claim real-database or integration evidence from a substitute that does not exercise that behavior.
3. **Acceptance and Behavioral Testing**:
   - Express feature acceptance and regression scenarios in FAIR using its established test structure.
   - Use ordinary MSTest scenario methods and meaningful Given/When/Then helpers with explicit Arrange/Act/Assert comments. No BDD framework or generated `.feature` artifacts.
4. **Pre-Submit Gate (SOP)**:
   - For all code changes, execute the 11-Phase Pre-Submit Gate SOP defined in the central docs/code-change-pre-submit-sop.md.
   - Run the configured workspace checks and shared Council source audit before completion. Report failures and skipped checks accurately.

---

## 4. Multi-Repository Workspace Discipline

1. **Independent Cloned Repositories**:
   - Every service directory under `workspace_root\` (e.g., `orderapi`, `warehouseapi`, `paymentservice`) is an independently cloned Git repository containing its own `.git` directory.
   - The workspace root only tracks workspace-level configuration.
2. **Subdirectory Command Execution**:
   - You MUST `cd` into the target child folder before executing `git`, `dotnet`, or container commands.
   - Never run `git add` from the workspace root expecting to stage child repo files.
3. **Cross-Repo Changes**:
   - Cross-repository tasks require creating separate feature branches and distinct pull requests in each affected child repository.

---

## 5. Security & Secret Hygiene

1. **Authentication Architecture**:
   - APIs follow the corporate Okta/OIDC pattern using the authority, audience and credentials for the target environment. Preview/QA settings are environment-specific, not a universal production default. Preserve inherited contracts under the applicability rules above.
   - Associate authentication follows Microsoft Entra ID as specified in the corporate rules. Associate sessions and application-to-API client credentials are separate boundaries; do not infer a provider conflict or migrate either flow merely because both appear in one application.
   - Verify the actual authentication package/version, registration and policy contract. Use the endpoint scopes and policy format from that application. Do not invent generic RequireRead/RequireWrite policies to match an example.
   - Local development uses the repository-supported secret-loading path and configuration key. Inspect the application before choosing a setting. Secret loading, token acquisition and development authorization bypass are separate controls. Local settings do not authorize bypassing QA/production authentication.
2. **Secret & PII Redaction**:
   - Never log, commit, or display secrets, API credentials, passwords, or customer PII.

---

## 6. Canonical Artifact & Persistence Routing Standard

Every file created, modified, or persisted across this workstation and workspace MUST follow these strict boundary rules:

1. **Workflow Output Artifacts (Specs & Plans)**:
   - **Design Specs (`@brainstorming`)**: `{artifact_root}/specs/YYYY-MM-DD-<topic>-design.md`
   - **Implementation Plans (`@writing-plans`)**: `{artifact_root}/plans/YYYY-MM-DD-<feature-name>.md`
   - **Prohibition**: NEVER save specs or plans into child repositories (`{PROJECT}/docs/superpowers/` is strictly prohibited). All design specs and implementation plans belong exclusively to the workspace-level governance layer.

2. **Project Documentation vs Workspace Documentation**:
   - **Microservice Internal Docs**: Keep service architecture in `{PROJECT}/docs/api-architecture.md`, `project-structure.md`, and `tech-stack.md`, with `README.md` as needed. Service-specific recurring procedures and significant decisions also belong in the child repository: use its existing authorized documentation layout, or `{PROJECT}/docs/procedures/` and `{PROJECT}/docs/decisions/` when no such layout exists. This profile owns destination selection for these documents. These additions do not permit workflow specs/plans or private Council state in child repositories.
   - **Workspace Cross-Cutting Docs**: `workspace_root/docs/architecture/` contains pod-wide standards (`corporate-architecture-rules.md`, `council-v2-documentation.md`, `tech-stack.md`, etc.).
   - **Prohibition**: Never place microservice-internal documentation into `workspace_root/docs/`, and never place cross-cutting corporate architecture or superpower workflows into `{PROJECT}/docs/`.

3. **MemoryForge Ephemeral Boundary (Personal State & Scratchpads)**:
   - **Storage Root**: the selected central memory namespace
   - **Files**: `MEMORY.md` (private index), `active_handoff.md` (written exclusively by `@handoff`), `active_session_backlog.md` (chronological milestone heartbeat), `preferences.md`.
   - **Prohibition**: Never save transient notes, session heartbeats, scratchpads, or personal handoffs to tracked Git repositories.

4. **Model Integration**:
   - Host adapters own instruction entry points, skill discovery, global execution policy, and indexing configuration.

5. **Agile & Review Artifacts**:
   - **Canonical Path**: `workspace_root/temp/userstories/sprint {N}/` or `workspace_root/temp/the-council/`
   - **Files**: INVEST-compliant user stories, DOD definitions, review tracking cards, visual architectural diagrams.

6. **Microservice Source & Tests**:
   - All code, solutions, and tests MUST live strictly within `{PROJECT}/src/` and `{PROJECT}/tests/`. Never bleed child code into the workspace root.
