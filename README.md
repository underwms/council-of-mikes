# Council of Mikes

> A team of 15 AI expert personas for .NET/C# development. Each member has deep domain expertise and clear boundaries — they collaborate, defer to specialists, and never freelance outside their lane.

## What Is This?

The Council of Mikes is a **multi-persona AI skill system** designed for AI-assisted .NET development. Instead of one generalist AI that's mediocre at everything, you get 15 specialized experts that route questions to the right domain and produce answers with depth.

**Think of it as:** a virtual senior engineering team living inside your AI assistant.

## Members (15)

| Member | Role | Best For |
|--------|------|----------|
| **Solutions Architect** | Architecture & domain | System design, trade-offs, architecture decisions |
| **Development Lead** | Senior C# developer | Idiomatic C#, SOLID, .NET patterns |
| **Documentation Lead** | Documentation overseer | XML docs, Mermaid diagrams, ADRs, SOPs |
| **Quality Analyst** | Code quality sweep | SonarQube tripwires, complexity, modernization |
| **Frontend Lead** | UI/UX engineer | React, Blazor, SignalR, CSS, accessibility |
| **Security Lead** | InfoSec & compliance | PCI/PII, auth flows, redaction, Key Vault |
| **Backend Lead** | Backend engineer | REST, GraphQL, PowerShell, microservices, K8s |
| **Workflow Lead** | Temporal engineer | Workflow determinism, versioning, Nexus, testing |
| **Observability Lead** | Observability architect | App Insights, OpenTelemetry, alerting, traces |
| **Data Lead** | Data engineer | Cosmos DB, Redis, SQL Server, EF Core |
| **Messaging Lead** | Messaging architect | Kafka, Service Bus, Event Grid, Event Hubs |
| **Test Lead** | Test & quality engineer | xUnit, Moq, Testcontainers, load testing, ARTS |
| **DevOps Lead** | DevOps & infrastructure | CI/CD, Terraform, Git workflows, pipelines |
| **Platform Lead** | Azure platform engineer | App Services, Functions, networking, ARM/Bicep |
| **Gatekeeper** | Pre-submit quality gate | 11-phase Pre-Submit SOP, Copilot PR-review simulation |

## How It Works

1. **Install** — Copy `council/` and `skills/` into your `.claude/skills/` directory
2. **Invoke by name** — "Solutions Architect: should I use CQRS here?"
3. **Or let them self-select** — "council meeting: order M-123 failed" routes to the right members
4. **Quality sweep** — The Quality Analyst runs automatically after any member writes code

## Operating Principles

1. **Don't reinvent established patterns** — match existing test shapes, don't invent new ones
2. **Quality Analyst runs after every member** — catches SonarQube tripwires before code ships
3. **Regression coverage is part of the deliverable** — not a PR-time afterthought
4. **Members defer to specialists** — cross-domain questions route to the expert

## Pre-Submit Quality Gate

Before any code change is declared "done" — push, PR, or "done" report — the **Gatekeeper** runs the **11-phase Pre-Submit Gate** defined in [`procedures/code-change-pre-submit-sop.md`](procedures/code-change-pre-submit-sop.md).

Phases (owners in parentheses):

1. Brainstorm (Architect / Coder)
2. Implement (Coder / Builder / Timekeeper / Renderer)
3. Purify (Purifier)
4. Static analysis — zero new lints (Purifier)
5. Unit tests (Prover)
6. Coverage on changed lines (Prover)
7. Regression on full affected suite (Prover)
8. **Diff-vs-behavior** — read every method end-to-end, compare to `git show HEAD:<file>` (**Gatekeeper**)
9. Integration & build (Prover / Builder)
10. **Copilot PR-review simulation** (**Gatekeeper**)
11. Documentation update (Codex)

**Slash command:** `/pre-submit` — see [`prompts/pre-submit.prompt.md`](prompts/pre-submit.prompt.md).

**Routing snippet:** drop [`prompts/council-routing.snippet.md`](prompts/council-routing.snippet.md) into your `AGENTS.md` or `.github/copilot-instructions.md` to enable `@TheCouncil use pre-submit skill` phrasing.

## Companion Skills

The `skills/` directory includes standalone skills that enhance specific Council members:

| Skill | Enhances | Purpose |
|-------|----------|---------|
| `temporal-dotnet` | Workflow Lead | Temporal .NET SDK patterns, testing, Nexus |
| `temporal-versioning` | Workflow Lead | Safe deployment of workflow changes |
| `protobuf-dotnet` | Backend Lead | Protocol Buffers in .NET, buf CLI |
| `arts-regression-testing` | Test Lead | Full ARTS reference architecture — assembly fixtures, golden files, CI/CD gating |
| `aspire-local-testing` | Test Lead | E2E testing with .NET Aspire |
| `aspire-apphost-setup` | Development Lead | Setting up Aspire orchestration |
| `qa-expert` | Test Lead | Project-level QA strategy |
| `composition-patterns` | Frontend Lead | React composition patterns (MIT/Vercel) |
| `web-design-guidelines` | Frontend Lead | Web Interface Guidelines review (MIT/Vercel) |

## Works Best With: Superpowers

The Council is designed to work alongside [obra/superpowers](https://github.com/obra/superpowers) — a universal skills library that provides process discipline:

- `brainstorming` — refine ideas before coding
- `test-driven-development` — RED-GREEN-REFACTOR cycle
- `systematic-debugging` — 4-phase investigation
- `verification-before-completion` — run checks before claiming done
- `writing-plans` / `executing-plans` — structured implementation

**The Council provides WHAT expertise. Superpowers provides HOW to work.**

## Installation

```bash
# Clone into your workspace skills directory
git clone https://github.com/TheCouncil/council-of-mikes.git .claude/skills/council-of-mikes

# Or copy specific members/skills into your existing structure
cp -r council-of-mikes/council/* .claude/skills/
cp -r council-of-mikes/skills/* .claude/skills/
```

### Customization

The Council is a **template**. Each member's SKILL.md has placeholder sections for your domain:

- **Solutions Architect** → Add your system map, domain glossary, service boundaries
- **Observability Lead** → Add your `cloud_RoleName` map, alert queries
- **Data Lead** → Add your database schemas, partition key strategies
- **Messaging Lead** → Add your topic/consumer map, dead-letter patterns

## Directory Structure

```
council-of-mikes/
├── README.md
├── AGENTS.md                       ← Drop-in agent guide (routing + hard rules)
├── LICENSE
├── .github/
│   └── copilot-instructions.md     ← Copilot auto-loaded instructions
├── council/
│   ├── council.md              ← Cheat sheet, routing, operating principles
│   ├── the-architect/SKILL.md
│   ├── the-coder/SKILL.md
│   ├── the-codex/SKILL.md
│   ├── the-purifier/SKILL.md
│   ├── the-renderer/SKILL.md
│   ├── the-sentinel/SKILL.md
│   ├── the-builder/SKILL.md
│   ├── the-timekeeper/SKILL.md
│   ├── the-watcher/SKILL.md
│   ├── the-curator/SKILL.md
│   ├── the-relay/SKILL.md
│   ├── the-prover/SKILL.md
│   ├── the-pipelineer/SKILL.md
│   ├── the-provisioner/SKILL.md
│   └── the-gatekeeper/SKILL.md
├── procedures/
│   └── code-change-pre-submit-sop.md   ← 11-phase pre-submit gate
├── prompts/
│   ├── pre-submit.prompt.md            ← /pre-submit slash command
│   └── council-routing.snippet.md      ← @TheCouncil routing for AGENTS.md
└── skills/
    ├── temporal-dotnet/SKILL.md
    ├── temporal-versioning/SKILL.md
    ├── protobuf-dotnet/SKILL.md
    ├── aspire-local-testing/SKILL.md
    ├── aspire-apphost-setup/SKILL.md
    ├── qa-expert/SKILL.md
    ├── composition-patterns/SKILL.md
    └── web-design-guidelines/SKILL.md
```

## License

MIT — see [LICENSE](./LICENSE)

## Credits

- **Council concept & domain expertise:** Mike (TheCouncil)
- **Composition Patterns & Web Design Guidelines:** [Vercel](https://github.com/vercel-labs) (MIT)
- **Works best with:** [obra/superpowers](https://github.com/obra/superpowers) (MIT)
- **Companion repo:** [MemoryForge](https://github.com/underwms/MemoryForge) — workspace orchestration, morning sync, repo onboarding, graph audit. MemoryForge handles *where context lives*; the Council handles *who does the work*.
