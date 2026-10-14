# The Council

Shared user-level skills, permissions, instructions, and adapters for Codex, Gemini CLI, and Claude Code. The active standalone orchestration engine uses real LangGraph with heterogeneous provider roles, durable SQLite checkpoints, and explicit approval gates.

Start with [setup instructions](docs/setup.md). Run setup-council.ps1 once to deploy model assets and provision the private Python runtime. See [engine usage](council/README.md) for credentials and run/resume commands. Offline verification does not prove provider access or native hook trust.

Definitions remain central under .council; service repositories receive no Council skill installations. Private memory, backups, runtime environments, and historical archives are excluded from the developer ZIP. Source hashes and native placement are separate verification layers; see [source contract](docs/source-contract.md) and the [pre-submit SOP](docs/code-change-pre-submit-sop.md).

The historical engine under legacy/ is inactive. The engine under council/ is the maintained implementation.
