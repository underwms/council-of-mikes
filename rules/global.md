# Global Council Host Invariants

Host facts and capabilities come from the running environment. Workspace-specific technology doctrine belongs in profiles, not these global rules.

- Load shared instructions and the active native adapter explicitly. All model discovery aliases reference the same canonical skill packages.
- User-scope execution policy authorizes routine development without repeated command prompts. Respect platform/administrator restrictions and existing task authorization. Shared Markdown does not itself alter native permissions.
- On Windows, prefer PowerShell for shell operations. Use native filesystem paths in PowerShell commands, while using the syntax required by JSON, Markdown links, URLs, and specific tools.
- Searching: use ripgrep (`rg`) when available; fall back to PowerShell `Select-String` and `Get-ChildItem` when `rg` is not installed.
- Shell commands: avoid unnecessarily complex multi-statement shell commands and unsafe string interpolation in automated tool commands. Keep agent tool invocations focused and inspectable.
- Directory deletion: verify the resolved target path stays within the named target or workspace; use PowerShell `Remove-Item -LiteralPath` for Windows filesystem operations. Add recursion only when required, and never follow a junction to delete its target.
- Specify explicit solution/project targets (e.g. dotnet build <name>.slnx) when multiple build or test targets exist.
- Do not alter another workspace, service repository, model's unrelated settings, or another session's memory unless included in the user's task.
- Private Council state belongs under the central memory root. Explicit workspace/session namespaces are available; do not put handoffs in source repositories.
- Native hooks record generic events and confirmed structured outcomes. They do not infer test success or semantic handoffs from assistant prose.
- Native trust/startup, source integrity, installation placement, and workspace health are different checks. Record the evidence for each.
