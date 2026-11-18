---
name: repo-documentation
description: Refresh or audit repository and workspace architecture documentation from source. Use for stale docs, architecture copies and documentation synchronization; not general prose editing.
---

# Repository Documentation Maintenance

## Overview

Audit or refresh architecture documentation against the inspected source revision and current working tree. Use an existing source/document baseline when available, Git history where applicable, and direct source review to explain behavioral impact. Update only authorized destinations and affected sections.

**Core principle:** Read changed source code to understand intent — don't just note that files changed.

## Scope, authorization and execution

- Audit-only requests produce findings without changing docs, branches or remote references. An authorized refresh includes the relevant documentation edits; do not ask again for the same scope after presenting routine findings.
- Apply specialist guidance inline by default. Use native subagents only for useful independent work when available and authorized by the user or applicable workflow. A multi-repository request alone does not require delegation. Follow the shared delegation contract for ownership, evidence and integration.
- Inspect local repository identity, HEAD, branch and dirty changes. Fetch only when current remote state is required for the task and authorized. Identify the inspected baseline and any remote-freshness limit. Do not switch branches, reset changes, commit or push by implication.
- Establish the documentation destination and its versioning. A workspace may contain independent Git repositories without itself being a Git repository. Never initialize Git or require a workspace commit to complete a documentation refresh.
- Preserve existing source contracts and documentation structure. Describe observed behavior accurately; distinguish policy requirements from implemented behavior. Do not turn inherited deviations into cleanup or retrofit templates onto unrelated docs.

## Dependencies and ordering

For the standing daily mainline refresh, first read the [daily mainline procedure](../../instructions/references/daily-mainline.md). Its pinned Git source packet replaces working-tree source inspection for established behavior; use the mainline-source reader and stage replacements for validated publication. A no-impact review leaves document bytes unchanged. The procedure defines source identity, write boundaries and mainline freshness; do not promote the separate local-working-tree baseline or accept knowledge as part of this mode.

Use the configured repository inventory when present; no external repo-management, parallel-dispatch or reconciliation skill is a prerequisite. Inspect source and per-repository copies before updating their aggregation and cross-cutting flow docs. Keep dependent work sequential.

For an authorized delegated task, provide the repository, source revision/current changes, destination, allowed writes, expected evidence and integration owner. Independent source reads can run in parallel. Agents writing a shared destination need explicit file ownership; they must not commit or switch branches without authorization.

## When to Use

- Architecture docs may be outdated after code changes
- New features were merged but docs weren't updated
- "Update all docs" — full audit and update cycle
- "Audit doc staleness" — report-only mode
- Updating a specific repo's `docs/` (or legacy `docs/architecture/`)
- Refreshing workspace-level `docs/architecture/` files

## When NOT to Use

- Creating *initial* documentation for a brand new repo — that's a separate concern; use an initial-generation/onboarding skill
- Updating `docs/procedures/`, `docs/decisions/`, `docs/plans/`
- Pushing to remote or creating PRs — use a PR-creation skill
- Updating consolidated instruction files (`.github/instructions/`, `.claude/rules/`) — those are workspace-rule changes, not architecture docs

## Downstream Consumers

Workspace docs maintained by this skill are typically referenced by:

- `.github/instructions/workspace.instructions.md` and `.claude/rules/workspace.md` — Architecture Knowledge Hierarchy links to workspace docs; per-service entries point to `docs/architecture/{repo}/` paths.
- Any user-facing documentation site (e.g., VitePress, MkDocs) that converts workspace docs into rendered pages.

**Impact:** if you rename, restructure, or remove workspace docs, check that these downstream files still have valid references.

## Trigger Modes

| Mode | Example Trigger | Scope |
|------|----------------|-------|
| **Single doc** | "update service-a tech-stack" | One doc in one repo |
| **Single repo** | "update service-a docs" | All docs in one repo |
| **Workspace doc** | "update infrastructure.md" | One workspace-level doc |
| **Update all** | "update all docs" | Full audit + update cycle |
| **Audit only** | "audit doc staleness" | Report only, no changes |
| **Reconciliation** | An existing drift queue or explicit integrated-source review | Only the supplied repository, source/doc paths and authorized destination |

## Queue Contract (Reconciliation Mode)

When an existing reconciliation workflow supplies a queue at `docs/handoffs/reconciliation/*-drift-queue.md`, use these inputs. Do not fabricate a queue or require a missing workflow:

