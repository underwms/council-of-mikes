# The Council

**Engineering roles, shared instructions, and practical workflows for native AI coding clients.**

The Council helps an AI coding assistant work like a careful engineering partner. It gives the assistant clear responsibilities, reusable workflows, and explicit boundaries for changes and verification.

The current approach uses the coding client's own tools. Codex handles the conversation, files, commands, and available native agents. Council skills guide how that work is planned, performed, reviewed, and handed back to you.

This repository contains the **native Council**, with **15 specialist roles and 9 workflow skills**. The earlier LangGraph engine and its viewer are retired. They are not part of this export. You do not need Python, a graph server, or a separate orchestration service.

This source snapshot is **3.0.0-alpha.4**. Windows and Codex are its current focus. It is intended for developer evaluation and customization.

## Start here

| Your goal | Read |
|---|---|
| Understand the project | Continue through this README |
| Install it on Windows | [Setup guide](docs/setup.md) |
| Find a role or skill | [Council catalog](docs/catalog.md) |
| Understand files and private state | [Repository structure](docs/structure.md) |
| Understand installation and execution | [Architecture flow](docs/architecture-flow.md) |
| Inspect source validation and updates | [Source contract](docs/source-contract.md) |
| Review the engineering checks | [Pre-submit SOP](docs/code-change-pre-submit-sop.md) |
| Understand test evidence and limits | [Behavior evaluation](docs/behavior-evaluation.md) |

## Why I built it

AI coding tools can do useful work. They can also skip context, widen a small change, confuse a proposal with a decision, or claim success after a narrow test.

The Council makes the working agreement explicit. Before changing behavior, understand the problem. Keep the change within its approved scope. Use the right engineering guidance. Check the actual result. Preserve the evidence and the remaining uncertainty.

The project started with named engineering roles. It grew into a shared set of skills, instructions, task context, and verification tools. A separate orchestration proof of concept added more machinery than I wanted to maintain. The active direction is simpler: let the native coding client do the execution, and give it useful engineering guidance.

The names are a convenient way to assign responsibility. They are not a claim that a room full of independent experts always runs behind every answer.

## What the Council does

- Routes work to relevant specialist guidance.
- Helps define scope, design choices, dependencies, and acceptance checks.
- Uses test-first development for executable behavior changes.
- Investigates failures before proposing a repair.
- Keeps independent service repositories separate.
- Reviews changed behavior as well as changed lines.
- Separates task history from current instructions and authorization.
- Preserves paused work and explicit task selection.
- Requires explicit approval before applying maintained knowledge proposals.
- Reports what was tested, what passed, and what remains unverified.

These are working instructions supported by scripts and tests. Some rules are enforced by code. Others depend on the model following the guidance. A source hash or an installed skill does not prove that a model followed every instruction.

## How it fits together

```text
Your request
    |
Native coding client
    |
Shared Council instructions + client adapter
    |
Relevant specialist skills + workflow skills
    |
Scoped work in your actual repository
    |
Tests, source review, evidence, and a clear handoff
```

The installer puts one shared source under `%USERPROFILE%\.council`. Native profile instructions point to it. Skill junctions under `%USERPROFILE%\.agents\skills` point to the same canonical packages.

The files in this Git repository are the portable source. Your installed Council is a separate copy. Editing your installed copy does not automatically update this repository.

The Council does not need to install its skills into each application repository. Your application source, tests, Git history, and repository instructions stay in their existing locations.

## Current client scope

**Codex is the focus of this snapshot.** The repository also retains the existing Gemini adapter and shared installer compatibility. Gemini-specific runtime qualification is separate work.

The current installer merges Council-owned instruction and hook sections for both client profiles. You do not need to install or sign in to Gemini to use Codex. Review the installer and adapter files if your organization needs a different client configuration.

Native clients, authentication, model access, and their billing remain your responsibility. This repository does not supply credentials or choose a paid model for you.

## Quick start on Windows

### Requirements

- Windows with PowerShell 5.1 or later.
- Node.js 20 or later.
- A supported native coding client, installed separately.
- A workspace directory that already exists.
- Permission to create profile files and directory junctions.

The recent script tests used Node.js 24 on Windows. Other environments need their own qualification. The installer in this export is native-only.

### Install

Clone or download this repository. Open PowerShell in the repository directory. Replace the workspace path with your own path:

```powershell
.\setup-council.ps1 -WorkspaceRoot 'D:\Development'
```

The installer verifies the source lock before it writes files. It then copies the portable source, renders machine paths, merges owned profile sections, and creates skill links.

It preserves unrelated client settings. Changed files receive backups under the installed `.council\backups` directory. Conflicting or malformed configuration stops installation instead of silently replacing it.

