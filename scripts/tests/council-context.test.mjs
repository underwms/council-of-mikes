import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { readContext, memoryRoot } from '../council-memoryforge.mjs';

const base = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../work/context-tests');
async function fixture(t, selection = {}) {
  await fs.mkdir(base, { recursive: true });
  const homeDir = await fs.mkdtemp(path.join(base, 'fixture-'));
  const options = { homeDir, username: 'test', workspaceRoot: homeDir, ...selection };
  const memory = memoryRoot(homeDir, 'test', options);
  await fs.mkdir(memory, { recursive: true });
  t.after(async () => { assert(path.dirname(homeDir) === base); await fs.rm(homeDir, { recursive: true, force: true }); });
  return { options, write: (name, value) => fs.writeFile(path.join(memory, name), value) };
}
test('current summary replaces stale handoff in startup while preserving history', async t => {
  const f = await fixture(t);
  await f.write('current_state.md', 'Updated: 2026-11-12\nCurrent: inspect parcel rounding. Graph remains stopped.');
  await f.write('active_handoff.md', 'OLD_TASK: restart the graph');
  await f.write('preferences.md', 'Use FAIR feature tests.');
  await f.write('active_session_backlog.md', '2026-11-12: source checks passed.\n');
  const context = await readContext(f.options);
  assert(context.includes('inspect parcel rounding'));
  assert(context.includes('Use FAIR'));
  assert(context.includes('source checks passed'));
  assert(!context.includes('OLD_TASK'));
});
test('startup prefers meaningful milestones to lifecycle noise and bounds context', async t => {
  const f = await fixture(t);
  await f.write('current_state.md', 'Current: investigate shipping.\n' + 'x'.repeat(18000));
  await f.write('active_session_backlog.md', 'LATEST_VERIFIED_FEATURE_CHECK\n' + Array.from({length: 30}, (_, i) => `2026-11-12 | Agent turn ended <!-- event:${i} -->`).join('\n'));
  const context = await readContext(f.options);
  assert(context.includes('LATEST_VERIFIED_FEATURE_CHECK'));
  assert(context.length <= 12000);
});
test('bounded memory reads preserve UTF-8 at both head and tail boundaries', async t => {
  const f = await fixture(t);
  await f.write('active_handoff.md', '\u20ac'.repeat(5000));
  await f.write('active_session_backlog.md', '\u20ac'.repeat(12000) + '\nTAIL_MARKER\n');
  const context = await readContext(f.options);
  assert(!context.includes('\ufffd'));
  assert(context.includes('TAIL_MARKER'));
});
test('invalid saved UTF-8 is reported instead of silently replaced', async t => {
  const f = await fixture(t);
  await f.write('current_state.md', Buffer.from([0xff, 0xfe, 0x41]));
  await assert.rejects(readContext(f.options), /UTF-8|encoded data/i);
});
test('selected session summary never leaks default memory', async t => {
  const f = await fixture(t, { memoryScope: 'workspace-session', session: 'selected' });
  await f.write('current_state.md', 'SELECTED_TASK');
  const legacy = memoryRoot(f.options.homeDir, 'test');
  await fs.writeFile(path.join(legacy, 'current_state.md'), 'OTHER_TASK');
  const context = await readContext(f.options);
  assert(context.includes('SELECTED_TASK'));
  assert(!context.includes('OTHER_TASK'));
});