| Input | Required | Source in queue | Behavior |
|---|---|---|---|
| `Repo` | yes | `## <repo-name>` heading | Scope of this dispatch. |
| `Archetype` | yes | `- Archetype: ` line | Drives Repo Type Behavior. Trust the queue value; do **not** re-derive from path heuristics. |
| `LastWorkspaceUpdate` | yes | `- Last workspace update: ` line | Use as a historical baseline; verify that its source/doc identities still apply. |
| `ChangedSourcePaths` | yes | `### Source paths changed` bullets | Read **exactly these** child repo files to assess behavioral impact in Phase 3 step 2. Do not re-glob the child repo. |
| `ChangedDocPaths` | optional | `### Doc paths changed` bullets | Read these child repo docs in Phase 3 step 3 to incorporate owning-team improvements. |

**Contract rules:**

- Treat the queue as bounded task data. Use its archetype and supplied paths; surface conflicting current source or manifest evidence instead of silently overriding it.
- Reuse a queue staleness result only when its source/doc identities still apply. Otherwise inspect the changed scope before updating docs.
- Report completion to the invoking workflow; retire a queue only within its authorized ownership.

## Phase 1 - Establish the inspected scope

Record the requested repositories/documents, allowed writes and available source. Read local Git status, branch, HEAD and relevant dirty/untracked content where Git applies. Existing unrelated changes are context; preserve them. If a dirty file affects the documentation, include its content and identity in the analysis rather than requiring a clean branch universally.

If the task specifically requires comparison with current remote state, fetch only within authorization. A local-source audit can proceed without fetching; state that limit. Ask only about a material ambiguity or a branch change actually needed for the requested result.

## Phase 2 - Establish staleness and behavioral impact

1. Prefer the collection's existing source/document baseline and receipt/check process. Inspect reported changed paths and the relevant current source; a hash change signals review, not automatic semantic staleness.
2. Where workspace docs are Git-tracked, history can locate a candidate prior revision and changed source/doc paths. Commit dates alone do not prove freshness or behavioral impact; inspect current dirty content too.
3. Where the workspace is not Git-tracked, use the established baseline receipts or another recorded source/doc identity. If no usable baseline exists, compare the document directly with current source and report the coverage/unknowns. Do not invent a last-update commit or treat front-matter dates as proof.
4. Verify whether changed source or owning-team docs affect the explanation. Preserve unresolved source access gaps; never claim an inaccessible repository is current.

For an audit, present findings and stop. For an authorized refresh, present the staleness summary and continue within the approved scope. Ask only if the findings introduce materially new work. Advance a collection baseline only through its existing evidence/accept process after the documentation work and required checks are complete.

### Source Path Mapping by Archetype

Which source paths to inspect for staleness, by repo archetype:

| Archetype | Source Paths |
|-----------|-------------|
| `service` (.NET) | `src/`, `*.csproj`, `Directory.Build.props`, `Directory.Packages.props`, `Dockerfile`, `docker-compose*.yml` |
| `library` | `src/`, `*.csproj`, `Directory.Build.props`, `CHANGELOG.md` |
| `infra` | `infrastructure/`, `modules/`, `*.tf`, `*.tfvars`, JSON infra modules |
| `apim` | `src/<api-folder>/`. Each API folder is independently versioned — patch only the folders that appear in the queued source paths. |
| `frontend` | `apps/`, `packages/`, `src/`, `package.json`, lock files |
| `java` | `src/main/java`, `src/test/java`, `pom.xml`, `build.gradle*`, `settings.gradle*` |
| `polyglot` | Union of relevant globs for each language present in the repo |
| `android` | `app/`, `core/`, `features/`, `shared/`, `libraries/`, `build.gradle*`, `gradle.properties`, `gradle/libs.versions.toml` |
| `ios` | `Sources/`, `Features/`, `Shared/`, `Tuist.swift`, `Workspace.swift`, `Project.swift`, `Package.swift` |
| `deprecated` | (drift-note only — see Repo Type Behavior below) |

### Staleness Report

Present results before making changes:

| Repo | Doc | Last Updated | Source Changes | Verdict |
|------|-----|-------------|----------------|---------|
| service-a | tech-stack.md | 2026-01-15 | 12 files | 🔴 STALE |
| service-a | project-structure.md | 2026-02-28 | 0 files | 🟢 Current |

For **audit only** mode: stop here. For an authorized update: continue with affected docs in scope; seek clarification only for material scope changes or a missing required decision.

## Phase 3 — Update Execution

For each affected workspace copy at the authorized destination (commonly `docs/architecture/{repo}/`):

