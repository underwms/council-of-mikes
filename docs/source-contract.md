# Native source contract

The portable repository and installed `%USERPROFILE%\.council` are separate copies. The installed root is the source used by native profile pointers and skill junctions. Do not edit a service repository to install Council definitions.

`manifest.json` lists skills, profiles, adapters, source roots, and files. `source-lock.json` fingerprints the governed bytes. Run `audit` for structure, local links, metadata, UTF-8, and selected content checks. Run `check` to include the release hashes. `lock` refuses structurally invalid source.

The native installer validates the payload before writing. It renders `__WORKSPACE_ROOT__` and `__COUNCIL_ROOT__` for the recipient. It regenerates the installed source lock after rendering. Portable hashes are not presented as hashes of installed bytes.

Distribution flags disable private-memory import and service-repository cleanup. Private task state, knowledge, credentials, backups, native databases, and caches are excluded. The engine and viewer are retired and absent.

Owned configuration merges preserve unrelated model, networking, root, plugin, and trust settings. Conflicting links and unsupported configuration forms stop installation. The current shared installer still carries both client profile routes. This export does not certify Gemini runtime behavior.

The Codex defaults are `approval_policy=on-request`, `approvals_reviewer=auto_review`, and `sandbox_mode=workspace-write`. Only the installed Council root is added by the adapter's writable-root binding. Native and managed permissions still apply.

Source validation, installed placement, hook trust, actual hook execution, and model behavior are separate evidence. The [behavior guide](behavior-evaluation.md) records those limits. A source audit does not establish universal instruction following.

The common CLI supports stable user startup, selected tasks, and explicit workspace/session memory. Worker startup reads stable context only. It does not choose a task or run daily maintenance. Generic lifecycle hooks do not author semantic checkpoints.

Maintained knowledge proposals require an explicit version-bound user decision. A model-recorded approval assertion is not independent human authentication. Target locks and source fingerprints protect supported writers; they are not an operating-system sandbox.
