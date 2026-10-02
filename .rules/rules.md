# Sourcing & Fulfillment Pod Architecture Rules (Tier 2)

> **Authority:** Fulfillment and Rate Engine Pod Architectural Governance  
> **Workspace Scope:** `workspace_root\` (Cross-cutting microservices: `orderapi`, `inventoryservice`, `warehouseapi`, `paymentservice`, etc.)  
> **Pod Lead:** Mike Underwood

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
   - Redis caching decorators, distributed cache layers, and in-memory cache synchronization mechanisms have been completely purged from the architecture.
   - All state, rating matrices, and lookups are stored and queried natively in PostgreSQL.
3. **ANSI PostgreSQL Standards**:
   - All database schemas, tables, columns, indexes, constraints, and query parameters MUST strictly adhere to ANSI standard `lower_snake_case`.

---

## 3. Testing Standards & Quality Gates

1. **Unit Testing**:
   - Framework: MSTest using modern `MSTest.Sdk`.
   - Mocking: `NSubstitute` is the pod-wide mocking library.
2. **Integration Testing**:
   - Framework: Native .NET Aspire Testing (`Aspire.Hosting.Testing`) and Testcontainers.
   - Zero Mock DBs: Never use in-memory database providers (e.g., InMemory EF provider or fake repositories) for integration tests; all tests must execute against real containerized PostgreSQL instances.
3. **Behavioral Testing**:
   - All feature-level acceptance tests must use Reqnroll with Gherkin `.feature` specifications.
4. **Pre-Submit Gate (SOP)**:
   - For all code changes, execute the 11-Phase Pre-Submit Gate SOP defined in `docs/procedures/code-change-pre-submit-sop.md`.
   - Execute `powershell -NoProfile -ExecutionPolicy Bypass -File %USERPROFILE%\workspace_root\scripts\validate-workspace.ps1` before completion. Work is only complete when the validator returns 100% PASS with 0 warnings.

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
   - APIs use Okta preview OpenID Connect (OIDC) token flows.
   - Scope authorization is governed dynamically via `IAuthorizationPolicyProvider`.
   - Local Fallback: Set `"UseSecrets": false` at the root of `appsettings.Development.json` for local containerized development to prevent invalid GCP Secret Manager connection attempts.
2. **Secret & PII Redaction**:
   - Never log, commit, or display secrets, API credentials, passwords, or customer PII.

---

## 6. Canonical Artifact & Persistence Routing Standard

Every file created, modified, or persisted across this workstation and workspace MUST follow these strict boundary rules:

1. **Workflow Output Artifacts (Specs & Plans)**:
   - **Design Specs (`@brainstorming`)**: `workspace_root/docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
   - **Implementation Plans (`@writing-plans`)**: `workspace_root/docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`
   - **Prohibition**: NEVER save specs or plans into child repositories (`{PROJECT}/docs/superpowers/` is strictly prohibited). All design specs and implementation plans belong exclusively to the workspace-level governance layer.

2. **Project Documentation vs Workspace Documentation**:
   - **Microservice Internal Docs**: `{PROJECT}/docs/` contains ONLY `api-architecture.md`, `project-structure.md`, `tech-stack.md`, and `README.md`.
   - **Workspace Cross-Cutting Docs**: `workspace_root/docs/architecture/` contains pod-wide standards (`corporate-architecture-rules.md`, `council-v2-documentation.md`, `tech-stack.md`, etc.).
   - **Prohibition**: Never place microservice-internal documentation into `workspace_root/docs/`, and never place cross-cutting corporate architecture or superpower workflows into `{PROJECT}/docs/`.

3. **MemoryForge Ephemeral Boundary (Personal State & Scratchpads)**:
   - **Storage Root**: `%USERPROFILE%\.gemini\tmp\%USERNAME%\memory\`
   - **Files**: `MEMORY.md` (private index), `active_handoff.md` (written exclusively by `@handoff`), `active_session_backlog.md` (chronological milestone heartbeat), `preferences.md`.
   - **Prohibition**: Never save transient notes, session heartbeats, scratchpads, or personal handoffs to tracked Git repositories.

4. **Gemini CLI Configuration & Context**:
   - **Global Host Rules & Specialists**: `%USERPROFILE%\.gemini\` (`GEMINI.md`, `.rules/rules.md`, `policies/auto-allow.toml`, `skills/<specialist>/`).
   - **Workspace Context & Superpowers**: `workspace_root\GEMINI.md` (root context import) and `workspace_root\.gemini\` (`GEMINI.md`, `.rules/rules.md`, `skills/`).

5. **Agile & Review Artifacts**:
   - **Canonical Path**: `workspace_root/temp/userstories/sprint {N}/` or `workspace_root/temp/the-council/`
   - **Files**: INVEST-compliant user stories, DOD definitions, review tracking cards, visual architectural diagrams.

6. **Microservice Source & Tests**:
   - All code, solutions, and tests MUST live strictly within `{PROJECT}/src/` and `{PROJECT}/tests/`. Never bleed child code into the workspace root.
