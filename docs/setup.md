# Install The Council on Windows

Requirements: Node.js 20+ and an existing workspace. Native client setup supports Windows PowerShell 5.1+; the optional standalone engine requires PowerShell 7+, Python 3.11+, and package-index access for initial provisioning. Install Codex, Gemini CLI, and Claude Code separately if needed. Close active Council engine processes before engine installation or updates.

Extract the entire .council folder, open PowerShell 7 in it, and run:

```powershell
.\setup-council.ps1 -WorkspaceRoot 'D:\Development'
```

Use -PythonPath or -NodePath for executables outside PATH. The installer places shared definitions in your profile's .council, creates user skill junctions for all three clients, merges managed instruction/hook sections and Codex defaults while preserving unrelated settings, and provisions Python under .council/runtime. Changed native settings have backups under .council/backups. No API keys, private memory, model client applications, Docker, or Rancher Desktop are installed.

For native Codex, Gemini, and Claude setup without the standalone engine, run from the extracted folder:

```powershell
.\setup-council.ps1 -WorkspaceRoot 'D:\Development' -NativeOnly
& "$env:USERPROFILE\.council\setup-council.ps1" -WorkspaceRoot 'D:\Development' -NativeOnly -ValidateOnly
```

NativeOnly skips Python checks, downloads, and runtime provisioning. It installs the shared source, skill links, native defaults, and hooks. Codex's writable roots gain only the recipient Council root; existing roots and networking settings remain. Runtime overrides and managed restrictions still apply.

The installer runs the version-scoped Gemini compatibility repair when Gemini CLI 0.64.0 is present. Unknown versions are left untouched. Use -SkipGeminiOptimization to skip this optional repair. It validates recognized JavaScript, preserves genuine flag detection, and uses dedicated hashed backups; -Rollback on scripts/optimize-gemini-cli.ps1 restores only files unchanged since that repair. ValidateOnly on that script checks without writing. Generic preexisting .bak files are not treated as trusted rollback records.

After installation:

```powershell
& "$env:USERPROFILE\.council\setup-council.ps1" -WorkspaceRoot 'D:\Development' -ValidateOnly
& "$env:USERPROFILE\.council\council.ps1" --doctor
```

Repeat installation is supported. Unchanged healthy runtimes are reused without downloads; changed engine files reinstall the wheel even when its version is unchanged. ValidateOnly audits source hashes, native placement, dependencies, and the offline engine. It does not invoke providers or grant native hook trust. Review/trust hooks in each client and verify fresh native startup separately. Conflicting skill or policy directories stop deployment for reconciliation.

Read council/README.md for provider credentials, model overrides, approval gates, workspace selection, and resume behavior. The launcher works from any directory. Engine file tools are workspace-bound; external commands retain your OS permissions. Native Codex permissions and standalone engine approvals are separate controls.

The developer artifact includes regression tests and the active engine source. It excludes private memory, runtime environments, archives, project overrides, and generated build artifacts. It does not import private memory or clean service repositories. The working Council may retain historical assets. Keep these distribution boundaries in manifest.json when updating the artifact; installation behavior is shared code rather than separate installer implementations.
