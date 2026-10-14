import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import test from 'node:test';

const central = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const fixtureParent = path.join(central, 'work/source-tests');
const executeFile = promisify(execFile);

async function fixture(t) {
  await fs.mkdir(fixtureParent, { recursive: true });
  const root = await fs.mkdtemp(path.join(fixtureParent, 'fixture-'));
  t.after(async () => {
    const resolved = await fs.realpath(root);
    const relative = path.relative(fixtureParent, resolved);
    assert(relative.startsWith('fixture-') && !relative.includes(path.sep));
    await fs.rm(resolved, { recursive: true, force: true });
  });
  async function write(relative, content) {
    await fs.mkdir(path.dirname(path.join(root, relative)), { recursive: true });
    await fs.writeFile(path.join(root, relative), typeof content === 'string' ? content : JSON.stringify(content, null, 2));
  }
  const manifest = { schema_version: 1, version: '3.0.0', skills: ['the-example', 'example-flow'],
    specialists: ['the-example'], workflows: ['example-flow'], default_profile: 'fulfillment',
    paths: { skills: 'skills', shared: 'instructions/shared.md', host_rules: 'rules/global.md', workspace_rules: 'rules/workspace.md', exclusions: 'exclusions/global.ignore' },
    profiles: { fulfillment: 'profiles/fulfillment/profile.json' },
    adapters: { codex: 'adapters/codex.json' }, execution: { scope: 'user', routine_development: 'allow_without_prompt' },
    source_roots: ['skills', 'instructions', 'rules', 'profiles', 'adapters', 'exclusions'], source_files: ['manifest.json'] };
  await write('manifest.json', manifest);
  for (const name of manifest.skills) await write(`skills/${name}/SKILL.md`, `---\nname: ${name}\ndescription: Scoped fixture skill\n---\n# Fixture\n`);
  await write('skills/the-example/references/the-example.md', '# Domain reference\n');
  await write('instructions/shared.md', '# Shared\n[Profile](../profiles/fulfillment/rules.md)\n');
  await write('rules/global.md', '# Host invariants\n');
  await write('rules/workspace.md', '# Selected profile\n');
  await write('profiles/fulfillment/profile.json', { id: 'fulfillment', rules: 'rules.md', corporate_rules: 'corporate.md', stack: { persistence: 'EF Core / PostgreSQL', forbidden: ['Redis', 'Dapper'], unit_tests: 'MSTest.Sdk / NSubstitute' } });
  await write('profiles/fulfillment/rules.md', '# Current doctrine\n');
  await write('profiles/fulfillment/corporate.md', '# Corporate doctrine\n');
  await write('adapters/codex.json', { id: 'codex', instructions: 'codex.md', execution_scope: 'user', indexing_scope: 'user', policy_fragment: 'codex/config.toml', indexing: 'instruction-guided' });
  await write('adapters/codex.md', '# Native adapter\n');
  await write('adapters/codex/config.toml', 'approval_policy = "never"\n');
  await write('exclusions/global.ignore', '**/bin/\n');
  return { root, write, manifest };
}

test('source audit distinguishes intact source, missing packages, and extra packages', async t => {
  const { auditSource } = await import('../council-source.mjs');
  const f = await fixture(t);
  assert.equal((await auditSource(f.root)).status, 'pass');
  await fs.unlink(path.join(f.root, 'skills/the-example/SKILL.md'));
  assert.equal((await auditSource(f.root)).status, 'fail');
  await f.write('skills/the-example/SKILL.md', '---\nname: the-example\ndescription: restored\n---\n');
  await f.write('skills/unregistered/SKILL.md', '---\nname: unregistered\ndescription: extra\n---\n');
  assert((await auditSource(f.root)).errors.some(e => e.includes('inventory')));
});

test('source lock detects edited, added, and missing content without changing source', async t => {
  const { writeSourceLock, verifySourceLock } = await import('../council-source.mjs');
  const f = await fixture(t);
  const before = await fs.readFile(path.join(f.root, 'instructions/shared.md'));
  await writeSourceLock(f.root);
  assert.equal((await verifySourceLock(f.root)).status, 'pass');
  await f.write('instructions/shared.md', '# Intentional edit\n');
  assert.equal((await verifySourceLock(f.root)).status, 'fail');
  await writeSourceLock(f.root);
  await f.write('skills/example-flow/helper.md', '# New resource\n');
  assert.equal((await verifySourceLock(f.root)).status, 'fail');
  await fs.unlink(path.join(f.root, 'skills/example-flow/helper.md'));
  await fs.writeFile(path.join(f.root, 'instructions/shared.md'), before);
  assert.equal((await verifySourceLock(f.root)).status, 'fail');
});

