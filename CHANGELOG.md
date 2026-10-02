# Changelog

All notable changes to the Council of Mikes are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Versioning convention for a skill library:**
> - **MAJOR** — breaking change to Council member names, routing phrases, or the Pre-Submit SOP phase contract.
> - **MINOR** — new Council member, new procedure, or additive change to an existing SKILL.md.
> - **PATCH** — wording, doc fixes, link repairs, frontmatter tweaks that do not change behavior.

---

## [2.2.0] — 2026-10-02

### Added
- **Autonomous Orchestration Engine (`tools/council/`)**: Production-grade LangGraph compiled state graph multi-agent orchestrator with Gate 1 & Gate 2 human-in-the-loop approvals, automated test-repair retry loops, SQLite persistent checkpoints, and 11 automated unit test suites.
- **The Coordinator (`the-coordinator`)**: Promoted to core 15th member of The Council, specializing in JIRA lifecycles, sprint backlogs, INVEST user stories, Definition of Ready (DoR), and Definition of Done (DoD).
- **Core Workflow Superpowers (`skills/`)**: Integrated 9 formal operational workflows (`brainstorming`, `writing-plans`, `handoff`, `test-driven-development`, `systematic-debugging`, `the-council-orchestration`, `using-superpowers`, `verification-before-completion`, `repo-documentation`).
- **One-Click Provisioner (`scripts/setup-council.ps1`)**: Turnkey machine setup script provisioning `~/.gemini/` directories, specialist skills, host lifecycle hooks, and verifying environment health.
- **Universal Workspace Validator (`scripts/validate_workspace.py`)**: Zero-dependency cross-platform 5-phase integrity validator.
- **AI-Friendly Architecture Specification (`docs/The-Council-Structure.md`)**: Full file-level directory structure, artifact routing taxonomy matrix, and helpful copy-paste prompts.

### Changed
- **Modernized 2026 Stack Across All Specialists**: Refactored all 15 members to modern enterprise standards: PostgreSQL, strict Entity Framework Core 10, .NET Aspire Testing with real containers, Scalar OpenAPI 3.0, Okta preview OIDC token flows, and React Router 7 / Deno runtime.
- **Restored Full-Fidelity Personas**: Re-injected rich engineering decision matrices (Records vs Classes, HTTP status codes, Testing Pyramid, CQRS trade-offs) and distinctive senior lead behavioral profiles across all 15 members.
- **Line Ending Normalization**: Added `.gitattributes` enforcing automated LF normalization across all code and text assets.

---

## [1.2.1] — 2026-05-21

### Fixed
- **`SECURITY.md` Supported Versions table** — bumped to reflect v1.2.x as Active, v1.1.x as Critical-fixes-only, < 1.1 as Unsupported (was lagging the release).

### Added
- **`scripts/validate-council.ps1` check 5** — `[[wikilink]]` resolution against Council members, companion skills, and any markdown file in the repo. Previously the validator only checked `[text](url)` style links, so a typo in a wikilink could ship silently.
- **`scripts/validate-council.ps1` check 6** — employer-specific fingerprint scan as a CI guardrail (currently clean; this prevents future regressions).
- **`CITATION.cff`** — academic citation metadata for v1.2.0.
- **`.github/DISCUSSION_TEMPLATE/`** — show-and-tell, idea, and q-and-a discussion templates.

---

## [1.2.0] — 2026-05-21

### Added
- **`examples/` folder** with three annotated transcripts demonstrating real Council interactions:
  - `01-architect-design-review.md` — The Architect leading a multi-specialist design before any code is written.
  - `02-purifier-quality-sweep.md` — The Purifier catching real issues (null-safety, contract gaps, domain question) the original "looks fine" code missed.
  - `03-gatekeeper-presubmit-gate.md` — The Gatekeeper issuing a `BLOCKED` verdict on a "tests-pass-therefore-ship" change. The canonical example of why Phase 8 exists.
- **Quick Start section** in `README.md` — 60-second install + first invocation path.
- **Mermaid routing-flow diagram** in `README.md` showing `@TheCouncil` → topic detection → member → Gatekeeper → ship/block.
- **SVG banner** (`assets/council-banner.svg`) embedded at top of README — all 15 members with role labels, version-controllable, renders inline on GitHub.
- Directory-structure block in README updated to include `examples/`, `assets/`, `templates/`, `scripts/`.

---

## [1.1.0] — 2026-05-21

### Added
- **YAML frontmatter** on every Council member SKILL.md (`name`, `description`) so AI skill loaders (Anthropic Agent Skills, Claude Code, Cursor, Copilot) can auto-discover Council members instead of requiring explicit `@`-mention.
- `CONTRIBUTING.md` — how to add a Council member, the recursive Gatekeeper rule, doc-lint expectations.
- `SECURITY.md` — vulnerability and skill-injection reporting flow.
- `.github/CODEOWNERS` — catch-all ownership.
- `.github/PULL_REQUEST_TEMPLATE.md` — embeds the Gatekeeper Report block as required output.
- `.github/ISSUE_TEMPLATE/` — structured forms for bug, feature, and new-member proposals.
- `.github/workflows/doc-lint.yml` + `scripts/validate-council.ps1` — CI that enforces frontmatter presence, member-count consistency across docs, internal link resolution, and 10-vs-11-phase consistency in the SOP.
- README badge row.

### Changed
- None.

### Fixed
- None.

---

## [1.0.0] — 2026-05-21

First public release of the Council of Mikes.

### Added
- 15 Council member skills (`council/the-*/SKILL.md`).
- 9 companion skills (`skills/*/SKILL.md`) for Temporal, Aspire, protobuf, ARTS, QA, composition patterns, web design guidelines.
- 11-phase Pre-Submit SOP (`procedures/code-change-pre-submit-sop.md`) owned by The Gatekeeper.
- `/pre-submit` slash command (`prompts/pre-submit.prompt.md`).
- `@TheCouncil` routing snippet (`prompts/council-routing.snippet.md`).
- Agent guides: `AGENTS.md`, `.github/copilot-instructions.md`.

### Changed
- Branding pass: every reference uses `The X — Lead-style role label`. Member count standardized at 15 everywhere.
- Pre-Submit SOP wording aligned to "11-phase" across all surfaces (was inconsistently "10-phase" in three places).

### Fixed
- `council/council.md` Members table previously listed 14 members; The Gatekeeper now appears in roster, routing, and Best Prompts.
- Clone URL in `README.md` and `AGENTS.md` aligned to actual remote (`github.com/underwms/council-of-mikes`).
- Title-case `The X` proper-noun usage in cross-references across `the-architect`, `the-coder`, `the-codex`, `the-renderer`, `the-sentinel` SKILL.md files.

---

[Unreleased]: https://github.com/underwms/council-of-mikes/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/underwms/council-of-mikes/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/underwms/council-of-mikes/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/underwms/council-of-mikes/releases/tag/v1.0.0