The compatibility switch `-NativeOnly` is still accepted. Native-only setup is already the default in this export.

### Validate the installation

```powershell
& "$env:USERPROFILE\.council\setup-council.ps1" `
    -WorkspaceRoot 'D:\Development' -ValidateOnly

& "$env:USERPROFILE\.council\scripts\validate-workspace.ps1" `
    -WorkspaceRoot 'D:\Development'
```

These checks validate source integrity and static placement. They do not grant hook trust or prove live model behavior.

### Open a fresh client session

Review and trust the installed hooks through the native client. Start a fresh session so the client can discover the current instructions and skills.

Ask the assistant to explain the selected task and relevant Council guidance. Then use a small, reversible task in a test repository. Check that it respects scope, preserves unrelated work, and reports real verification.

You do not need to say an initial “onboard” phrase. The profile pointer and startup flow are intended to provide that context. If native startup context is unavailable, the assistant has a documented fallback.

## Meet the specialists

Load the specialists that fit the task. A small review can use one role inline. A larger approved assignment can use native agents with clear ownership and evidence.

| Specialist | Main responsibility |
|---|---|
| [The Architect](skills/the-architect/SKILL.md) | System boundaries, design choices, and cross-service contracts |
| [The Builder](skills/the-builder/SKILL.md) | .NET Minimal API routes, HTTP contracts, and OpenAPI |
| [The Coder](skills/the-coder/SKILL.md) | C# domain and application logic |
| [The Curator](skills/the-curator/SKILL.md) | PostgreSQL, EF Core mappings, migrations, and indexes |
| [The Relay](skills/the-relay/SKILL.md) | Kafka, event contracts, consumers, and CloudEvents |
| [The Renderer](skills/the-renderer/SKILL.md) | React, TypeScript, CSS, and frontend behavior |
| [The Sentinel](skills/the-sentinel/SKILL.md) | Authentication, authorization, secrets, and PII |
| [The Prover](skills/the-prover/SKILL.md) | Tests, fixtures, failure diagnosis, and evidence limits |
| [The Purifier](skills/the-purifier/SKILL.md) | Clarity, dead code, formatting, and static warnings |
| [The Gatekeeper](skills/the-gatekeeper/SKILL.md) | Completion evidence and final source review |
| [The Codex](skills/the-codex/SKILL.md) | Technical documentation, decisions, and diagrams |
| [The Coordinator](skills/the-coordinator/SKILL.md) | Backlogs, acceptance criteria, and delivery dependencies |
| [The Pipelineer](skills/the-pipelineer/SKILL.md) | Build pipelines and Git delivery mechanics |
| [The Provisioner](skills/the-provisioner/SKILL.md) | Containers, Kubernetes, sizing, and runtime hosting |
| [The Watcher](skills/the-watcher/SKILL.md) | Logs, traces, metrics, and live-system diagnosis |

The bundled [Fulfillment profile](profiles/fulfillment/profile.json) is opinionated. Its defaults include .NET, PostgreSQL/EF Core, MSTest/NSubstitute, FAIR feature testing, and React/TypeScript. Treat it as an example to review and adapt. It is not a universal architecture standard or another organization's policy endorsement.

## The workflow skills

| Skill | When it helps |
|---|---|
| `using-superpowers` | Select relevant guidance for development work |
| `brainstorming` | Resolve design choices and requirements |
| `writing-plans` | Turn an approved approach into executable work |
| `the-council-orchestration` | Coordinate an explicitly requested Council assignment |
| `systematic-debugging` | Investigate a reproducible failure before fixing it |
| `test-driven-development` | Write and observe a failing test before changing behavior |
| `verification-before-completion` | Require fresh checks before a completion claim |
| `repo-documentation` | Refresh architecture explanations from inspected source |
| `handoff` | Save selected task state and useful checkpoints |

## Example requests

Ordinary work can stay small:

> Review this function for a correctness defect. Use the relevant Council guidance and report the evidence.

For a failure:

> Investigate this failing test before changing code. Find the cause, add a regression test, and make the smallest repair.

For coordinated work:

> Convene the Council: plan and implement this feature. Preserve the existing contracts and show the scope and verification plan first.

For a checkpoint:

> Save our current task state. Keep the unresolved questions, source identities, and next actions clear.

For architecture documentation:

> Compare this service's architecture documentation with the inspected source. Update only the affected explanations.

Naming a role does not automatically launch a separate agent. Discussing or quoting “Convene the Council” does not invoke the coordination workflow.

## Approval and execution

An explicit Council assignment uses two review points:

1. **Plan approval:** agree on scope, changes, responsibility, dependencies, and verification before implementation.
2. **Pre-submit review:** inspect the result, observed checks, remaining issues, and any real action that needs approval.

