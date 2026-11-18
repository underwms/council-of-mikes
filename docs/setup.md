# Native Council setup

This export installs the native Council. The retired engine and viewer are not included. Node.js 20+, Windows PowerShell 5.1+, an existing workspace, and a separately installed client are required.

## Install

Run from the cloned repository:

```powershell
.\setup-council.ps1 -WorkspaceRoot 'D:\Development'
```

The installer verifies source hashes, renders recipient paths, copies source to `%USERPROFILE%\.council`, merges owned profile sections, and creates skill junctions. Changed native files have backups. Unrelated settings remain in place. `-HomeRoot` and `-NodePath` support explicit locations. `-NativeOnly` is a compatibility switch; native setup is already the default.

The shared installer writes both Codex and Gemini profile sections. The Gemini adapter is retained compatibility, with separate runtime qualification. Neither model client nor its authentication is installed here.

The export disables service-repository cleanup and private-memory import. An existing conflicting installation stops for reconciliation. Use a clean test profile first if you maintain a different Council installation.

## Validate

```powershell
& "$env:USERPROFILE\.council\setup-council.ps1" -WorkspaceRoot 'D:\Development' -ValidateOnly
& "$env:USERPROFILE\.council\scripts\validate-workspace.ps1" -WorkspaceRoot 'D:\Development'
```

Static validation does not grant hook trust. Review the hooks in the client and open a fresh session. Verify startup, selected task context, paused work, and a small reversible development task.

Keep workspace and profile directories separate. Managed settings and session permission overrides remain authoritative. Council writable access does not give a projectless chat automatic access to its registered maintenance workspace.

## Update

Review the release diff and source check. Close work that uses files you will replace. Run setup from the new source. Validate again and review changed native hook definitions when the client requires it. Reinstalling does not import another developer's memory.

Updates do not delete unrelated directories or private history. Files from an older engine installation can remain on disk. They are outside this export and setup does not invoke them.

See the [README](../README.md), [source contract](source-contract.md), and [behavior guide](behavior-evaluation.md) for scope and evidence limits.
