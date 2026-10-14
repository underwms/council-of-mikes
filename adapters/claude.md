# claude adapter

Canonical Council: __COUNCIL_ROOT__.

Claude Code loads profile .claude/CLAUDE.md and its @ import of the shared instructions. Personal skills use profile .claude/skills junctions to the canonical packages. Use the Skill and available native delegation tools according to the shared workflow. Hooks register in profile .claude/settings.json. SessionStart and Stop use the common memory handler; timeout values are seconds. Stop identities use the documented prompt_id when provided; without a stable identity, no milestone is fabricated. Local profile integration does not make skills available in remote/cloud sessions.

## Shared source configuration

Read manifest.json and this adapter's JSON descriptor. Source policy and exclusions are user-scoped, across development workspaces. Use central exclusions/global.ignore for explicit discovery. Read docs/source-contract.md for native configuration fragments, their effective limitations, and the source audit commands. The source reconciliation does not overwrite live user-profile settings.

Existing hook configuration is preserved. Optional explicit --memory-scope workspace-session --session <simple-name> uses a workspace/session namespace below central memory, shared by all model actors. Unscoped saved handoffs and currently configured hooks keep their existing storage default.
