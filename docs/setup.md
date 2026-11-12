# Install The Council on Windows

Requirements: Node.js 20+ and an existing workspace. Native client setup supports Windows PowerShell 5.1+; the optional standalone engine requires PowerShell 7+, Python 3.11+, and package-index access for initial provisioning. Install Codex and Gemini CLI separately if needed. Close active Council engine processes before engine installation or updates.

Extract the entire .council folder, open PowerShell 7 in it, and run:

```powershell
.\setup-council.ps1 -WorkspaceRoot 'D:\Development'
```

Use -PythonPath or -NodePath for executables outside PATH. The installer places shared definitions in your profile's .council, creates user skill junctions for both clients, merges managed instruction/hook sections and Codex defaults while preserving unrelated settings, and provisions Python under .council/runtime. Changed native settings have backups under .council/backups. No API keys, private memory, model client applications, Docker, or Rancher Desktop are installed.

For native Codex and Gemini setup without the standalone engine, run from the extracted folder:

```powershell
.\setup-council.ps1 -WorkspaceRoot 'D:\Development' -NativeOnly
& "$env:USERPROFILE\.council\setup-council.ps1" -WorkspaceRoot 'D:\Development' -NativeOnly -ValidateOnly
```

NativeOnly skips Python checks, downloads, and runtime provisioning. It installs the shared source, skill links, native defaults, and hooks. Codex's writable roots gain only the recipient Council root; existing roots and networking settings remain. Runtime overrides and managed restrictions still apply.

The installer leaves the user's Gemini CLI installation untouched. The legacy `-SkipGeminiOptimization` argument remains accepted for older setup commands but has no effect. The standalone `scripts/optimize-gemini-cli.ps1` is a historical, version-specific repair tool and is not required by the Council transport; do not use it for routine setup.

Council startup is automatic in both Codex and Gemini CLI: the profile instruction pointer directs the model to load shared guidance and recover MemoryForge context before substantive work. No initial onboard command is required. If native SessionStart context is absent, including in projectless Council chats, the assistant reads it through the common onboard CLI or approved UTF-8 file reads. Startup does not convene the Council or resume saved work. Open a fresh client session after changing profile instructions; verify actual startup separately from static placement.

After installation:

```powershell
& "$env:USERPROFILE\.council\setup-council.ps1" -WorkspaceRoot 'D:\Development' -ValidateOnly
& "$env:USERPROFILE\.council\council.ps1" --doctor
```

Repeat installation is supported. Unchanged healthy runtimes are reused without downloads; changed engine files reinstall the wheel even when its version is unchanged. ValidateOnly audits source hashes, native placement, dependencies, and the offline engine. It does not invoke providers or grant native hook trust. Review/trust hooks in each client and verify fresh native startup separately. Conflicting skill or policy directories stop deployment for reconciliation.

New engine runs use `gpt-6.1-sol` through the installed Codex CLI with the existing ChatGPT login for every role. The standard run needs only Codex installed and signed in; Gemini and API keys are unnecessary. Multi-model routing is deferred, while historical saved provider settings remain readable. Council records CLI versions for diagnostics and checks required capabilities instead of pinning releases. Autonomous review is the default. New protocol-2 runs preserve bounded inspection evidence and stable findings, allow at most five revisions, and distinguish stalled review, budget exhaustion, user decisions and operational failures. Existing checkpoints retain their recorded policy. Explicit manual mode retains human gates. PowerShell can invoke the private Python executable directly with `-I -m council`; the launcher is optional. Read council/README.md for authentication, model overrides, review policies, workspace selection, and resume behavior. The launcher works from any directory. Engine file tools are workspace-bound; external commands retain your OS permissions. Native Codex permissions and standalone engine review are separate controls.

The developer artifact includes regression tests and the active engine source. It excludes private memory, runtime environments, archives, project overrides, and generated build artifacts. It does not import private memory or clean service repositories. The working Council may retain historical assets. Keep these distribution boundaries in manifest.json when updating the artifact; installation behavior is shared code rather than separate installer implementations.

