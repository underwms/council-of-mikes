import assert from 'node:assert/strict';
import test from 'node:test';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const implementation = await import('../gemini-compat.mjs').catch(() => ({}));
const original = `export function probe(existingSkill, newSkill) {
  const warnings = [];
  const debugLogger = {warn: message => warnings.push(message)};
  const coreEvents = {emitFeedback: (_, message) => warnings.push(message)};
  if (existingSkill && existingSkill.location !== newSkill.location) {
    if (existingSkill.isBuiltin) { debugLogger.warn('builtin'); }
    else { coreEvents.emitFeedback('warning', 'Skill conflict detected'); }
  }
  return warnings;
}
function findUntrustedFlags(command, untrustedContext) {
  return command.includes('--unsafe') ? ['--unsafe'] : [];
}
export { findUntrustedFlags };
`;
async function fixture(t, version = '0.64.0') {
  const parent = path.join(root, 'work/compat-tests');
  await fs.mkdir(parent, {recursive: true});
  const base = await fs.mkdtemp(path.join(parent, 'fixture-'));
  t.after(async () => {
    const resolved = await fs.realpath(base);
    assert.equal(path.dirname(resolved).toLowerCase(), (await fs.realpath(parent)).toLowerCase());
    await fs.rm(resolved, {recursive: true, force: true});
  });
  await fs.mkdir(path.join(base, 'bundle'));
  await fs.writeFile(path.join(base, 'package.json'), JSON.stringify({name: '@google/gemini-cli', version, type: 'module'}));
  const file = path.join(base, 'bundle/chunk-fixture.js');
  await fs.writeFile(file, original);
  return {base, file};
}
function required(name) {
  assert.equal(typeof implementation[name], 'function', name + ' must be implemented');
  return implementation[name];
}

test('Compat_PatchesPristineBundle_PreservesRealConflictsAndFlagDetection', async t => {
  const f = await fixture(t);
  const repair = required('repairGemini');
  const first = await repair(f.base);
  assert.equal(first.status, 'repaired');
  const repaired = await fs.readFile(f.file, 'utf8');
  const alias = path.join(f.base, 'alias');
  const target = path.join(f.base, 'target');
  await fs.mkdir(target); await fs.symlink(target, alias, 'junction');
  const mod = await import(pathToFileURL(f.file).href);
  assert.equal(mod.probe({location: target}, {location: alias}).length, 0);
  assert.equal(mod.probe({location: target}, {location: f.base}).length, 1);
  assert.equal(mod.probe({location: 'missing-a'}, {location: 'missing-b'}).length, 1);
  assert.deepEqual(mod.findUntrustedFlags('--unsafe', {}), ['--unsafe']);
  assert.equal((await repair(f.base)).status, 'verified');
  assert.equal((await repair(f.base,{validateOnly:true})).status,'verified');
  assert.equal(await fs.readFile(f.file, 'utf8'), repaired);
  assert.equal((await repair(f.base, {rollback: true})).status, 'restored');
  assert.equal(await fs.readFile(f.file, 'utf8'), original);
});

test('Compat_RejectsUnknownStructureAndInvalidSyntax_BeforeAnyWrite', async t => {
  const f = await fixture(t);
  const repair = required('repairGemini');
  await assert.rejects(repair(f.base,{validateOnly:true}),/needed/i);
  assert.equal(await fs.readFile(f.file,'utf8'),original);
  await fs.writeFile(path.join(f.base, 'bundle/chunk-invalid.js'), original + '\ninvalid syntax !');
  await assert.rejects(repair(f.base), /syntax|check/i);
  assert.equal(await fs.readFile(f.file, 'utf8'), original);
  await fs.unlink(path.join(f.base, 'bundle/chunk-invalid.js'));
  await fs.writeFile(f.file, 'export const unrelated = true;');
  await assert.rejects(repair(f.base), /recognized|structure|skill/i);
});

test('Compat_RestoresEarlierChunks_WhenALaterWriteIsDenied', async t => {
  const f = await fixture(t);
  const repair = required('repairGemini');
  const blocked = path.join(f.base,'bundle/chunk-z-readonly.js');
  await fs.writeFile(blocked,original);
  await fs.chmod(blocked,0o444);
  try {
    await assert.rejects(repair(f.base));
    assert.equal(await fs.readFile(f.file,'utf8'),original);
    assert.equal(await fs.readFile(blocked,'utf8'),original);
  } finally {await fs.chmod(blocked,0o666);}
});

test('Compat_SkipsUnknownVersion_AndProtectsDriftedRollback', async t => {
  const f = await fixture(t, '9.9.9');
  const repair = required('repairGemini');
  assert.equal((await repair(f.base)).status, 'unsupported');
  assert.equal(await fs.readFile(f.file, 'utf8'), original);
  await fs.writeFile(path.join(f.base, 'package.json'), JSON.stringify({name: '@google/gemini-cli', version: '0.64.0', type: 'module'}));
  await repair(f.base);
  await fs.appendFile(f.file, '\n// subsequent edit\n');
  await assert.rejects(repair(f.base, {rollback: true}), /changed|drift/i);
});

test('Compat_RestoresKnownEarlyReturn_WithoutRemovingNormalFlagChecks', () => {
  const transform = required('transformGeminiChunk');
  const bypass = original.replace('function findUntrustedFlags(command, untrustedContext) {', 'function findUntrustedFlags(command, untrustedContext) {\n  return [];');
  const result = transform(bypass);
  assert(!result.content.includes('untrustedContext) {\n  return [];'));
  assert(result.content.includes("return command.includes('--unsafe')"));
  assert.equal(transform(result.content).content, result.content);
});
