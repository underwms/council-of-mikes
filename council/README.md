# Council orchestration engine

The standalone engine uses native LangGraph, durable SQLite checkpoints, and explicit plan/final approval gates. File tools and command working directories are bound to the selected workspace. Subprocesses retain the launching user's operating-system permissions; this engine is not an operating-system sandbox. Missing credentials, missing validation, and failed tasks return errors.

Install the complete Council distribution with its `setup-council.ps1` script. It requires Windows, PowerShell 7+, Node.js 20+, Python 3.11+, and access to the Python package index. The script creates a private Python environment under the installed Council's `runtime/` and installs this package. The wheel's `council` entry point and `python -m council` use the same CLI. Runtime files and credentials are not part of the share source.

Run the installed launcher from any directory:

```powershell
& "$env:USERPROFILE\.council\council.ps1" --doctor
& "$env:USERPROFILE\.council\council.ps1" --workspace 'D:\Development' 'Implement the approved feature'
```

Use `--dry-run` to generate a plan without executing tasks, `--no-input` to leave approval gates paused for a later process, and `--resume <run-id>` to continue the same workspace-bound run. `--auto-approve` explicitly bypasses the engine's approval prompts. It is separate from the native Codex permission mode.

Provider credentials and model identifiers are configured locally through the engine's documented environment variables. The doctor verifies local imports, routing, checkpoint access, and graph construction without making provider requests or modifying project files. Successful offline validation does not prove model credentials or account availability.

| Role | Model setting | Provider setting | Default |
|---|---|---|---|
| Orchestrator | `COUNCIL_ORCHESTRATOR_MODEL` | `COUNCIL_ORCHESTRATOR_PROVIDER` | `gpt-6.1-sol` |
| Investigator | `COUNCIL_INVESTIGATOR_MODEL` | `COUNCIL_INVESTIGATOR_PROVIDER` | `gemini-3.8-flash` |
| Escalation | `COUNCIL_ESCALATION_MODEL` | `COUNCIL_ESCALATION_PROVIDER` | `claude-4.5-sonnet` |

Provider values are `gpt`, `gemini`, and `claude`, using `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `ANTHROPIC_API_KEY` respectively. Custom model names require an explicit provider when their prefix does not identify one. These inherited model identifiers are local defaults, not a claim that an account can access them. Enable escalation explicitly with `COUNCIL_ENABLE_ESCALATION=true`. Credentials are read from the environment; the engine does not load `.env` files automatically.

Native approval pauses use the same run ID when resumed. Nodes may run again after a crash; external commands should be safe to repeat. Avoid running two installers or two processes for the same run concurrently. Close engine processes before updating the runtime. Installation needs package-index access; regular reuse and `-ValidateOnly` make no package downloads.

The existing orchestrator and investigator roles remain separate; escalation is optional. Plans declare task working directories and test commands. Execution reports actual test/validator results and does not automatically certify every phase of the corporate pre-submit SOP. Review that SOP before merging generated changes.

Private engine state belongs beneath the canonical Council's `memory/`. Shared skill definitions remain in its `skills/` directory. The historical engine under `legacy/` is an inactive archive.
