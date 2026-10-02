---
title: Council V2 Architectural Hierarchy & Directory Structure
description: Canonical file-level directory structure, specialist skill contracts, workflow superpowers, and multi-repository workspace topology for Council V2.
version: 2.2.0
author: Mike Underwood
authority: Fulfillment and Rate Engine Pod Architectural Governance
workspace_root: workspace_root\
host_root: '%USERPROFILE%\.gemini\'
tags:
  - council-v2
  - architecture
  - directory-structure
  - gemini-cli
  - agentic-governance
last_updated: 2026-10-02
---

# Council V2 Architectural Hierarchy & Directory Structure

> **Authority**: Fulfillment and Rate Engine Pod Architectural Governance  
> **Workspace Scope**: `workspace_root\` (Cross-cutting microservices: `orderapi`, `adminportal`, `inventoryservice`, `paymentservice`, etc.)  
> **Host Scope**: `%USERPROFILE%\.gemini\` (Global host guardrails, Council V2 specialist skills, MemoryForge ephemeral cache)  
> **Target Environment**: Windows 11 Enterprise (`win32`) on PowerShell 7+

---

## 1. Overview & AI Ingestion Directives

This document is the authoritative structural blueprint of the **Council V2** multi-agent development environment. It details the complete file-level hierarchy across the host workstation (`%USERPROFILE%\`) and the project workspace (`workspace_root\`).

### AI Agent Operational Rules
When navigating or operating within this workspace, AI agents MUST observe the following boundaries:
1. **Context Root**: The primary project instructions reside at `workspace_root\GEMINI.md`, which recursively imports Tier 2 Pod Rules and Workflow Superpowers.
2. **Specialist Call-Signs ("WHO")**: Active call-signs (`[THE ARCHITECT]`, `[THE CODER]`, `[THE CURATOR]`, `[THE PROVER]`, `[THE PURIFIER]`, `[THE GATEKEEPER]`, `[THE CODEX]`, etc.) MUST prefix domain actions according to the 15 specialist packages under `%USERPROFILE%\.gemini\skills\`.
3. **Workflow Superpowers ("HOW")**: Operational lifecycles (TDD, Systematic Debugging, Brainstorming, Verification) reside under `workspace_root\.gemini\skills\` and must be invoked prior to modifying code.
4. **MemoryForge Ephemeral Boundary**: All transient scratchpads, session heartbeats (`active_session_backlog.md`), and developer handoffs (`active_handoff.md`) MUST be confined to `%USERPROFILE%\.gemini\tmp\%USERNAME%\memory\`. Never commit ephemeral artifacts to Git.
5. **Multi-Repo Boundary**: Every service subdirectory under `workspace_root\` is an independently cloned Git repository. Always execute commands within the target child repository.

---

## 2. Complete File-Level Directory Structure

```text
%USERPROFILE%\
├── .geminiignore                                       <-- User profile indexing exclusions (Restrains scanning AppData, Downloads, caches)
└── .gemini\
    ├── .rules\
    │   └── rules.md                                    <-- Tier 1: Global Invariant Host System & Shell Guardrails (win32, PS7+, atomic commands)
    ├── policies\
    │   └── auto-allow.toml                             <-- CLI Tool Auto-Execution Policy (Unrestricted tool authorization in YOLO mode)
    ├── scripts\
    │   ├── onboard.py                                  <-- Automatic Session Onboarding & Verification Protocol (Restores context, scrubs temp, audits health)
    │   └── heartbeat_hook.py                           <-- Deterministic AfterAgent lifecycle hook (Maintains MemoryForge state bridge)
    ├── skills\                                         <-- Council V2 Specialists ("WHO" - Independent personas providing domain doctrine)
    │   ├── the-architect\                              <-- Solutions Architecture Lead (Onion Architecture, CQRS, multi-specialist orchestration)
    │   │   ├── SKILL.md                                <-- Execution contract (Runtime persona, architectural boundaries, Gate 1 decomposition rules)
    │   │   └── references\the-architect.md             <-- Domain reference card & wikilink graph node
    │   ├── the-builder\                                <-- Backend API Lead (High-throughput Minimal APIs, OpenAPI/Scalar, CLI host automation)
    │   │   ├── SKILL.md                                <-- Execution contract (Minimal API endpoints, REST semantics, script automation)
    │   │   └── references\the-builder.md               <-- API design reference card & wikilink graph node
    │   ├── the-coder\                                  <-- C# Development Lead (Idiomatic C# 10-14, SOLID, pattern matching, async purity)
    │   │   ├── SKILL.md                                <-- Execution contract (Clean Domain/Application code, primary constructors, collection expressions)
    │   │   └── references\the-coder.md                 <-- C# coding reference card & wikilink graph node
    │   ├── the-codex\                                  <-- Documentation & Knowledge Lead (Repo architecture wikis, ADRs, Mermaid diagrams, XML docs)
    │   │   ├── SKILL.md                                <-- Execution contract (Documentation standards, ADR chronologies, Markdown formatting)
    │   │   └── references\the-codex.md                 <-- Documentation reference card & wikilink graph node
    │   ├── the-coordinator\                            <-- Agile Delivery Lead (JIRA lifecycles, sprint backlogs, INVEST stories, DoD/DoR verification)
    │   │   ├── SKILL.md                                <-- Execution contract (Story decomposition, acceptance criteria, delivery cadence)
    │   │   └── references\the-coordinator.md           <-- Agile delivery reference card & wikilink graph node
    │   ├── the-curator\                                <-- Database & Persistence Lead (PostgreSQL relational schemas, strict EF Core 10, migrations)
    │   │   ├── SKILL.md                                <-- Execution contract (EF Core DbSets, Fluent API mappings, zero Dapper / zero Redis doctrine)
    │   │   └── references\the-curator.md               <-- PostgreSQL & EF Core reference card & wikilink graph node
    │   ├── the-gatekeeper\                             <-- Pre-Submit Quality Gate Lead (11-Phase SOP enforcement, workspace integrity, PR reviews)
    │   │   ├── SKILL.md                                <-- Execution contract (Pre-submit checklist enforcement, Gate 2 approval sign-off)
    │   │   └── references\the-gatekeeper.md            <-- Quality gate reference card & wikilink graph node
    │   ├── the-pipelineer\                             <-- DevOps & CI/CD Lead (Automated build pipelines, TeamCity, Octopus Deploy, Git branching)
    │   │   ├── SKILL.md                                <-- Execution contract (CI build targets, deployment gates, branch management)
    │   │   └── references\the-pipelineer.md            <-- CI/CD pipeline reference card & wikilink graph node
    │   ├── the-prover\                                 <-- Testing & Validation Lead (MSTest.Sdk unit testing, NSubstitute, Reqnroll BDD, Aspire suites)
    │   │   ├── SKILL.md                                <-- Execution contract (100% test pass enforcement, compiler diagnostic parsing, zero mock DBs)
    │   │   └── references\the-prover.md                <-- Testing doctrine reference card & wikilink graph node
    │   ├── the-provisioner\                            <-- Platform Hosting Lead (GKE container topology, Kubernetes manifests, HPA autoscaling)
    │   │   ├── SKILL.md                                <-- Execution contract (Kubernetes resources, ingress definitions, container runtime sizing)
    │   │   └── references\the-provisioner.md           <-- Cloud topology reference card & wikilink graph node
    │   ├── the-purifier\                               <-- Code Quality & Static Analysis Lead (Roslyn static analysis, SonarQube tripwires, dead code pruning)
    │   │   ├── SKILL.md                                <-- Execution contract (Zero warnings policy, code deduplication, formatting compliance)
    │   │   └── references\the-purifier.md              <-- Code cleanliness reference card & wikilink graph node
    │   ├── the-relay\                                  <-- Distributed Messaging Lead (Apache Kafka event streaming, topic partitioning, CloudEvents schemas)
    │   │   ├── SKILL.md                                <-- Execution contract (Kafka consumer groups, message contracts, partition key strategy)
    │   │   └── references\the-relay.md                 <-- Event streaming reference card & wikilink graph node
    │   ├── the-renderer\                               <-- Frontend UI Lead (React components, Deno runtime, TypeScript safety, CSS modules, Kiwi design)
    │   │   ├── SKILL.md                                <-- Execution contract (Pixel-perfect UI layout, client/server routing, state machines)
    │   │   └── references\the-renderer.md              <-- UI engineering reference card & wikilink graph node
    │   ├── the-sentinel\                               <-- InfoSec & Authentication Lead (Okta preview OIDC tokens, dynamic IAuthorizationPolicyProvider)
    │   │   ├── SKILL.md                                <-- Execution contract (Dynamic policy generation, secret isolation, PII sanitization)
    │   │   └── references\the-sentinel.md              <-- Security & auth reference card & wikilink graph node
    │   └── the-watcher\                                <-- Observability & Telemetry Lead (OpenTelemetry tracing, Serilog logging, Grafana Loki queries)
    │       ├── SKILL.md                                <-- Execution contract (Correlation IDs, structured log levels, distributed trace spans)
    │       └── references\the-watcher.md               <-- Observability reference card & wikilink graph node
    ├── tmp\%USERNAME%\memory\                          <-- MemoryForge Ephemeral Storage (Session state, handoffs, and developer preferences)
    │   ├── MEMORY.md                                   <-- Private project memory index (Ports, auth triage notes, architectural shifts)
    │   ├── active_handoff.md                           <-- Active developer handoff written by @handoff skill
    │   ├── active_session_backlog.md                   <-- Chronological session heartbeat log (appended on every major milestone)
    │   ├── active_session_backlog.archive.md           <-- Archived historical milestones (automatically rotated when active > 100 entries)
    │   ├── heartbeat_state.json                        <-- Session runtime state bridge (Tracks active session, event, and timestamp)
    │   ├── preferences.md                              <-- Developer-specific workstation tooling & IDE preferences
    │   └── adr_api_versioning.md                       <-- Private mirror of DARCH API Versioning Architecture Decision Record
    └── GEMINI.md                                       <-- Global Agent Context (Tier 1 rules, Mike's persona, Council specialist catalog)
	
workspace_root\	
├── GEMINI.md                                           <-- Native Gemini CLI context root (Imports .gemini/GEMINI.md for deterministic ingestion)
├── .geminiignore                                       <-- Workspace indexing exclusions (Restrains scanning bin, obj, node_modules, .vs)
├── .gemini\	
│   ├── .rules\
│   │   └── rules.md                                    <-- Tier 2: Pod Architecture Rules (Clean/Onion architecture, EF Core 10, no Redis/Dapper, Aspire)
│   ├── skills\                                         <-- Workflow Superpowers ("HOW" - Operational workflows for executing tasks safely)
│   │   ├── brainstorming\                              <-- Collaborative design & specification formulation prior to code modification
│   │   │   ├── SKILL.md                                <-- Workflow instructions (Interactive questioning, visual companion setup, design review)
│   │   │   ├── spec-document-reviewer-prompt.md        <-- Subagent review template for design specifications
│   │   │   ├── visual-companion.md                     <-- Architecture diagramming & UI layout mockup guidance
│   │   │   └── scripts\                                <-- HTML/JS visual mockup live server runtime
│   │   ├── handoff\                                    <-- Incremental session persistence protocol
│   │   │   └── SKILL.md                                <-- Workflow instructions (Writes active_handoff.md to ephemeral MemoryForge cache)
│   │   ├── repo-documentation\                         <-- Repository knowledge base & architecture documentation maintenance
│   │   │   └── SKILL.md                                <-- Workflow instructions (Maintaining docs/ hierarchy, wikilinks, and ADR records)
│   │   ├── systematic-debugging\                       <-- Structured 4-phase root-cause analysis workflow for regressions and test failures
│   │   │   ├── SKILL.md                                <-- Workflow instructions (Reproduction, isolation, root cause diagnosis, regression test)
│   │   │   ├── defense-in-depth.md                     <-- Multi-layered verification principles
│   │   │   ├── root-cause-tracing.md                   <-- Backward execution path tracing techniques
│   │   │   └── condition-based-waiting.md              <-- Flaky test prevention using deterministic polling
│   │   ├── test-driven-development\                    <-- Strict Red-Green-Refactor implementation discipline
│   │   │   ├── SKILL.md                                <-- Workflow instructions (Write failing test first, make it pass with minimal code, refactor)
│   │   │   └── testing-anti-patterns.md                <-- Catalog of testing anti-patterns to detect and avoid
│   │   ├── the-council-orchestration\                  <-- LangGraph autonomous state graph orchestrator integration
│   │   │   └── SKILL.md                                <-- Workflow instructions (Gate 1 decomposition, multi-specialist routing, Gate 2 sign-off)
│   │   ├── using-superpowers\                          <-- Meta-skill governing skill discovery and tool invocation discipline
│   │   │   ├── SKILL.md                                <-- Mandatory invocation rules (Check for skills before action, zero rationalization)
│   │   │   └── references\                             <-- Tool mapping reference cards (gemini-tools.md, copilot-tools.md, codex-tools.md)
│   │   ├── verification-before-completion\             <-- Mandatory pre-completion evidence gathering
│   │   │   └── SKILL.md                                <-- Workflow instructions (Empirical test runs, validator execution, PR checklist generation)
│   │   └── writing-plans\                              <-- Granular sub-task planning for approved designs
│   │       ├── SKILL.md                                <-- Workflow instructions (Bite-sized plan creation, testing strategy definition)
│   │       └── plan-document-reviewer-prompt.md        <-- Subagent review template for implementation plans
│   ├── specialists\                                    <-- Council V2 Specialists Master Source (Mirrored in Git for one-click developer distribution)
│   │   ├── the-architect\                              <-- Complete mirrored specialist package (SKILL.md & references/)
│   │   ├── the-builder\                                <-- Complete mirrored specialist package (SKILL.md & references/)
│   │   ├── the-coder\                                  <-- Complete mirrored specialist package (SKILL.md & references/)
│   │   └── ... (all 15 specialist packages)
│   └── GEMINI.md                                       <-- Pod Workspace Rules & Enforcements (Specialist call-signs, MemoryForge, Git multi-repo rules)
├── docs\                                               <-- Centralized Documentation & Architecture Hierarchy
│   ├── architecture\                                   <-- Cross-cutting and per-service architectural specifications
│   │   ├── corporate-architecture-rules.md             <-- DARCH enterprise governance (API versioning, Entra ID auth, NuGet packages)
│   │   ├── council-v2-documentation.md                 <-- Comprehensive Council V2 architecture, specialist roles, and orchestration guide
│   │   ├── adr-api-versioning.md                       <-- Architecture Decision Record for URL-based API versioning strategy
│   │   ├── api-architecture.md                         <-- Cross-service API communication patterns and data flow contracts
│   │   ├── tech-stack.md                               <-- Pod technology matrix (.NET 10, EF Core, PostgreSQL, React Router, Deno)
│   │   ├── project-structure.md                        <-- Workspace directory layout, repository boundaries, and solution targeting
│   │   └── {service}\ (e.g. orderapi\, rewardsapi\) <-- Per-service architectural deep-dives, tech stacks, and domain structures
│   ├── procedures\                                     <-- Standard Operating Procedures (SOPs) and governance workflows
│   │   ├── code-change-pre-submit-sop.md               <-- 11-Phase Pre-Submit Quality Gate SOP (from design to PR review simulation)
│   │   └── user-story-template.md                      <-- INVEST-compliant Gherkin user story template
│   └── superpowers\                                    <-- Technical specifications and implementation plans for autonomous capabilities
│       ├── specs\                                      <-- Formal design specs (2026-09-29-council-orchestration-design.md)
│       └── plans\                                      <-- Multi-phase execution plans (2026-09-29-council-orchestration-engine.md)
├── tools\                                              <-- Workspace Automation Tooling
│   └── council\                                        <-- Autonomous Council Orchestration Engine (Option B - LangGraph compiled state machine)
│       ├── council\                                    <-- Core engine Python package
│       │   ├── __init__.py                             <-- Package initialization and exports
│       │   ├── __main__.py                             <-- CLI entrypoint module (python -m council)
│       │   ├── cli.py                                  <-- Rich terminal UI (Gate 1/2 prompts, progress spinners, --dry-run, --resume)
│       │   ├── graph.py                                <-- Compiled LangGraph StateGraph (7 specialist nodes, conditional retry routing)
│       │   ├── state.py                                <-- CouncilState schema (Pydantic v2 data models, step counts, error fingerprints)
│       │   ├── runner.py                               <-- Cross-platform SubprocessRunner (pwsh on Win32, zsh on macOS, atomic commands)
│       │   ├── specialists.py                          <-- SpecialistLoader (Discovers 15 Council packages, parses personas and reference cards)
│       │   ├── checkpoint.py                           <-- SQLite persistent checkpointer (Targets ephemeral memory for crash recovery)
│       │   ├── config.py                               <-- Multi-provider LLM factory (Google Gemini, Anthropic Claude, OpenAI GPT)
│       │   └── tools\                                  <-- Specialist-invoked execution tools
│       │       ├── file_tools.py                       <-- Sandboxed file operations (read, write, replace) with anti-loop call deduplication
│       │       ├── test_runner.py                      <-- TestSuiteRunner with C# MSTest and Deno test diagnostic compiler error parsing
│       │       └── validator_bridge.py                 <-- Programmatic bridge to validate_workspace.py
│       ├── tests\                                      <-- Automated engine test suites (11/11 passing 100% green)
│       │   ├── test_checkpoint.py                      <-- Verification of SQLite session persistence and state restoration
│       │   ├── test_cli.py                             <-- Verification of Rich CLI arguments, Gate prompts, and dry-run execution
│       │   ├── test_config.py                          <-- Verification of LLM provider instantiation and environment variable resolution
│       │   ├── test_file_tools.py                      <-- Verification of sandboxed file mutation, path resolution, and call deduplication
│       │   ├── test_graph.py                           <-- Verification of LangGraph state transitions, specialist routing, and step limits
│       │   ├── test_loop_safeguards.py                 <-- Verification of 4 anti-loop circuit breakers (step ceiling, error hashing, dedup)
│       │   ├── test_runner.py                          <-- Verification of cross-platform shell process spawning and exit code tracking
│       │   ├── test_specialists.py                     <-- Verification of Council V2 specialist package loading and frontmatter extraction
│       │   ├── test_state.py                           <-- Verification of CouncilState schema serialization and validation
│       │   ├── test_test_runner.py                     <-- Verification of dotnet test and deno test output parsing and failure extraction
│       │   └── test_validator.py                       <-- Verification of workspace integrity validator rules and report generation
│       ├── pyproject.toml                              <-- Python package metadata and tool dependencies
│       ├── requirements.txt                            <-- Pinned dependencies (langgraph, langchain-core, pydantic, rich)
│       └── README.md                                   <-- Engine architecture guide, CLI arguments, and specialist routing reference
├── scripts\                                            <-- Host Automation & Verification Scripts
│   ├── setup-council.ps1                               <-- One-Click Developer Machine Provisioner (Installs ~/.gemini/, skills, hooks, and audits health)
│   ├── convene.py                                      <-- Ceremonial runner: Ingests user prompt, cleans markdown, launches council engine
│   ├── validate-workspace.ps1                          <-- PowerShell workspace integrity validator (5-Phase audit: SKILLs, imports, wikilinks, syntax, host skills)
│   ├── validate_workspace.py                           <-- Universal Python workspace integrity validator (5-Phase audit: cross-platform, zero dependencies)
│   ├── heartbeat_hook.py                               <-- Host AfterAgent lifecycle hook (Maintains MemoryForge state bridge)
│   ├── onboard.py                                      <-- Automatic Session Onboarding & Verification Protocol (Restores context, scrubs temp, audits health)
│   ├── rate_audit.py                                   <-- Multi-layered rate engine telemetry, Kafka consumer, and Okta diagnostic audit runner
│   └── screenshot-rename.ps1                           <-- Helper script to standardize visual artifact screenshot filenames
└── {PROJECT}\                                          <-- Independent Cloned Git Repositories (Multi-repo workspace discipline)
    └── docs\                                           <-- Project Documentation & Architecture
        ├── api-architecture.md                         <-- Project API communication patterns and data flow contracts
        ├── project-structure.md                        <-- Project directory layout, assembly boundaries & layer responsibilities
        └── tech-stack.md                               <-- Project technology matrix (.NET 10, EF Core, PostgreSQL, React Router, Deno)
```

---

## 3. Artifact & Persistence Routing Standard

To ensure absolute consistency across developers and AI subagents, all generated and managed files MUST strictly adhere to the following routing standard:

| Artifact Category | Canonical Path | Governed By / Tooling | Target Audience & Visibility |
| :--- | :--- | :--- | :--- |
| **Design Specifications** | `workspace_root/docs/superpowers/specs/` | `@brainstorming` | Workspace / Architecture |
| **Implementation Plans** | `workspace_root/docs/superpowers/plans/` | `@writing-plans` | Workspace / Developers |
| **Workspace Architecture** | `workspace_root/docs/architecture/` | `[THE ARCHITECT]`, `[THE CODEX]` | Pod-Wide Governance |
| **Standard Operating Procedures** | `workspace_root/docs/procedures/` | `[THE GATEKEEPER]` | All Engineers & AI Agents |
| **Project-Level Docs** | `{PROJECT}/docs/` | `@repo-documentation` | Service-Specific Internal Wiki |
| **MemoryForge Ephemeral Cache** | `%USERPROFILE%\.gemini\tmp\%USERNAME%\memory\` | `@handoff`, Host scripts | Machine-Local (Never in Git) |
| **Global CLI Configuration** | `%USERPROFILE%\.gemini\` | Host System | Cross-Workspace (User Scope) |
| **Workspace Context & Rules** | `workspace_root\GEMINI.md` & `.gemini\` | Pod Lead | Workspace Scope |
| **Agile Stories & Temp Artifacts** | `workspace_root/temp/` | `[THE COORDINATOR]` | Active Sprint Management |
| **Service Code & Unit Tests** | `{PROJECT}/src/` and `{PROJECT}/tests/` | `[THE CODER]`, `[THE PROVER]` | Independent Cloned Git Repos |

---

## 4. Helpful Prompts

### One-Click Developer Onboarding
To provision a new developer workstation with the complete Council V2 framework:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-council.ps1
```

### Convening The Full Council
To initiate an autonomous multi-specialist orchestration cycle (Architect -> Curator -> Coder -> Prover -> Purifier -> Gatekeeper):
```text
Convene the Council: Implement {feature description} across {target microservice}
```

### Specialist Member Invocations
To invoke individual specialists for targeted domain tasks:
- **The Architect (`@the-architect`)**: `"@the-architect evaluate whether we should use CQRS or standard queries for {feature}"`
- **The Builder (`@the-builder`)**: `"@the-builder design the Minimal API endpoint contract and route group for {endpoint}"`
- **The Coder (`@the-coder`)**: `"@the-coder refactor {service} to use modern C# 13 primary constructors and pattern matching"`
- **The Codex (`@the-codex`)**: `"@the-codex author an Architecture Decision Record (ADR) and Mermaid diagram for {decision}"`
- **The Coordinator (`@the-coordinator`)**: `"@the-coordinator decompose Epic {KEY} into INVEST-compliant Gherkin user stories"`
- **The Curator (`@the-curator`)**: `"@the-curator create domain entities and configure EF Core Fluent API mappings for {table}"`
- **The Gatekeeper (`@the-gatekeeper`)**: `"@the-gatekeeper execute the 11-phase pre-submit quality gate on our branch"`
- **The Pipelineer (`@the-pipelineer`)**: `"@the-pipelineer verify TeamCity build steps and configure deployment promotion gates"`
- **The Prover (`@the-prover`)**: `"@the-prover write unit tests with NSubstitute and author an Aspire integration test"`
- **The Provisioner (`@the-provisioner`)**: `"@the-provisioner configure the Kubernetes GKE deployment manifest with resource limits"`
- **The Purifier (`@the-purifier`)**: `"@the-purifier run a static analysis sweep to eliminate compiler warnings and linter errors"`
- **The Relay (`@the-relay`)**: `"@the-relay design the Kafka CloudEvents schema for {event} with partition keys"`
- **The Renderer (`@the-renderer`)**: `"@the-renderer build the interactive form controls and diff viewer in React Router"`
- **The Sentinel (`@the-sentinel`)**: `"@the-sentinel audit endpoint authorization and dynamic scope policy generation"`
- **The Watcher (`@the-watcher`)**: `"@the-watcher write the Grafana Loki LogQL query to isolate {service} error spikes"`

### Repository Documentation Synchronization
To generate or refresh repository-level documentation matching the `{PROJECT}\docs\` specification:
```text
Run the @repo-documentation skill for project {PROJECT}.
```

### Pre-Submit Verification
Before finalizing any pull request or completing code changes:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-workspace.ps1
```

### Session Checkpoint & Handoff
To persist active progress and record a formal checkpoint in MemoryForge:
```text
Run the @handoff skill to checkpoint session progress.
```
