import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const fixtureParent = path.resolve(scriptRoot, '../temp/the-council/tests');

export async function runTests() {
  const { installCouncil, validateCouncil, mergeManagedBlock, buildHooks, cleanupCouncilProjects, mergeGeminiSettings } = await import('../council-codex-lib.mjs');
  const { handleHook, readContext, memoryRoot } = await import('../council-memoryforge.mjs');
  const results = [];
  const fixtures = [];
  async function test(name, body) {
    try { await body(); results.push({ name, status: 'pass' }); }
    catch (error) { results.push({ name, status: 'fail', error: error.message }); }
  }
  async function fixture() {
    await fs.mkdir(fixtureParent, { recursive: true });
    const base = await fs.mkdtemp(path.join(fixtureParent, 'fixture-'));
    fixtures.push(base);
    const options = { workspaceRoot: path.join(base, 'workspace'), payloadRoot: path.join(base, 'payload'), homeDir: path.join(base, 'home'), username: 'test-user', nodePath: path.join(base, 'node runtime/node.exe'), scriptRoot };
    options.councilRoot = path.join(options.homeDir, '.council');
    await fs.mkdir(path.dirname(options.nodePath), { recursive: true });
    await fs.writeFile(options.nodePath, 'Fixture runtime marker; never executed.');
    await fs.mkdir(path.join(options.workspaceRoot, 'service/.git'), { recursive: true });
    await fs.mkdir(path.join(options.payloadRoot, 'skills/example/references'), { recursive: true });
    await fs.mkdir(path.join(options.payloadRoot, 'rules'), { recursive: true });
    await fs.writeFile(path.join(options.payloadRoot, 'manifest.json'), JSON.stringify({ skills: ['example'] }));
    await fs.writeFile(path.join(options.payloadRoot, 'AGENTS.md'), 'Read __WORKSPACE_ROOT__/rules.');
    await fs.writeFile(path.join(options.payloadRoot, 'rules/workspace.md'), 'Rules for __WORKSPACE_ROOT__.');
    await fs.writeFile(path.join(options.payloadRoot, 'skills/example/SKILL.md'), '---\nname: example\ndescription: Fixture behavior\n---\nRead __WORKSPACE_ROOT__.');
    await fs.writeFile(path.join(options.payloadRoot, 'skills/example/references/helper.bin'), Buffer.from([0, 1, 2, 255]));
    return options;
  }
  const codexDefaults = 'approval_policy = "on-request"\napprovals_reviewer = "auto_review"\nsandbox_mode = "workspace-write"\n';
  await test('Install_DeploysEngineAndLauncher_WithoutGeneratedArtifacts', async () => {
    const o = await fixture();
    await fs.mkdir(path.join(o.payloadRoot, 'council/__pycache__'), { recursive: true });
    await fs.mkdir(path.join(o.payloadRoot, 'council/build'), { recursive: true });
    await fs.writeFile(path.join(o.payloadRoot, 'council/cli.py'), '# engine source');
    await fs.writeFile(path.join(o.payloadRoot, 'council/__pycache__/cli.pyc'), 'local compiled artifact');
    await fs.writeFile(path.join(o.payloadRoot, 'council/build/private.txt'), 'local build artifact');
    await fs.writeFile(path.join(o.payloadRoot, 'council.ps1'), '# engine launcher');
    await fs.writeFile(path.join(o.payloadRoot, 'setup-council.ps1'), '# deployment entry point');
    await fs.writeFile(path.join(o.payloadRoot, '.gitignore'), 'runtime/\n');

    await installCouncil(o);

    assert.equal(await fs.readFile(path.join(o.councilRoot, 'council/cli.py'), 'utf8'), '# engine source');
    assert.equal(await fs.readFile(path.join(o.councilRoot, 'council.ps1'), 'utf8'), '# engine launcher');
    assert.equal(await fs.readFile(path.join(o.councilRoot, '.gitignore'), 'utf8'), 'runtime/\n');
    await assert.rejects(fs.stat(path.join(o.councilRoot, 'council/__pycache__')), { code: 'ENOENT' });
    await assert.rejects(fs.stat(path.join(o.councilRoot, 'council/build')), { code: 'ENOENT' });
    assert.equal((await installCouncil(o)).changed.length, 0);
  });
  async function codexFixture() {
    const o = await fixture();
    await fs.writeFile(path.join(o.payloadRoot, 'manifest.json'), JSON.stringify({ skills: ['example'], adapters: { codex: 'adapters/codex.json' } }));
    await fs.mkdir(path.join(o.payloadRoot, 'adapters/codex'), { recursive: true });
    await fs.writeFile(path.join(o.payloadRoot, 'adapters/codex.json'), JSON.stringify({ id: 'codex', policy_fragment: 'codex/config.toml', policy_destination: '~/.codex/config.toml' }));
    await fs.writeFile(path.join(o.payloadRoot, 'adapters/codex/config.toml'), codexDefaults);
    return o;
  }
  await test('Install_MergesCodexDefaults_PreservingSettingsAndBackups', async () => {
    const o = await codexFixture();
    const configPath = path.join(o.homeDir, '.codex/config.toml');
    const original = '# User settings\r\nmodel = "chosen-model"\r\nexample = """\r\napproval_policy = "sample text"\r\n"""\r\napproval_policy = "never" # former default\r\n\'sandbox_mode\' = \'read-only\'\r\n[sandbox_workspace_write]\r\nnetwork_access = false\r\nwritable_roots = ["C:/shared"]\r\n[mcp_servers.example]\r\ncommand = "node"\r\n';
    await fs.mkdir(path.dirname(configPath), { recursive: true });
    await fs.writeFile(configPath, original);

    const installed = await installCouncil(o);
    const merged = await fs.readFile(configPath, 'utf8');

    assert.equal(merged, 'approvals_reviewer = "auto_review"\r\n' + original.replace('approval_policy = "never"', 'approval_policy = "on-request"').replace("'sandbox_mode' = 'read-only'", "'sandbox_mode' = \"workspace-write\""));
    assert(installed.changed.includes(configPath));
    const backupRows = (await fs.readFile(path.join(installed.backupRoot, 'files.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    assert.equal(await fs.readFile(backupRows.find(row => row.target === configPath).backup, 'utf8'), original);
    assert.equal((await installCouncil(o)).changed.length, 0);
  });
  await test('Install_CreatesCodexDefaults_WhenNativeConfigIsAbsent', async () => {
    const o = await codexFixture();

    await installCouncil(o);

    assert.equal(await fs.readFile(path.join(o.homeDir, '.codex/config.toml'), 'utf8'), codexDefaults);
    assert.equal((await installCouncil(o)).changed.length, 0);
  });
  await test('Install_RejectsDuplicateCodexKeys_BeforeWriting', async () => {
    const o = await codexFixture();
    const original = 'approval_policy = "never"\n"approval_policy" = "on-request"\n';
    await fs.mkdir(path.join(o.homeDir, '.codex'), { recursive: true });
    await fs.writeFile(path.join(o.homeDir, '.codex/config.toml'), original);

    await assert.rejects(() => installCouncil(o), /duplicate.*approval_policy/i);

    assert.equal(await fs.readFile(path.join(o.homeDir, '.codex/config.toml'), 'utf8'), original);
    await assert.rejects(fs.stat(o.councilRoot), { code: 'ENOENT' });
  });
  await test('Install_RejectsScopedCodexKeys_BeforeWriting', async () => {
    const o = await codexFixture();
    await fs.mkdir(path.join(o.homeDir, '.codex'), { recursive: true });
    await fs.writeFile(path.join(o.homeDir, '.codex/config.toml'), '[approval_policy.granular]\nsandbox_approval = true\n');

    await assert.rejects(() => installCouncil(o), /scoped.*approval_policy/i);

    await assert.rejects(fs.stat(o.councilRoot), { code: 'ENOENT' });
  });
  await test('Install_ReplacesEscapedCodexKey_WithoutAddingDuplicate', async () => {
    const o = await codexFixture();
    await fs.mkdir(path.join(o.homeDir, '.codex'), { recursive: true });
    await fs.writeFile(path.join(o.homeDir, '.codex/config.toml'), '"\\u0061pproval_policy" = "never"\n');

    await installCouncil(o);

    assert.equal(await fs.readFile(path.join(o.homeDir, '.codex/config.toml'), 'utf8'), 'approvals_reviewer = "auto_review"\nsandbox_mode = "workspace-write"\n"\\u0061pproval_policy" = "on-request"\n');
  });
  await test('Install_RejectsEscapedAdapterFragment_BeforeWriting', async () => {
    const o = await codexFixture();
    await fs.writeFile(path.join(o.payloadRoot, 'adapters/codex.json'), JSON.stringify({ policy_fragment: '../../outside.toml', policy_destination: '~/.codex/config.toml' }));

    await assert.rejects(() => installCouncil(o), /resource escapes/i);

    await assert.rejects(fs.stat(o.councilRoot), { code: 'ENOENT' });
  });
  await test('Install_RejectsUnsupportedConfigDestination_BeforeWriting', async () => {
    const o = await codexFixture();
    await fs.writeFile(path.join(o.payloadRoot, 'adapters/codex.json'), JSON.stringify({ policy_fragment: 'codex/config.toml', policy_destination: '~/outside.toml' }));

    await assert.rejects(() => installCouncil(o), /policy destination/i);

    await assert.rejects(fs.stat(o.councilRoot), { code: 'ENOENT' });
  });
  await test('Install_PreservesUnrelatedContent_AndIsIdempotent', async () => {
    const o = await fixture();
    await fs.writeFile(path.join(o.workspaceRoot, 'AGENTS.md'), 'Personal workspace instruction.\n');
    await fs.writeFile(path.join(o.workspaceRoot, 'service/AGENTS.md'), 'Service-specific instruction.\n');
    await fs.mkdir(path.join(o.homeDir, '.codex'), { recursive: true });
    const unrelated = { hooks: { Stop: [{ hooks: [{ type: 'command', command: 'existing-command' }] }] }, custom: { retain: true } };
    await fs.writeFile(path.join(o.homeDir, '.codex/hooks.json'), JSON.stringify(unrelated));
    const first = await installCouncil(o);
    assert(first.changed.length > 0);
    const report = await validateCouncil(o);
    assert.equal(report.placement.status, 'pass', JSON.stringify(report));
    assert.equal(report.lifecycle.status, 'configured');
    assert.equal(report.runtime.status, 'unverified');
    assert.equal(report.ready, false);
    assert((await fs.readFile(path.join(o.workspaceRoot, 'AGENTS.md'), 'utf8')).includes('Personal workspace instruction.'));
    await assert.rejects(fs.stat(path.join(o.workspaceRoot, 'service/AGENTS.md')), { code: 'ENOENT' });
    assert.equal(await fs.readFile(path.join(o.councilRoot, 'project-instructions/service.md'), 'utf8'), 'Service-specific instruction.\n');
    await assert.rejects(fs.stat(path.join(o.workspaceRoot, 'service/.agents')), { code: 'ENOENT' });
    assert((await fs.readFile(path.join(o.homeDir, '.codex/AGENTS.md'), 'utf8')).includes(o.workspaceRoot));
    for (const folder of ['.agents', '.gemini', '.claude']) assert.equal((await fs.realpath(path.join(o.homeDir, folder, 'skills/example'))).toLowerCase(), (await fs.realpath(path.join(o.councilRoot, 'skills/example'))).toLowerCase());
    for (const file of ['.gemini/GEMINI.md', '.claude/CLAUDE.md']) assert((await fs.readFile(path.join(o.homeDir, file), 'utf8')).includes(o.councilRoot));
    assert.equal(await fs.readFile(path.join(o.workspaceRoot, 'AGENTS.md'), 'utf8'), 'Personal workspace instruction.\n');
    const hooks = JSON.parse(await fs.readFile(path.join(o.homeDir, '.codex/hooks.json'), 'utf8'));
    assert.deepEqual(hooks.custom, { retain: true });
    assert(hooks.hooks.Stop.some(group => group.hooks.some(h => h.command === 'existing-command')));
    assert.equal((await installCouncil(o)).changed.length, 0);
    assert.deepEqual(await fs.readFile(path.join(o.councilRoot, 'skills/example/references/helper.bin')), Buffer.from([0, 1, 2, 255]));
  });
  await test('Install_RejectsCentralOverridesAndProfileSkillConflicts_BeforeWriting', async () => {
    const o = await fixture();
    await fs.mkdir(path.join(o.homeDir, '.codex'), { recursive: true });
    await fs.writeFile(path.join(o.homeDir, '.codex/AGENTS.override.md'), 'Override');
    await assert.rejects(() => installCouncil(o), /override/i);
    await assert.rejects(fs.stat(path.join(o.workspaceRoot, 'AGENTS.md')), { code: 'ENOENT' });
    await fs.unlink(path.join(o.homeDir, '.codex/AGENTS.override.md'));
    await fs.mkdir(path.join(o.homeDir, '.agents/skills/example'), { recursive: true });
    await assert.rejects(() => installCouncil(o), /conflict/i);
    await assert.rejects(fs.stat(path.join(o.workspaceRoot, 'AGENTS.md')), { code: 'ENOENT' });
  });
  await test('ManagedBlocks_RejectMalformedAndDuplicateMarkers', async () => {
    assert.throws(() => mergeManagedBlock('<!-- COUNCIL CODEX BEGIN -->', 'body'), /block/i);
    const once = mergeManagedBlock('User text', 'body');
    assert.equal(mergeManagedBlock(once, 'body'), once);
    assert.throws(() => mergeManagedBlock(once + once, 'body'), /block/i);
  });
  await test('Validate_DetectsStaleInstructionRuleAndSupportContent', async () => {
    const o = await fixture(); await installCouncil(o);
    await fs.writeFile(path.join(o.homeDir, '.codex/AGENTS.md'), '<!-- COUNCIL CODEX BEGIN -->\nwrong instruction\n<!-- COUNCIL CODEX END -->');
    await fs.writeFile(path.join(o.councilRoot, 'rules/workspace.md'), 'wrong rules');
    await fs.writeFile(path.join(o.councilRoot, 'skills/example/references/helper.bin'), 'wrong binary');
    const report = await validateCouncil(o);
    assert.equal(report.placement.status, 'fail');
    for (const term of ['instruction', 'rules', 'helper.bin']) assert(report.placement.errors.some(e => e.includes(term)), JSON.stringify(report));
  });
  await test('Validate_RejectsOverrideAndCopiedSkills_WhenContentMatches', async () => {
    const o = await fixture(); await installCouncil(o);
    const linked = path.join(o.homeDir, '.agents/skills/example');
    await fs.unlink(linked);
    await fs.cp(path.join(o.councilRoot, 'skills/example'), linked, { recursive: true });
    await fs.writeFile(path.join(o.homeDir, '.codex/AGENTS.override.md'), 'override');
    const report = await validateCouncil(o);
    assert(report.placement.errors.some(e => /junction|link/i.test(e)));
    assert(report.placement.errors.some(e => /override/i.test(e)));
  });
  await test('Validate_ReportsAbsentLifecycle_WithoutClaimingReadiness', async () => {
    const o = await fixture(); await installCouncil(o);
    await fs.unlink(path.join(o.homeDir, '.codex/hooks.json'));
    const report = await validateCouncil(o);
    assert.equal(report.placement.status, 'pass');
    assert.equal(report.lifecycle.status, 'absent');
    assert.equal(report.ready, false);
  });
  await test('Hooks_ExcludeOutsideWorkspace_AndRejectInvalidInput', async () => {
    const o = await fixture();
    assert.deepEqual(await handleHook({ hook_event_name: 'Stop', cwd: o.workspaceRoot + '-other', session_id: 'session', turn_id: 'turn' }, o), {});
    await assert.rejects(fs.stat(memoryRoot(o.homeDir, o.username)), { code: 'ENOENT' });
    assert.deepEqual(await handleHook(null, o), {});
    assert.deepEqual(await handleHook({ hook_event_name: 'AfterAgent', cwd: o.workspaceRoot }, o), {});
  });
  await test('Onboard_ReadsExistingTimestampBacklog_WithoutCreatingOrDeletingState', async () => {
    const o = await fixture();
    const empty = await readContext(o);
    assert(empty.includes('No saved handoff'));
    await assert.rejects(fs.stat(memoryRoot(o.homeDir, o.username)), { code: 'ENOENT' });
    await fs.mkdir(memoryRoot(o.homeDir, o.username), { recursive: true });
    await fs.writeFile(path.join(memoryRoot(o.homeDir, o.username), 'active_session_backlog.md'), '2026-10-12T08:00:00Z | Existing milestone\n');
    const context = await readContext(o);
    assert(context.includes('Existing milestone'));
    const output = await handleHook({ hook_event_name: 'SessionStart', cwd: o.workspaceRoot, source: 'startup' }, o);
    assert.equal(output.hookSpecificOutput.hookEventName, 'SessionStart');
    assert(output.hookSpecificOutput.additionalContext.includes('Existing milestone'));
  });
  await test('Onboard_BoundsLargeHandoffAndBacklog', async () => {
    const o = await fixture(); const dir = memoryRoot(o.homeDir, o.username);
    await fs.mkdir(dir, { recursive: true });
    await fs.writeFile(path.join(dir, 'active_handoff.md'), 'x'.repeat(200000));
    await fs.writeFile(path.join(dir, 'active_session_backlog.md'), Array.from({ length: 1000 }, (_, i) => 'milestone ' + i).join('\n'));
    const context = await readContext(o);
    assert(context.length <= 12000);
    assert(context.includes('milestone 999'));
    assert(!context.includes('milestone 0\n'));
  });
  await test('Heartbeat_DeduplicatesRetryAndConcurrentEvents_WithoutPayloadLeak', async () => {
    const o = await fixture();
    const payload = { hook_event_name: 'Stop', cwd: o.workspaceRoot, session_id: 'session', turn_id: 'one', last_assistant_message: 'PRIVATE_MARKER', transcript_path: 'PRIVATE_MARKER' };
    await Promise.all(Array.from({ length: 8 }, () => handleHook(payload, o)));
    await Promise.all(Array.from({ length: 5 }, (_, i) => handleHook({ ...payload, turn_id: 'extra-' + i }, o)));
    const dir = memoryRoot(o.homeDir, o.username);
    const backlog = await fs.readFile(path.join(dir, 'active_session_backlog.md'), 'utf8');
    assert.equal(backlog.trim().split('\n').length, 6);
    assert(!backlog.includes('PRIVATE_MARKER'));
    const state = JSON.parse(await fs.readFile(path.join(dir, 'heartbeat_state.json'), 'utf8'));
    assert.equal(state.last_actor, 'codex');
    assert(!JSON.stringify(state).includes('PRIVATE_MARKER'));
    assert(!backlog.includes('tests passed'));
  });
  await test('ToolMilestones_RecordOnlyConfirmedCompletion_AndNeverRawCommands', async () => {
    const o = await fixture(); const payload = { hook_event_name: 'PostToolUse', cwd: o.workspaceRoot, session_id: 'session', turn_id: 'turn', tool_name: 'Bash', tool_input: { command: 'PRIVATE_COMMAND' } };
    await handleHook({ ...payload, tool_use_id: 'failed', tool_response: { exit_code: 1 } }, o);
    await handleHook({ ...payload, tool_use_id: 'running', tool_response: { session_id: 12 } }, o);
    await handleHook({ ...payload, tool_use_id: 'unknown', tool_response: { output: 'PRIVATE_OUTPUT' } }, o);
    await handleHook({ ...payload, tool_use_id: 'success', tool_response: { exit_code: 0 } }, o);
    const log = await fs.readFile(path.join(memoryRoot(o.homeDir, o.username), 'active_session_backlog.md'), 'utf8');
    assert.equal(log.trim().split('\n').length, 1);
    assert(log.includes('Shell command completed (exit 0)'));
    assert(!log.includes('PRIVATE'));
  });
  await test('HookConfig_DoesNotRegisterApprovalOrBlockingHandlers', async () => {
    const o = await fixture(); const config = buildHooks({ ...o, nodePath: 'C:/Program Files/nodejs/node.exe' });
    assert.deepEqual(Object.keys(config.hooks).sort(), ['Interrupt', 'PostToolUse', 'SessionStart', 'Stop']);
    for (const groups of Object.values(config.hooks)) for (const g of groups) for (const h of g.hooks) { assert.equal(h.type, 'command'); assert(h.commandWindows.startsWith('powershell.exe ')); assert(h.commandWindows.includes("& 'C:/Program Files/nodejs/node.exe'")); }
  });
  await test('CLI_ReportsFailedValidation_AndRejectsUnknownOptions', async () => {
    const { executeCommand } = await import('../council-codex.mjs');
    const o = await fixture();
    const args = ['validate', '--workspace', o.workspaceRoot, '--payload', o.payloadRoot, '--home', o.homeDir, '--username', o.username];
    const report = await executeCommand(args);
    assert.equal(report.exitCode, 1);
    assert.equal(JSON.parse(report.output).ready, false);
    await assert.rejects(() => executeCommand(['validate', '--unknown', 'value']), /Unknown option/);
    await assert.rejects(() => executeCommand(['hook'], { input: '{bad JSON' }), /Invalid hook JSON/);
  });
  await test('Validate_ReportsMalformedHookConfig_AsFailure', async () => {
    const o = await fixture(); await installCouncil(o);
    await fs.writeFile(path.join(o.homeDir, '.codex/hooks.json'), '{bad');
    assert.equal((await validateCouncil(o)).lifecycle.status, 'fail');
  });
  await test('Install_RejectsLinkedPayloadTargets_AndMalformedHooks_BeforeWriting', async () => {
    const o = await fixture();
    await fs.mkdir(path.join(o.homeDir, '.codex'), { recursive: true });
    await fs.writeFile(path.join(o.homeDir, '.codex/hooks.json'), '{bad');
    await assert.rejects(() => installCouncil(o), /Invalid JSON configuration/);
    await assert.rejects(fs.stat(path.join(o.workspaceRoot, 'AGENTS.md')), { code: 'ENOENT' });
    await fs.unlink(path.join(o.homeDir, '.codex/hooks.json'));
    await fs.mkdir(path.join(o.councilRoot, 'skills'), { recursive: true });
    const outside = path.join(o.homeDir, 'outside'); await fs.mkdir(outside);
    await fs.symlink(outside, path.join(o.councilRoot, 'skills/example'), 'junction');
    await assert.rejects(() => installCouncil(o), /link|escape/i);
    assert.equal((await fs.readdir(outside)).length, 0);
  });
  await test('Install_DeploysFullCouncilPayload_AndVerifiesAllPackages', async () => {
    const o = await fixture();
    o.payloadRoot = path.basename(path.resolve(scriptRoot, '..')) === '.council' ? path.resolve(scriptRoot, '..') : path.resolve(scriptRoot, '../temp/the-council/central');
    const installed = await installCouncil(o);
    assert.equal(installed.report.skills, 24);
    assert.equal(installed.report.repositories, 1);
    assert.equal(installed.report.placement.errors.length, 0);
    assert.equal(installed.report.lifecycle.status, 'configured');
    const profile = JSON.parse(await fs.readFile(path.join(o.councilRoot, 'profiles/fulfillment/profile.json'), 'utf8'));
    assert.equal(profile.id, 'fulfillment');
    assert.deepEqual(await fs.readFile(path.join(o.councilRoot, 'exclusions/global.ignore')), await fs.readFile(path.join(o.payloadRoot, 'exclusions/global.ignore')));
    assert.deepEqual(await fs.readFile(path.join(o.councilRoot, 'rules/global.md')), await fs.readFile(path.join(o.payloadRoot, 'rules/global.md')));
    assert.equal((await fs.realpath(path.join(o.homeDir, '.gemini/policies'))).toLowerCase(), path.resolve(o.councilRoot, 'adapters/gemini/policies').toLowerCase());
    const { verifySourceLock } = await import('../council-source.mjs');
    assert.equal((await verifySourceLock(o.councilRoot)).status, 'pass');
    assert.equal((await installCouncil(o)).changed.length, 0);
  });
  await test('Install_BacksUpChangedFiles_AndPreservesMalformedState', async () => {
    const o = await fixture(); await installCouncil(o);
    const target = path.join(o.councilRoot, 'rules/workspace.md');
    await fs.writeFile(target, 'Prior rules');
    const result = await installCouncil(o);
    const backups = (await fs.readFile(path.join(result.backupRoot, 'files.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    const entry = backups.find(row => row.target === target);
    assert(entry);
    assert.equal(await fs.readFile(entry.backup, 'utf8'), 'Prior rules');
    const dir = memoryRoot(o.homeDir, o.username);
    await fs.writeFile(path.join(dir, 'heartbeat_state.json'), '{bad');
    await assert.rejects(() => handleHook({ hook_event_name: 'Stop', cwd: o.workspaceRoot, session_id: 's', turn_id: 't' }, o), /preserve it for review/);
    assert.equal(await fs.readFile(path.join(dir, 'heartbeat_state.json'), 'utf8'), '{bad');
    await assert.rejects(fs.stat(path.join(dir, 'heartbeat.lock')), { code: 'ENOENT' });
  });
  await test('Install_RejectsMissingRuntimeAndEscapedBackups_BeforeWriting', async () => {
    const o = await fixture();
    await assert.rejects(() => installCouncil({ ...o, scriptRoot: path.join(o.workspaceRoot, 'missing') }), /script/i);
    await assert.rejects(() => installCouncil({ ...o, nodePath: path.join(o.workspaceRoot, 'missing-node.exe') }), /Node/i);
    await assert.rejects(fs.stat(path.join(o.workspaceRoot, 'AGENTS.md')), { code: 'ENOENT' });
    const outside = path.join(o.homeDir, 'outside-backups'); await fs.mkdir(outside, { recursive: true });
    await fs.mkdir(o.councilRoot, { recursive: true });
    await fs.symlink(outside, path.join(o.councilRoot, 'backups'), 'junction');
    await fs.writeFile(path.join(o.workspaceRoot, 'AGENTS.md'), 'Prior instructions');
    await assert.rejects(() => installCouncil(o), /escape|link/i);
    assert.equal(await fs.readFile(path.join(o.workspaceRoot, 'AGENTS.md'), 'utf8'), 'Prior instructions');
    assert.equal((await fs.readdir(outside)).length, 0);
  });
  await test('Install_DoesNotCreateCouncilArtifacts_InsideProjects', async () => {
    const o = await fixture(); await installCouncil(o);
    assert.equal((await fs.readdir(path.join(o.workspaceRoot, 'service'))).join(','), '.git');
  });
  await test('Cleanup_RemovesOnlyCanonicalCouncilLinks_AndMovesExistingInstructionsCentrally', async () => {
    const o = await fixture();
    await fs.mkdir(path.join(o.workspaceRoot, '.agents/skills/example'), { recursive: true });
    const repo = path.join(o.workspaceRoot, 'service');
    await fs.mkdir(path.join(repo, '.agents/skills'), { recursive: true });
    await fs.symlink(path.join(o.workspaceRoot, '.agents/skills/example'), path.join(repo, '.agents/skills/example'), 'junction');
    await fs.mkdir(path.join(repo, '.agents/skills/local-test'), { recursive: true });
    await fs.writeFile(path.join(repo, '.agents/skills/local-test/SKILL.md'), 'Project-owned skill.');
    const original = 'Existing project guidance.\n';
    await fs.writeFile(path.join(repo, 'AGENTS.md'), mergeManagedBlock(original, 'Legacy Council instructions'));
    const cleanup = await cleanupCouncilProjects(o);
    assert.equal(cleanup.removedLinks, 1);
    assert.equal(cleanup.retainedSkills, 1);
    const moves = (await fs.readFile(path.join(cleanup.backupRoot, 'files.jsonl'), 'utf8')).trim().split('\n').map(line => JSON.parse(line));
    assert(moves.some(row => row.kind === 'skill' && row.retainedTarget === path.join(o.councilRoot, 'project-skills/service/local-test')));
    assert.equal(await fs.readFile(path.join(o.councilRoot, 'project-skills/service/local-test/SKILL.md'), 'utf8'), 'Project-owned skill.');
    await assert.rejects(fs.stat(path.join(repo, 'AGENTS.md')), { code: 'ENOENT' });
    await assert.rejects(fs.stat(path.join(repo, '.agents')), { code: 'ENOENT' });
    assert.equal(await fs.readFile(path.join(o.councilRoot, 'project-instructions/service.md'), 'utf8'), original);
    assert.equal((await fs.stat(path.join(o.workspaceRoot, '.agents/skills/example'))).isDirectory(), true);
    assert.equal((await cleanupCouncilProjects(o)).removedLinks, 0);
  });
  await test('Cleanup_PreservesForeignSkillTargets_AndCanKeepOriginalInstructions', async () => {
    const o = await fixture(); const repo = path.join(o.workspaceRoot, 'service');
    const foreign = path.join(o.homeDir, 'foreign-skill'); await fs.mkdir(foreign, { recursive: true });
    await fs.mkdir(path.join(repo, '.agents/skills'), { recursive: true });
    await fs.symlink(foreign, path.join(repo, '.agents/skills/example'), 'junction');
    await fs.writeFile(path.join(repo, 'AGENTS.md'), mergeManagedBlock('Original instructions.\n', 'Legacy Council instructions'));
    const cleanup = await cleanupCouncilProjects({ ...o, relocateExistingInstructions: false });
    assert.equal(cleanup.removedLinks, 0);
    assert.equal(await fs.readFile(path.join(repo, 'AGENTS.md'), 'utf8'), 'Original instructions.\n');
    assert.equal((await fs.realpath(path.join(repo, '.agents/skills/example'))).toLowerCase(), foreign.toLowerCase());
  });
  await test('Install_MigratesOnlyFingerprintedLegacyProfileSkills_WithoutLosingFiles', async () => {
    const o = await fixture(); const legacy = path.join(o.homeDir, '.gemini/skills/example');
    await fs.mkdir(legacy, { recursive: true }); const original = 'Old Gemini instructions';
    await fs.writeFile(path.join(legacy, 'SKILL.md'), original);
    await fs.writeFile(path.join(o.payloadRoot, 'legacy-fingerprints.json'), JSON.stringify({ profiles: { '.gemini': { example: { 'SKILL.md': createHash('sha256').update(original).digest('hex') } } } }));
    const installed = await installCouncil(o);
    assert.equal((await fs.realpath(legacy)).toLowerCase(), (await fs.realpath(path.join(o.councilRoot, 'skills/example'))).toLowerCase());
    assert.equal(await fs.readFile(path.join(installed.backupRoot, 'legacy-skills/.gemini/example/SKILL.md'), 'utf8'), original);
  });
  await test('Hooks_UseModelSpecificSchemas_AndShareOnlyOneMemoryDirectory', async () => {
    const o = await fixture();
    const restored = await handleHook({ hook_event_name: 'SessionStart', cwd: o.workspaceRoot }, { ...o, actor: 'gemini' });
    assert.equal(Object.hasOwn(restored.hookSpecificOutput, 'hookEventName'), false);
    const gemini = buildHooks({ ...o, actor: 'gemini' });
    assert(gemini.hooks.AfterAgent); assert.equal(gemini.hooks.AfterAgent[0].hooks[0].timeout, 3000);
    const claude = buildHooks({ ...o, actor: 'claude' });
    assert(claude.hooks.Stop); assert.equal(claude.hooks.Stop[0].hooks[0].timeout, 3);
    await handleHook({ hook_event_name: 'AfterAgent', timestamp: '2026-10-12T12:00:00Z', session_id: 's', cwd: o.workspaceRoot, prompt_response: 'PRIVATE_REPLY' }, { ...o, actor: 'gemini' });
    await handleHook({ hook_event_name: 'Stop', prompt_id: 'prompt', session_id: 's', cwd: o.workspaceRoot, last_assistant_message: 'PRIVATE_REPLY' }, { ...o, actor: 'claude' });
    const dir = memoryRoot(o.homeDir, o.username);
    const log = await fs.readFile(path.join(dir, 'active_session_backlog.md'), 'utf8');
    assert.equal(log.trim().split('\n').length, 2); assert(!log.includes('PRIVATE_REPLY'));
    assert.equal(JSON.parse(await fs.readFile(path.join(dir, 'heartbeat_state.json'), 'utf8')).last_actor, 'claude');
  });
  await test('Validate_DetectsAChangedClaudeHook_AndProfileLinksReadLiveCanonicalEdits', async () => {
    const o = await fixture(); await installCouncil(o);
    await fs.writeFile(path.join(o.homeDir, '.claude/settings.json'), JSON.stringify({ hooks: {} }));
    assert.equal((await validateCouncil(o)).lifecycle.status, 'fail');
    await fs.writeFile(path.join(o.homeDir, '.claude/skills/example/SKILL.md'), 'One shared update');
    for (const folder of ['.agents', '.gemini']) assert.equal(await fs.readFile(path.join(o.homeDir, folder, 'skills/example/SKILL.md'), 'utf8'), 'One shared update');
  });
  await test('Install_ImportsLegacyMemory_WithoutOverwritingCanonicalNotes', async () => {
    const o = await fixture(); const old = path.join(o.homeDir, '.gemini/tmp', o.username, 'memory');
    await fs.mkdir(old, { recursive: true }); await fs.writeFile(path.join(old, 'active_handoff.md'), 'Saved objective');
    await fs.writeFile(path.join(old, 'active_session_backlog.md'), '2026-10-12 | old milestone\n');
    await installCouncil(o);
    const dir = memoryRoot(o.homeDir, o.username);
    assert.equal(await fs.readFile(path.join(dir, 'active_handoff.md'), 'utf8'), 'Saved objective');
    assert((await fs.readFile(path.join(dir, 'active_session_backlog.md'), 'utf8')).includes('old milestone'));
    await assert.rejects(fs.stat(path.join(old, 'active_handoff.md')), { code: 'ENOENT' });
    await fs.writeFile(path.join(dir, 'active_handoff.md'), 'Current objective');
    await installCouncil(o);
    assert.equal(await fs.readFile(path.join(dir, 'active_handoff.md'), 'utf8'), 'Current objective');
  });
  await test('Install_PreservesGeminiPolicyThroughACentralDirectoryLink', async () => {
    const o = await fixture(); const old = path.join(o.homeDir, '.gemini/policies');
    await fs.mkdir(old, { recursive: true }); const policy = '# Existing policy\n';
    await fs.writeFile(path.join(old, 'council.toml'), policy);
    await fs.writeFile(path.join(o.payloadRoot, 'legacy-fingerprints.json'), JSON.stringify({ profilePolicies: { 'council.toml': createHash('sha256').update(policy).digest('hex') } }));
    await installCouncil(o);
    const canonical = path.join(o.councilRoot, 'adapters/gemini/policies');
    assert.equal((await fs.realpath(old)).toLowerCase(), (await fs.realpath(canonical)).toLowerCase());
    assert.equal(await fs.readFile(path.join(canonical, 'council.toml'), 'utf8'), policy);
    await fs.unlink(old); await fs.mkdir(old);
    assert.equal((await validateCouncil(o)).placement.status, 'fail');
  });
  await test('Validate_CanUseTheInstalledRootAsItsOwnSource_AndRetiresLegacyGeminiContext', async () => {
    const o = await fixture(); const global = path.join(o.homeDir, '.gemini/GEMINI.md');
    const rules = path.join(o.homeDir, '.gemini/.rules/rules.md');
    const old = '# Personal preferences\n@./.rules/rules.md\n\n## 4. Automatic Session Onboarding\nOld onboarding\n## 6. The Council V2\nOld definitions\n';
    await fs.mkdir(path.dirname(rules), { recursive: true }); await fs.writeFile(rules, 'Global guardrails'); await fs.writeFile(global, old);
    await fs.writeFile(path.join(o.payloadRoot, 'legacy-fingerprints.json'), JSON.stringify({ globalInstructions: { '.gemini/GEMINI.md': createHash('sha256').update(old).digest('hex') }, profileFiles: { '.gemini/.rules/rules.md': createHash('sha256').update('Global guardrails').digest('hex') } }));
    await installCouncil(o);
    const current = await fs.readFile(global, 'utf8');
    assert(current.includes('Personal preferences')); assert(!current.includes('Old onboarding'));
    assert(current.includes('rules/global.md'));
    assert.equal(await fs.readFile(path.join(o.councilRoot, 'rules/global.md'), 'utf8'), 'Global guardrails');
    const canonical = await validateCouncil({ ...o, payloadRoot: o.councilRoot, scriptRoot: path.join(o.councilRoot, 'scripts') });
    assert.equal(canonical.placement.status, 'pass', JSON.stringify(canonical));
  });
  await test('InvalidSettings_DoNotExposePrivateJSON_InErrorMessages', async () => {
    const o = await fixture(); await fs.mkdir(path.join(o.homeDir, '.claude'), { recursive: true });
    await fs.writeFile(path.join(o.homeDir, '.claude/settings.json'), 'PRIVATE_SETTINGS_MARKER invalid JSON');
    try { await installCouncil(o); assert.fail('Expected malformed settings rejection'); }
    catch (error) { assert(!error.message.includes('PRIVATE_SETTINGS_MARKER')); assert(error.message.includes('Invalid JSON configuration')); }
  });
  await test('Install_ArchivesFingerprintedWorkspaceEngine_WithoutExecutingIt', async () => {
    const o = await fixture(); const engine = path.join(o.workspaceRoot, 'tools/council');
    await fs.mkdir(engine, { recursive: true }); await fs.writeFile(path.join(engine, 'legacy.py'), 'Original engine source');
    await fs.writeFile(path.join(o.payloadRoot, 'legacy-fingerprints.json'), JSON.stringify({ workspaceFolders: { 'tools/council': { 'legacy.py': createHash('sha256').update('Original engine source').digest('hex') } } }));
    await installCouncil(o);
    await assert.rejects(fs.stat(engine), { code: 'ENOENT' });
    assert.equal(await fs.readFile(path.join(o.councilRoot, 'legacy/workspace/tools/council/legacy.py'), 'utf8'), 'Original engine source');
  });

  await test('Install_MergesGeminiSettings_PreservesUserPreferences_AndHandlesMalformedTypes', async () => {
    const o = await fixture();
    // 1. Pure mergeGeminiSettings unit checks
    const mergedPure = mergeGeminiSettings({
      security: { auth: 'custom' },
      context: {
        fileFiltering: {
          respectGeminiIgnore: false,
          customIgnoreFilePaths: ['C:/custom/ignore']
        }
      }
    }, o);
    assert.equal(mergedPure.security.auth, 'custom');
    assert.equal(mergedPure.context.fileFiltering.respectGeminiIgnore, false);
    assert(mergedPure.context.fileFiltering.customIgnoreFilePaths.includes('C:/custom/ignore'));
    assert(mergedPure.context.fileFiltering.customIgnoreFilePaths.some(p => p.toLowerCase().includes('exclusions')));

    // 2. Malformed type handling
    const malformed = mergeGeminiSettings({ context: 42 }, o);
    assert.equal(typeof malformed.context, 'object');
    assert.equal(malformed.context.fileFiltering.respectGeminiIgnore, true);
    assert(Array.isArray(malformed.context.fileFiltering.customIgnoreFilePaths));

    // 3. End-to-end installCouncil with pre-existing settings
    const geminiSettings = path.join(o.homeDir, '.gemini/settings.json');
    await fs.mkdir(path.dirname(geminiSettings), { recursive: true });
    await fs.writeFile(geminiSettings, JSON.stringify({
      security: { customKey: 'preserved' },
      context: { fileFiltering: { respectGeminiIgnore: false, customIgnoreFilePaths: ['C:/my-existing/ignore'] } }
    }));
    await installCouncil(o);
    const installed = JSON.parse(await fs.readFile(geminiSettings, 'utf8'));
    assert.equal(installed.security.customKey, 'preserved');
    assert.equal(installed.context.fileFiltering.respectGeminiIgnore, false);
    assert(installed.context.fileFiltering.customIgnoreFilePaths.includes('C:/my-existing/ignore'));
    assert(installed.context.fileFiltering.customIgnoreFilePaths.some(p => p.toLowerCase().includes('exclusions')));
    assert(installed.hooks.AfterAgent.length > 0);
  });

  await test('Install_SucceedsWithSpacesInPaths_AndCustomUsername', async () => {
    const o = await fixture();
    const baseWithSpaces = path.join(path.dirname(o.workspaceRoot), 'dir with spaces');
    await fs.mkdir(baseWithSpaces, { recursive: true });
    const spaceOptions = {
      ...o,
      workspaceRoot: path.join(baseWithSpaces, 'my workspace'),
      homeDir: path.join(baseWithSpaces, 'my user profile'),
      username: 'Special User Name'
    };
    spaceOptions.councilRoot = path.join(spaceOptions.homeDir, '.council');
    await fs.mkdir(spaceOptions.workspaceRoot, { recursive: true });
    await fs.mkdir(spaceOptions.homeDir, { recursive: true });
    await installCouncil(spaceOptions);
    const report = await validateCouncil(spaceOptions);
    assert.equal(report.placement.status, 'pass', JSON.stringify(report.placement.errors));
    const geminiMd = await fs.readFile(path.join(spaceOptions.homeDir, '.gemini/GEMINI.md'), 'utf8');
    assert(!geminiMd.includes('@file'), 'Managed block must not contain literal @file prose');
    assert(geminiMd.includes(spaceOptions.councilRoot));
  });

  await test('Validate_DistinguishesIdenticalCanonicalAliases_FromGenuineSkillConflicts', async () => {
    const o = await fixture();
    await installCouncil(o);
    // Verified: initial aliases point to canonical package
    const report1 = await validateCouncil(o);
    assert.equal(report1.placement.status, 'pass');

    // Create a genuine conflict: replace .agents/skills/example with a non-canonical target
    const conflictDir = path.join(path.dirname(o.workspaceRoot), 'foreign-skill');
    await fs.mkdir(conflictDir, { recursive: true });
    await fs.writeFile(path.join(conflictDir, 'SKILL.md'), '---\nname: example\ndescription: Foreign\n---\n');
    const linked = path.join(o.homeDir, '.agents/skills/example');
    await fs.unlink(linked);
    await fs.symlink(conflictDir, linked, 'junction');
    const report2 = await validateCouncil(o);
    assert.equal(report2.placement.status, 'fail');
    assert(report2.placement.errors.some(e => e.includes('Profile skill junction/link mismatch')));
  });

  for (const base of fixtures) {
    const resolved = await fs.realpath(base);
    const relative = path.relative(fixtureParent, resolved);
    if (!relative.startsWith('fixture-') || relative.includes(path.sep) || path.isAbsolute(relative)) throw new Error('Fixture cleanup path escaped the test directory');
    await fs.rm(resolved, { recursive: true, force: true });
  }
  return { total: results.length, passed: results.filter(r => r.status === 'pass').length, failed: results.filter(r => r.status === 'fail').length, results };
}

if (globalThis.process?.argv[1] && path.resolve(globalThis.process.argv[1]) === fileURLToPath(import.meta.url)) {
  runTests().then(report => { console.log(JSON.stringify(report, null, 2)); process.exitCode = report.failed ? 1 : 0; }).catch(error => { console.error(error.message); process.exitCode = 1; });
}