An already approved plan does not need repeated approval for the same work. Routine implementation decisions stay with the engineer. New material scope or consequential decisions can still require discussion.

These review points do not authorize pushing, publishing, merging, deploying, or messaging other people. Those actions need the authority supplied by your actual request and native policy.

## Memory and context

MemoryForge keeps task context separate from the distributable source. A new chat receives stable preferences and knowledge routing. It restores only an explicitly selected task or namespace.

An unbound chat offers relevant tasks and Start fresh. Selecting a paused task restores its context; it does not authorize resumption. Historical notes are data, not new instructions.

Hooks record bounded lifecycle facts. They do not invent semantic task summaries or claim that tests passed. The assistant authors meaningful checkpoints.

This export contains no personal task catalogue, preferences, knowledge notes, chat transcripts, credentials, or maintenance receipts. A new installation creates its own private memory directory. Missing knowledge is a coverage limit; the assistant can continue from inspected source.

## Optional knowledge maintenance

The source includes an opt-in workflow for maintained architecture and knowledge. It is not enabled by installing the repository alone.

Configured stages can observe integrated `main`/`master` revisions, review documentation, screen knowledge impact, prepare proposals, and queue parent review. Knowledge application requires explicit approval of the reviewed version.

Codex startup only announces available work. The actual agent command must pass write checks before claiming a day. Existing failed or interrupted runs remain closed. A later chat does not silently replay them.

The current maintenance implementation uses a registered Order Management workspace layout. Review its configuration contract before adopting it elsewhere. There is no scheduler, merge watcher, or automatic learning service in this export.

## Permissions and safety boundaries

The installer merges three Codex defaults: `on-request`, `auto_review`, and `workspace-write`. It adds the installed Council root to writable roots. Existing networking choices and unrelated roots are preserved.

Native policy, managed restrictions, current session settings, and operating-system permissions still apply. Council Markdown cannot grant access. The Council is not an operating-system sandbox.

The source also preserves clear boundaries between application repositories, shared definitions, workflow artifacts, and private state. Tests and scripts check selected cases. They do not establish protection against every hostile filesystem race or every external writer.

## What is tested

The repository includes Node fixture tests for source locks, configuration merging, installation, startup selection, worker context, task state, maintenance, proposals, and propagation.

Recent repair verification used a full 225-test snapshot and later targeted boundary checks. These runs overlap. They are not a single combined test count. The repaired code also received source review and changed-line coverage checks.

The native CLI trials did not establish a full runtime pass. The final pair recovered the selected synthetic state and task IDs, but failed bounded pause checks. Raw answers were discarded, so those flags cannot prove actual wrong advice or a restart. That qualification remains visible rather than being converted into a success claim.

Run source validation from the repository:

```powershell
node .\scripts\council-source.mjs check
```

Run the selected native/shared script suites:

```powershell
$tests = Get-ChildItem .\scripts\tests\*.test.mjs |
    Where-Object { $_.Name -notlike 'gemini-*' -and
        $_.Name -ne 'council-codex.test.mjs' }
node --test --test-concurrency=1 $tests.FullName
```

The wrapper suite already runs the direct installer fixture suite. Excluding that direct file avoids counting it twice. Keep full logs and distinguish an assertion failure from a host permission failure.

Native behavior trials are optional and can use paid model access. Read the [behavior guide](docs/behavior-evaluation.md) before running them. Do not repeat failed trials merely to obtain a pass.

## What is intentionally absent

- The retired LangGraph engine, runtime provisioning, and viewer.
- Personal memory, company knowledge collections, local plans, and chat history.
- Model credentials, API keys, native client databases, and session approval rules.
- Python environments, package caches, generated builds, and test work folders.
- Claims that the Council always follows its instructions or saves a measured amount of money.

The native visual companion inside the brainstorming skill is a separate optional mockup helper. It is not the retired engine viewer.

## Customize and contribute

Start with the profile and role closest to your work. Keep one authoritative rule for each responsibility. Prefer a small source change with a useful test over another orchestration layer.

For executable changes, add a failing regression first. Inspect the changed method, affected callers, and tests. Preserve unrelated work. Use clear evidence when reporting completion.

After an intentional reviewed source edit, run the audit before refreshing the lock:

```powershell
node .\scripts\council-source.mjs audit
node .\scripts\council-source.mjs lock
node .\scripts\council-source.mjs check
```

The lock records the approved bytes. Refreshing it is not a substitute for review.

Keep private experiments out of commits. Use the ignored `work/` directory for scratch data. If you add a role or workflow, update the manifest, catalog, tests, and relevant documentation together.

The aim is practical engineering help: clear responsibility, bounded changes, useful verification, and an honest account of what happened.
