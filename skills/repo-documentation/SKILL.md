---
name: repo-documentation
description: "Use when documentation may be outdated — updating workspace copies at docs/architecture/{repo}/, refreshing workspace docs/architecture/ (infrastructure, project-structure, tech-stack, api-architecture), or auditing staleness across all repos"
---

# Repository Documentation Maintenance

## Overview

Detect and fix stale architecture documentation across the multi-repo workspace. Uses git commit history to find docs that haven't been updated since their source code changed, reads the changed code to understand behavioral impact, and surgically patches docs.

**Core principle:** Read changed source code to understand intent — don't just note that files changed.

## Cross-Skill References

- **REQUIRED:** `repo-management` — Repo manifest (local folder, GitHub owner/repo, default branch, repo type). Use for pre-flight branch checks and `git fetch`.
- **REQUIRED (when available):** `dispatching-parallel-agents` — Dispatch one subagent per repo for parallel operations (pre-flight, staleness detection, per-repo doc updates). Read this skill before any "update all" invocation.
- **RECOMMENDED:** a PR-creation skill — use after completing doc updates if the user wants to open a PR.

## Subagent Usage

**Use subagents for all parallelizable work.** Independent repos have no shared state — dispatch one subagent per repo whenever operating on multiple repos.

**Parallelize these operations:**

- Pre-flight `git fetch` + branch status checks (one subagent per repo)
- Staleness detection across repos (one subagent per repo)
- Per-repo workspace copy updates (one subagent per repo)

**Do NOT parallelize these operations:**

- Workspace-level doc updates (sequential — later docs may reference earlier ones)
- Cross-cutting flow / sequence docs (sequential — they depend on the workspace-level docs)

Each subagent receives:

- The repo's local folder, default branch, and repo type
- The specific operation (fetch, audit, or update)
- Instructions to commit per doc in the workspace root: `docs: update {repo} {doc-name}`

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
| **Reconciliation** | Invoked by `reconciliation` from a `*-drift-queue.md` entry | One repo per dispatch; archetype + queued source/doc paths supplied |

## Queue Contract (Reconciliation Mode)

When invoked by `reconciliation`, the caller passes the following typed inputs derived from the queue file at `docs/handoffs/reconciliation/*-drift-queue.md`:

| Input | Required | Source in queue | Behavior |
|---|---|---|---|
| `Repo` | yes | `## <repo-name>` heading | Scope of this dispatch. |
| `Archetype` | yes | `- Archetype: ` line | Drives Repo Type Behavior. Trust the queue value; do **not** re-derive from path heuristics. |
| `LastWorkspaceUpdate` | yes | `- Last workspace update: ` line | Bypass the staleness algorithm in Phase 2 — the queue already proved the workspace copy is stale. |
| `ChangedSourcePaths` | yes | `### Source paths changed` bullets | Read **exactly these** child repo files to assess behavioral impact in Phase 3 step 2. Do not re-glob the child repo. |
| `ChangedDocPaths` | optional | `### Doc paths changed` bullets | Read these child repo docs in Phase 3 step 3 to incorporate owning-team improvements. |

**Contract rules:**

- The queue is the authoritative wire format. If the queue says `Archetype: deprecated`, treat the repo as deprecated even if other workspace files suggest otherwise.
- Reconciliation mode **skips Phase 2 (Staleness Detection)** because the Forge Cycle already performed it. Go directly to Phase 3 with the supplied paths.
- After completing, hand control back to `reconciliation` so it can retire the queue file.

## Prerequisites

- **REQUIRED SKILL:** Read `repo-management` for repo manifest and branch status operations
- Repos must be cloned and on a clean branch (use `repo-management` to verify)
- For "update all" mode: read `dispatching-parallel-agents` (if available) for subagent dispatch patterns

## Phase 1 — Pre-flight

### Branch Status Check

Before any update, verify every repo in scope:

1. Run `git fetch` in each repo
2. Present status table:

| Repo | Branch | Behind | Action |
|------|--------|--------|--------|
| service-a | main | 0 | ✅ Include |
| service-b | feature/x | 3 | ⚠️ Behind main |

3. For repos not on default branch or behind remote: ask user to **include**, **skip**, or **switch to default branch**
4. Proceed only with confirmed repos

## Phase 2 — Staleness Detection

### Algorithm

For each workspace copy in scope:

```bash
# When was the workspace copy last updated?
WORKSPACE_DATE=$(git log -1 --format="%aI" -- docs/architecture/{repo}/tech-stack.md)

# Have source files changed in the child repo since then?
cd {repo}
SOURCE_CHANGES=$(git log --since="$WORKSPACE_DATE" --name-only --pretty=format: -- src/ *.csproj *.props)
# Identify child repo documentation directory:
# 1. Primary: {repo}/docs/
# 2. Secondary/Legacy: {repo}/docs/architecture/
# 3. Fallback: {repo}/README.md

cd {repo}
if [ -d "docs" ]; then
  CHILD_DOC_DIR="docs"
elif [ -d "docs/architecture" ]; then
  CHILD_DOC_DIR="docs/architecture"
else
  CHILD_DOC_DIR="README.md"
fi

# Has the child repo's own docs directory been updated since then?
DOC_CHANGES=$(git log --since="$WORKSPACE_DATE" --name-only --pretty=format: -- $CHILD_DOC_DIR)
cd ..
```

If either `SOURCE_CHANGES` or `DOC_CHANGES` is non-empty, the workspace copy is stale.

> **Note:** Use `git log` dates on the workspace copy, not the `**Last Updated**:` front-matter date. The git date is authoritative — front-matter dates may use varied formats and may not reflect the actual last commit date.

