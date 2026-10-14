# Central Council Source Contract

The installed .council root is the only active source. manifest.json schema 1 names a version, unified skill inventory, specialist/workflow groups, selected profile, adapter descriptors, source roots, execution scope, memory modes, and bundled engine status. Existing user-profile junctions load these exact packages.

Run node scripts/council-source.mjs audit for structural/content checks. Run check to include the explicit source-lock.json hashes. After an intentional reviewed shared edit, run lock to refresh the baseline; it rejects structurally invalid source. A source lock detects unreviewed source drift, not native runtime trust. Private memory and archives remain outside the selected source roots.

Global execution and indexing assets live at central user scope. The Codex fragment owns three root defaults: approval_policy=on-request, approvals_reviewer=auto_review, and sandbox_mode=workspace-write. The installer activates these defaults in the user's native config, preserving unrelated text and existing network, writable-root, model, MCP, plugin, and trust settings. Source reconciliation and audits alone do not activate native settings. Gemini native policy keeps its existing junction, and Gemini customIgnoreFilePaths refers to exclusions/global.ignore. Codex and Claude use exclusion guidance for explicit discovery; native automatic indexing parity is not claimed. Native activation obeys active platform/managed restrictions and does not rewrite existing session overrides.

The installer carries profiles, exclusions, descriptors, and audit tooling while retaining managed block/hook merging, backups, fingerprints, and native links. Codex defaults and the descriptor's council-root writable-access binding are merged before installation writes; changed native config participates in the existing backup mechanism. The bounded merger handles three owned root scalars and the native sandbox writable-root string array, preserving unrelated settings and existing roots. Duplicate/scoped/non-scalar owned keys or unsupported dotted/inline sandbox tables reject before writes. It is not a full TOML validator. Legacy payloads without a Codex policy fragment do not alter native config. Placement validation checks these native defaults independently of source hashes.

Shared installer code respects distribution.project_cleanup=false and distribution.import_private_memory=false. Release integrity is checked before writes for versioned packages. JSON is parsed before rendering path strings. Installation regenerates hashes for the recipient's rendered source, rather than copying portable-package hashes as if they described installed bytes. Source, static placement, actual hook execution, and native startup remain distinct checks.

Shared clarification/authorization guidance lives in instructions/shared.md; Codex-native question tools and file-link syntax live in adapters/codex.md. Profile instruction files contain thin pointers. Session-specific command approvals, managed policy, credentials, plugins, and native client databases are not part of the developer artifact. NativeOnly setup does not require the optional Python engine.

Workspace/session memory is opt-in. --memory-scope workspace-session --session <simple-name> selects memory/workspaces/<workspace-hash>/<session>. All actors share that location. Default hooks and existing saved handoffs continue to use memory/ until explicitly migrated. Existing locks, duplicate-event suppression, bounded recovery and atomic updates remain in force.

The active standalone engine is under council/. The setup script provisions a private runtime and an installed launcher. It uses real LangGraph/SQLite, exact provider role configuration, bounded file tools, actual test commands, and approval interrupts. Subprocesses retain user OS permissions. The legacy engine is an inactive archive. Source audits alone do not prove live provider access or successful execution. See council/README.md.

Native config references checked during the source migration:

- [Codex configuration](https://developers.openai.com/codex/config-reference/)
- [Codex config scope](https://developers.openai.com/codex/config-basic/)
- [Gemini user policies](https://geminicli.com/docs/reference/policy-engine/)
- [Gemini exclusion configuration](https://geminicli.com/docs/reference/configuration/)