test('source audit rejects bad metadata, path escape, bad adapters, and broken links', async t => {
  const { auditSource } = await import('../council-source.mjs');
  const f = await fixture(t);
  await f.write('skills/example-flow/SKILL.md', '# Missing metadata\n');
  await f.write('instructions/shared.md', '[Missing](../missing.md)\n[[unknown-member]]\n');
  await f.write('adapters/codex.json', { id: 'wrong', execution_scope: 'workspace', indexing_scope: 'workspace' });
  let result = await auditSource(f.root);
  assert.equal(result.status, 'fail');
  for (const pattern of ['metadata', 'adapter', 'link']) assert(result.errors.some(e => e.toLowerCase().includes(pattern)));
  f.manifest.paths.shared = '../outside.md';
  await f.write('manifest.json', f.manifest);
  assert((await auditSource(f.root)).errors.some(e => e.includes('escapes')));
});

test('runtime memory namespaces share across models while separating workspace and session', async t => {
  const { memoryRoot, handleHook, readContext } = await import('../council-memoryforge.mjs');
  const f = await fixture(t);
  const workspace = path.join(f.root, 'workspace');
  await fs.mkdir(workspace);
  const options = { homeDir: f.root, username: 'test', workspaceRoot: workspace, memoryScope: 'workspace-session', session: 'shared-session' };
  const selected = memoryRoot(f.root, 'test', options);
  assert.notEqual(selected, memoryRoot(f.root, 'test'));
  assert.notEqual(selected, memoryRoot(f.root, 'test', { ...options, session: 'other-session' }));
  assert.throws(() => memoryRoot(f.root, 'test', { ...options, session: '../escape' }));
  assert((await readContext(options)).includes('No saved handoff'));
  await assert.rejects(fs.stat(selected), { code: 'ENOENT' });
  await handleHook({ hook_event_name: 'Stop', cwd: workspace, session_id: 'shared-session', turn_id: 'turn-1' }, { ...options, actor: 'codex' });
  assert((await readContext({ ...options, actor: 'gemini' })).includes('Agent turn ended'));
  assert((await readContext({ ...options, session: 'other-session' })).includes('No milestones'));
  await Promise.all([1, 2, 3].map(() => handleHook({ hook_event_name: 'Stop', cwd: workspace, session_id: 'shared-session', turn_id: 'turn-1' }, options)));
  assert.equal((await fs.readFile(path.join(selected, 'active_session_backlog.md'), 'utf8')).split('\n').filter(Boolean).length, 1);
});

test('installed central source uses unified inventory and current profile doctrine', async () => {
  const { auditSource } = await import('../council-source.mjs');
  const report = await auditSource(central);
  assert.equal(report.status, 'pass', JSON.stringify(report));
  assert.equal(report.specialists, 15);
  assert.equal(report.workflows, 9);
  const manifest = JSON.parse(await fs.readFile(path.join(central, 'manifest.json'), 'utf8'));
  assert.equal(manifest.default_profile, 'fulfillment');
  const documentation = await fs.readFile(path.join(central, 'skills/repo-documentation/SKILL.md'), 'utf8');
  assert(!documentation.includes('Redis caching topologies'));
  assert(!documentation.includes('dapper persistence isolation'));
});

test('source audit checks duplicate inventories and profile doctrine before locking', async t => {
  const { auditSource, writeSourceLock } = await import('../council-source.mjs');
  const f = await fixture(t);
  f.manifest.skills.push('the-example');
  await f.write('manifest.json', f.manifest);
  assert((await auditSource(f.root)).errors.some(e => e.includes('inventory')));
  await assert.rejects(writeSourceLock(f.root), /Refusing source lock refresh/);
  f.manifest.skills.pop();
  await f.write('manifest.json', f.manifest);
  await f.write('profiles/fulfillment/profile.json', { id: 'wrong', rules: 'rules.md', corporate_rules: 'corporate.md', stack: { persistence: 'Redis', forbidden: [], unit_tests: 'Moq' } });
  const errors = (await auditSource(f.root)).errors.join('\n');
  assert(errors.includes('Profile ID mismatch'));
  assert(errors.includes('violates current contracts'));
});

