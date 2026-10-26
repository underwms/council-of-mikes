# The Council

Shared user-level skills, permissions, instructions, and adapters for Codex and Gemini CLI. The standalone orchestration engine uses real LangGraph, durable SQLite checkpoints, and autonomous Council plan review. New runs use `gpt-6.1-sol` through Codex CLI with the existing ChatGPT login for every role: planning, investigation, independent plan review, and coding. Multi-model routing is deferred; historical saved provider settings remain readable. Review and revision share bounded inspection evidence and specialist guidance, with stable findings and progress-aware limits. LangGraph owns sequencing and independent validation. Routine plan/final approvals are automatic; blockers distinguish user decisions, stalled review, exhausted budget and operational failure. Explicit manual gates and optional API reasoning backends remain available.

Start with [setup instructions](docs/setup.md). Run setup-council.ps1 once to deploy model assets and provision the private Python runtime. See [engine usage](council/README.md) for credentials and run/resume commands. Offline verification does not prove provider access or native hook trust.

Definitions remain central under .council; service repositories receive no Council skill installations. Private memory, backups, runtime environments, and historical archives are excluded from the developer ZIP. Source hashes and native placement are separate verification layers; see [source contract](docs/source-contract.md) and the [pre-submit SOP](docs/code-change-pre-submit-sop.md).

The historical engine under legacy/ is inactive. The engine under council/ is the maintained implementation.