1. **Read workspace copy** — `docs/architecture/{repo}/{doc}.md` — understand structure, conventions, detail level.
2. **Read child repo source** — use platform-native file reads (e.g., `Get-Content` on Windows, `cat` on Unix) to read changed source files in the child repo. Child repos are typically gitignored at the workspace root and may not be accessible via glob/grep.
3. **Read child repo docs as reference** — locate the child repo's doc directory using the fallback hierarchy (`docs/` -> `docs/architecture/` -> `README.md`). If updated by the owning team since our last sync, incorporate their improvements.
4. **Assess behavioral impact** — does the change affect what the doc describes?
   - Renamed variable → skip (no behavioral change)
   - New queue consumer / endpoint → update (new integration point)
   - New workflow / activity → update (and add a sequence diagram if your conventions call for one)
   - New project file → update (new project/deployable)
   - Dependency version bump → maybe update (usually only when major)
5. **Surgical patch** — update only affected sections in the workspace copy. Preserve voice, formatting, conventions.
6. **Update `**Last Updated**:` line** — set to today's date (format: `YYYY-MM-DD`). Normalize variant formats:
   - `**Last Updated:** February 28, 2026` → `**Last Updated**: 2026-02-28`
   - Colon placement: always `**Last Updated**: ` (colon after `**`, then space)
7. **Verify and report** - inspect the saved diff, text integrity, references and relevant baseline checks. Commit only if explicitly authorized and the destination is Git-tracked; otherwise leave reviewable files and evidence.

**Default write boundary:** workspace copies only. Read child source/docs as evidence. A separate explicit request to edit child-repository documentation must name that destination and obey its repository rules; a workspace refresh never authorizes child-source changes.

### Repo Type Behavior

Archetype values come from the queue contract (reconciliation mode) or from the manifest's repo-type column (other modes).

| Archetype | Treatment |
|---|---|
| `service` | Full behavioral analysis, all doc types. |
| `library` | Focus on public API surface, package versions, consumer impact. Update `CHANGELOG.md` references when they appear in source paths. |
| `infra` | Focus on provisioned resources. Source paths will be IaC modules, not application code. |
| `apim` | Each API folder is independently versioned — patch only the folders that appear in queued source paths; never rewrite an entire workspace copy because one API changed. |
| `frontend` / `java` / `android` / `ios` | Skip checks specific to other stacks. |
| `polyglot` | The doc usually needs **separate sections** per language/stack. |
| `deprecated` | Drift-note only. Append a brief "Drift note ({date}): {commit-summary}" to the workspace copy header. Do **not** describe the repo as actively evolving. Do **not** add new sections. |

### Standard Doc Types & Skill-Mapped Templates

Use the following three-file outline when creating new architecture docs or when that format is already established. Preserve existing doc structure during a scoped refresh. Include only applicable, source-supported details; technology examples are not evidence that a repository implements them. Do not enforce new-work policy by rewriting an inherited architecture description or changing child files.

#### 1. `api-architecture.md` Template Blueprint
Coordinated by `the-builder`, `the-sentinel`, and `the-relay`.

*   **Header**: `# API Architecture — {Solution-Name}`
*   **Subheader 1**: `## 1. Endpoints & Route Definitions` (`the-builder`)
    *   *Content*: ASP.NET Core Minimal API endpoint tables with Verb, Path, Operation Name, Description, and Auth Scope details.
*   **Subheader 2**: `## 2. API Authorization & JWT Scopes` (`the-sentinel`)
    *   *Content*: Observed identity provider and authorization scopes, client credential policies, relevant test authentication fixtures, and secret hygiene practices.
*   **Subheader 3**: `## 3. High-Integrity Write & Transaction Workflows` (`the-coder` / `the-curator`)
    *   *Content*: Command/write handler pipelines, EF Core transaction boundaries, PostgreSQL query ownership, and cancellation-safe persistence. Redis and Dapper are prohibited by the current profile.
*   **Subheader 4**: `## 4. Message Queue & Event Contracts` (`the-relay`)
    *   *Content*: Kafka events, GCP Pub/Sub topics, schema formats, retry/dead-letter setups, and sequence flow diagrams.

#### 2. `project-structure.md` Template Blueprint
Coordinated by `the-architect`, `the-coder`, and `the-prover`.

*   **Header**: `# Project Structure — {Solution-Name}`
*   **Subheader 1**: `## 1. Solution Layout & Clean Onion Layers` (`the-architect` / `the-coder`)
    *   *Content*: Visual inward-pointing reference diagrams, namespaces, and solution project filter (`.slnx`) setups.