> **Child repo doc changes:** If the owning team updated their `{repo}/docs/` (or legacy `{repo}/docs/architecture/`) files, those improvements should be incorporated into the workspace copy. This lets workspace copies benefit from team knowledge without requiring teams to update workspace files directly.

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

For **audit only** mode: stop here. For update modes: ask user to confirm which stale docs to update, then proceed.

## Phase 3 — Update Execution

For each confirmed stale workspace copy at `docs/architecture/{repo}/`:

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
7. **Commit** — one commit per doc: `docs: update {repo} {doc-name}`

**⚠️ Never modify child repo files.** All writes go to `docs/architecture/{repo}/` workspace copies only.

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

To maintain organizational consistency across all microservices, each repository's local `docs/` folder (and its mirrored snapshot under `docs/architecture/{repo}/`) must enforce the following three core architecture files structured with standardized subheaders mapped directly to Council role domains:

#### 1. `api-architecture.md` Template Blueprint
Coordinated by `the-builder`, `the-sentinel`, and `the-relay`.

*   **Header**: `# API Architecture — {Solution-Name}`
*   **Subheader 1**: `## 1. Endpoints & Route Definitions` (`the-builder`)
    *   *Content*: ASP.NET Core Minimal API endpoint tables with Verb, Path, Operation Name, Description, and Auth Scope details.
*   **Subheader 2**: `## 2. API Authorization & JWT Scopes` (`the-sentinel`)
    *   *Content*: Okta/OIDC scopes, client credentials policies, mock token variables for BDD tests, and secret hygiene practices.
*   **Subheader 3**: `## 3. High-Integrity Write & Transaction Workflows` (`the-coder` / `the-curator`)
    *   *Content*: Logical Command Command/Write handler pipelines, dapper persistence isolation, separate reader/writer pooling, and Redis sliding expiration invalidate calls.
*   **Subheader 4**: `## 4. Message Queue & Event Contracts` (`the-relay`)
    *   *Content*: Kafka events, GCP Pub/Sub topics, schema formats, retry/dead-letter setups, and sequence flow diagrams.

#### 2. `project-structure.md` Template Blueprint
Coordinated by `the-architect`, `the-coder`, and `the-prover`.

*   **Header**: `# Project Structure — {Solution-Name}`
*   **Subheader 1**: `## 1. Solution Layout & Clean Onion Layers` (`the-architect` / `the-coder`)
    *   *Content*: Visual inward-pointing reference diagrams, namespaces, and solution project filter (`.slnx`) setups.
*   **Subheader 2**: `## 2. Assembly Boundaries & Layer Responsibilities` (`the-coder`)
    *   *Content*: Assembly layers (e.g. `.Core`, `.Data`, `.Api`). Rigorously enforce that the pure `.Core` assembly contains zero physical SQL/Dapper or Redis/caching NuGet package dependencies.
*   **Subheader 3**: `## 3. In-Memory, Integration & Spec Test Suites` (`the-prover`)
    *   *Content*: MSTest/NSubstitute directories, Arrange/Act/Assert boundaries, Gherkin Reqnroll specs, and Testcontainers.

#### 3. `tech-stack.md` Template Blueprint
Coordinated by `the-purifier`, `the-curator`, `the-watcher`, and `the-pipelineer`.

*   **Header**: `# Technical Stack — {Solution-Name}`
*   **Subheader 1**: `## 1. Runtime Frameworks & Core Libraries` (`the-purifier` / `the-architect`)
    *   *Content*: Core runtime versions (e.g. .NET 10.0), primary framework libraries, and centralized package management props.
*   **Subheader 2**: `## 2. Low-Latency Database Persistences & Caching` (`the-curator`)
    *   *Content*: PostgreSQL ANSI ANSI syntax, vertical alignments for schema columns/constraints, and Redis caching topologies.
*   **Subheader 3**: `## 3. Distributed Telemetry & Structured Logging` (`the-watcher`)
    *   *Content*: Serilog structure formats, OpenTelemetry span metrics, Grafana Loki exporter setups, and alerts.
*   **Subheader 4**: `## 4. CI/CD Pipelines & Container Release Specifications` (`the-pipelineer` / `the-provisioner`)
    *   *Content*: TeamCity configurations, Octopus deployment scripts, Dockerfile setups, and hosting GKE environments.

## Phase 4 — "Update All" Orchestration

When triggered with "update all docs":

1. **Fetch** — `git fetch` all repos (parallel)
2. **Audit** — Staleness check across all repos (parallel). Present full report. Checks both child repo source code AND child repo doc changes since last workspace sync.
3. **Per-repo workspace copies** — Dispatch one subagent per stale repo. Each subagent reads child repo source/docs and updates `docs/architecture/{repo}/` workspace copies. Commits to workspace root.
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
| Modifying child repo files | **Never write to child repos.** All doc updates go to workspace `docs/architecture/{repo}/` copies only. |
| Using glob/grep on child repo paths | Child repos are typically gitignored — use platform file reads to access them. |
| Updating docs without reading changed source | Always read source first — understand intent, not just file existence. |
| Rewriting entire doc sections | Surgical patches only — change what's actually stale. |
| Treating all file changes as behavioral | Renames and formatting changes don't need a doc update. |
| Updating deprecated repos as if they're evolving | They're snapshots — note that changes occurred, don't rewrite architecture. |
| Forgetting to update `**Last Updated**:` date | Every doc update must include the date line update. |
| Running updates on repos behind remote | Pre-flight catches this — always fetch and check first. |
| Updating cross-cutting flow docs before per-repo docs | Flow docs depend on per-repo docs — always update them last. |