test('source lock handles absent, malformed, and missing required content distinctly', async t => {
  const { auditSource, writeSourceLock, verifySourceLock } = await import('../council-source.mjs');
  const f = await fixture(t);
  assert.equal((await verifySourceLock(f.root)).status, 'absent');
  await f.write('source-lock.json', '{}');
  assert.equal((await verifySourceLock(f.root)).status, 'fail');
  await writeSourceLock(f.root);
  assert.equal((await auditSource(f.root, { checkLock: true })).status, 'pass');
  await fs.unlink(path.join(f.root, 'instructions/shared.md'));
  assert.equal((await verifySourceLock(f.root)).status, 'fail');
  assert.equal((await auditSource(f.root, { checkLock: true })).status, 'fail');
});

test('source links cannot redirect audit inputs or release-lock writes', async t => {
  const { auditSource, writeSourceLock, sourceSnapshot } = await import('../council-source.mjs');
  const f = await fixture(t);
  const outside = path.join(f.root, 'work/outside');
  await fs.mkdir(outside, { recursive: true });
  await fs.symlink(outside, path.join(f.root, 'skills/linked'), 'junction');
  assert.equal((await auditSource(f.root)).status, 'fail');
  await assert.rejects(sourceSnapshot(f.root), /links/);
  await fs.unlink(path.join(f.root, 'skills/linked'));
  // A directory junction at the output filename must not be followed or overwritten.
  await fs.symlink(outside, path.join(f.root, 'source-lock.json'), 'junction');
  await assert.rejects(writeSourceLock(f.root), /links/);
  assert.deepEqual(await fs.readdir(outside), []);
});

test('existing native hooks retain unscoped command defaults', async () => {
  const { buildHooks } = await import('../council-codex-lib.mjs');
  const expected = buildHooks({ workspaceRoot: path.join(central, 'work/runtime'), homeDir: central, nodePath: process.execPath });
  assert(!JSON.stringify(expected).includes('--memory-scope'));
  assert(!JSON.stringify(expected).includes('--session'));
});

test('session memory rejects invalid selections and CLI supports explicit recovery', async t => {
  const { memoryRoot } = await import('../council-memoryforge.mjs');
  const { executeCommand } = await import('../council-codex.mjs');
  const f = await fixture(t);
  assert.throws(() => memoryRoot(f.root, '../bad'), /username/);
  assert.throws(() => memoryRoot(f.root, 'test', { memoryScope: 'unknown' }), /scope/);
  assert.throws(() => memoryRoot(f.root, 'test', { memoryScope: 'workspace-session', workspaceRoot: 'relative', session: 'ok' }), /workspace/);
  assert.throws(() => memoryRoot(f.root, 'test', { memoryScope: 'workspace-session', workspaceRoot: f.root }), /session/);
  const result = await executeCommand(['onboard', '--workspace', f.root, '--home', f.root, '--memory-scope', 'workspace-session', '--session', 'manual-session']);
  assert.equal(result.exitCode, 0);
  assert(result.output.includes('No saved handoff'));
  await assert.rejects(fs.stat(path.join(f.root, '.council/memory')), { code: 'ENOENT' });
});

test('source CLI audits, locks, checks, and reports failure through exit status', async t => {
  const f = await fixture(t);
  const entrypoint = path.join(central, 'scripts/council-source.mjs');
  for (const command of ['audit', 'lock', 'check']) {
    const result = await executeFile(process.execPath, [entrypoint, command, f.root]);
    assert.equal(JSON.parse(result.stdout).status, 'pass');
  }
  await f.write('instructions/shared.md', '# Changed\n');
  await assert.rejects(executeFile(process.execPath, [entrypoint, 'check', f.root]), error => {
    assert.equal(error.code, 1);
    assert.equal(JSON.parse(error.stdout).status, 'fail');
    return true;
  });
  await assert.rejects(executeFile(process.execPath, [entrypoint, 'unknown', f.root]), /Usage/);
});