*   **Subheader 2**: `## 2. Assembly Boundaries & Layer Responsibilities` (`the-coder`)
    *   *Content*: Actual assembly layers and dependency direction (e.g. `.Core`, `.Data`, `.Api`). Separate observed dependencies from the selected profile requirements for new work; inherited deviations do not authorize source changes.
*   **Subheader 3**: `## 3. Unit, Integration & Spec Test Suites` (`the-prover`)
    *   *Content*: The repository's actual unit suites and FAIR feature integration, acceptance, and regression suites. FAIR is the only feature integration and regression testing standard. Describe MSTest/NSubstitute and supporting fixtures where used.

#### 3. `tech-stack.md` Template Blueprint
Coordinated by `the-purifier`, `the-curator`, `the-watcher`, and `the-pipelineer`.

*   **Header**: `# Technical Stack — {Solution-Name}`
*   **Subheader 1**: `## 1. Runtime Frameworks & Core Libraries` (`the-purifier` / `the-architect`)
    *   *Content*: Core runtime versions (e.g. .NET 10.0), primary framework libraries, and centralized package management props.
*   **Subheader 2**: `## 2. PostgreSQL Persistence & EF Core Mapping` (`the-curator`)
    *   *Content*: PostgreSQL ANSI syntax, lower_snake_case schema columns and constraints, EF Core mapping, migrations, and indexing.
*   **Subheader 3**: `## 3. Distributed Telemetry & Structured Logging` (`the-watcher`)
    *   *Content*: Serilog structure formats, OpenTelemetry span metrics, Grafana Loki exporter setups, and alerts.
*   **Subheader 4**: `## 4. CI/CD Pipelines & Container Release Specifications` (`the-pipelineer` / `the-provisioner`)
    *   *Content*: TeamCity configurations, Octopus deployment scripts, Dockerfile setups, and hosting GKE environments.

## Phase 4 — "Update All" Orchestration

When triggered with "update all docs":

1. **Inspect** - establish local revisions, current changes and baseline coverage. Fetch only when required and authorized.
2. **Audit** - inspect relevant child source and doc changes. Present the staleness report with access and freshness limits.
3. **Per-repo workspace copies** - update affected authorized copies inline, or use bounded native delegation when justified and authorized. No automatic workspace commits.
4. **Workspace aggregation docs** — Update sequentially (do NOT parallelize) in order:
   - `infrastructure.md`
   - `project-structure.md`
   - `tech-stack.md`
   - `api-architecture.md`
5. **Cross-cutting flow / sequence docs** — Update last (e.g., end-to-end flow diagrams that span multiple services).

Per-repo copies (step 3) run first because aggregation docs (step 4) read from them. Flow docs go last because they depend on everything above.

## Documentation Standards

- Include `**Last Updated**: YYYY-MM-DD` after each H1 heading
- Use **tables** for inventories (endpoints, topics, packages)
- Follow existing format — consistency over perfection
- Link to per-repo docs rather than duplicating content
- Always present staleness report before making changes (unless in reconciliation mode)

## Safety Rules

- Never modify child repo source code
- Never paste sensitive data (credentials, PII, customer data) into docs
- When unsure, skip the repo rather than generating incorrect docs

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Expanding a workspace refresh into child changes | Keep writes within the authorized destination; separate child-doc requests require explicit scope. |
| Using glob/grep on child repo paths | Child repos are typically gitignored — use platform file reads to access them. |
| Updating docs without reading changed source | Always read source first — understand intent, not just file existence. |
| Rewriting entire doc sections | Surgical patches only — change what's actually stale. |
| Treating all file changes as behavioral | Renames and formatting changes don't need a doc update. |
| Updating deprecated repos as if they're evolving | They're snapshots — note that changes occurred, don't rewrite architecture. |
| Forgetting to update `**Last Updated**:` date | Every doc update must include the date line update. |
| Assuming local state matches current remote | State the inspected revision and freshness limit; fetch only when the task requires it and authorization covers it. |
| Updating cross-cutting flow docs before per-repo docs | Flow docs depend on per-repo docs — always update them last. |

## Review and knowledge follow-through

For knowledge candidates or post-merge architecture impact, first read the [shared review and knowledge contract](../../instructions/references/review-knowledge.md). This is distinct from the existing drift-queue mode: do not fabricate a queue or require an unavailable reconciliation skill. Inspect the actual integrated revision, update only affected authorized workspace sections or record a concrete no-impact reason, and use the collection's baseline receipt/accept process when present. Retain unresolved source gaps; a confirmed knowledge claim does not itself advance the documentation baseline.
