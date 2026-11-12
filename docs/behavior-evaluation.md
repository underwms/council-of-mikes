# Council skill and context behavior checks

Use these checks after changing skill routing, startup, memory selection, or coordination. Keep installation checks and observed model behavior as separate results.

## Routine verification

```powershell
node scripts/council-source.mjs audit
node --test scripts/tests/council-context.test.mjs scripts/tests/council-eval.test.mjs scripts/tests/council-source.test.mjs
node scripts/council-codex.mjs validate
& scripts/validate-workspace.ps1
```

The source audit checks all governed text for strict UTF-8 and common corrupted-character signatures. It rejects references to the retired feature-testing framework in active instructions, profiles, adapters and skill guidance. It permits valid Unicode and escaped negative-test examples. The lock command refuses an invalid source baseline. No heuristic can detect every semantically incorrect character; inspect saved text and tool rendering too.

## Fresh native-client samples

```powershell
node scripts/council-eval.mjs --client all --case all --timeout-ms 180000
node scripts/council-eval.mjs --client gemini --case startup --report work/gemini-startup.json
```

The runner starts fresh native Codex/Gemini CLI sessions with their configured default models and authentication. Codex uses its read-only sandbox, never-approve mode and ephemeral session option. Gemini uses its native plan mode; it does not provide an OS sandbox guarantee. Native trust, permissions and policies remain in force. The runner never invokes the custom Council engine, bypasses hook trust, installs clients, changes credentials, or alters service repositories.

Each case gets a new scratch workspace and selected private MemoryForge session containing synthetic current and paused tasks. Profile startup instructions must recover that namespace without an onboard prompt. Historical notes are deliberately older than the current summary. The cases cover automatic startup, stale history, FAIR routing, convening, quoted non-invocation and a small inline review. The read-only fixture constraints are deliberate safety controls: absence of engine execution in these trials is evidence for these constrained requests, not proof that the same result holds under every permission configuration.

Scoring uses native JSONL events, observed memory/skill reads, exact synthetic tracking-ID recovery, final-answer outcomes, attempted mutations/spawns and engine commands. A claim such as "Council loaded" alone cannot pass startup. Successful CLI exit alone cannot pass any case. Incomplete or unavailable native turns are blocked, observed violations are failed, and only satisfied sampled criteria are passed. These are behavioral smoke tests, not an exhaustive semantic judge. Inspect failures before changing guidance; do not weaken a criterion to manufacture a pass.

Positive skill evidence requires successful native activation or delivery of the complete canonical skill body, including when a later command in the same batch fails. A successful path mention, partial read or failed attempt alone does not count. Convening requires the coordination and brainstorming skills plus a concrete collaborative question; a printed call-sign alone is not evidence of the workflow, and equivalent behavior does not fail merely because a decorative label is absent. Reports fingerprint the evaluator revision so preliminary and reviewed runs remain distinguishable.

The report retains sanitized observations and reason codes. Raw messages, shell commands, tool arguments and payloads are discarded. Scratch workspaces and synthetic memory remain under central work/ and memory/workspaces/ for review; never reuse them as real task state. Use the same cases in fresh sessions after a model/client upgrade. Actual interactive compaction, client-specific UI discovery and persisted hook trust still require native checks; a fresh-process recovery sample does not certify those flows.

## Windows host qualification and native injection

Run Codex qualification from a normal supported client host. Launching a second native Windows sandbox inside an outer agent sandbox can fail before a file-read command starts. The observed failure is `CreateDesktopW failed for shared private desktop: 5`. A controlled native command/exec probe on 2026-11-12 failed inside the outer sandbox and passed outside it with the same Codex read-only sandbox policy. Treat an unmet loading check accompanied by this failure as environment-blocked; it does not establish a skill-selection defect. Unsafe actions still fail the case, and successful later delivery can satisfy the check after a recovered launch failure.

For agent-driven qualification, use the normal approved escalation mechanism to run the test process on the host while keeping Codex's own read-only policy and never-approve mode. Do not disable native sandboxing, bypass hook trust or modify managed security to make a test pass. Record host conditions and native launch failures separately from model behavior.

Compare ordinary trigger phrases with explicit native skill selection and, for integrations that own turn/start, a structured skill input item. The [official app-server skill interface](https://learn.chatgpt.com/docs/app-server#skills) accepts an absolute skill path and injects its instructions. Record accepted structured inputs separately from tool-mediated body reads; a valid native injection need not produce a file-read tool event. Include a text-only app-server control so a change of transport is not mistaken for an injection effect. Repeat identical cases with the same configured model and permissions, retaining every result rather than rerunning until one passes.

MCP text and structured-content wrappers may carry complete skill bodies. The evaluator decodes supported output wrappers for comparison against canonical skill content without persisting their raw payloads. A successful read attempt, an entry in skills/list or a printed role label still does not prove the full skill was delivered.

## Current memory maintenance

Maintain current_state.md in the selected namespace at meaningful milestones and checkpoints: date, current objective/status, verified facts with evidence pointers, open items and separately paused work. Keep it within 5,000 UTF-8 bytes. preferences.md holds stable user-confirmed preferences. The startup handler reads these and a bounded recent semantic backlog; it retrieves the historical handoff only when no current summary exists. Existing historical files remain preserved. Follow the handoff skill for semantic updates; hooks must not invent the current objective from arbitrary assistant prose.

## Skill and role maintenance

Keep each skill description focused on its trigger and ownership boundary. Place detailed doctrine in the selected profile and task references, and read it only when relevant. Apply specialist skills inline by default. Use a separate native agent only for authorized bounded work with a concrete benefit from independent context, parallelism, or review; assign ownership and integrate the evidence. A role call-sign alone does not indicate that a separate agent ran.
