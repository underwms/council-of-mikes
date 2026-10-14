import assert from 'node:assert/strict';
import test from 'node:test';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {verifySourceLock} from '../council-source.mjs';
const execute = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

test('Distribution_InstallsReinstallsAndValidates_NativeOnlyUnderAnotherProfile', async t => {
  const manifest = JSON.parse(await fs.readFile(path.join(root,'manifest.json'),'utf8'));
  const artifact = manifest.distribution ? root : path.join(JSON.parse(await fs.readFile(path.join(root,'installation.json'),'utf8')).workspaceRoot,'temp/the-council/.council');
  const parent = path.join(root,'work/distribution-tests'); await fs.mkdir(parent,{recursive:true});
  const base = await fs.mkdtemp(path.join(parent,'fixture-'));
  t.after(async () => {
    assert.equal(path.dirname(await fs.realpath(base)).toLowerCase(),(await fs.realpath(parent)).toLowerCase());
    await fs.rm(base,{recursive:true,force:true});
  });
  const home = path.join(base,'Developer Other Name'), workspace = path.join(base,'Development Space');
  await fs.mkdir(path.join(workspace,'service/.git'),{recursive:true});
  await fs.writeFile(path.join(workspace,'service/AGENTS.md'),'Keep developer instructions.\n');
  await fs.mkdir(path.join(home,'.codex'),{recursive:true});
  const original = 'model = "retain-model"\n[sandbox_workspace_write]\nnetwork_access = false\nwritable_roots = ["D:/Existing"]\n';
  await fs.writeFile(path.join(home,'.codex/config.toml'),original);
  await fs.mkdir(path.join(home,'.gemini/tmp/Developer Other Name/memory'),{recursive:true});
  await fs.writeFile(path.join(home,'.gemini/tmp/Developer Other Name/memory/active_handoff.md'),'PRIVATE SENTINEL');
  const args = ['-NoProfile','-NonInteractive','-File',path.join(artifact,'setup-council.ps1'),'-WorkspaceRoot',workspace,'-HomeRoot',home,'-NodePath',process.execPath,'-NativeOnly','-SkipGeminiOptimization'];
  await execute('powershell.exe',args,{timeout:60000});
  const installed = path.join(home,'.council');
  assert.equal((await verifySourceLock(installed)).status,'pass');
  const config = await fs.readFile(path.join(home,'.codex/config.toml'),'utf8');
  assert(config.includes('retain-model') && config.includes('network_access = false') && config.includes('D:/Existing'));
  assert(config.includes(JSON.stringify(installed).slice(1,-1)));
  assert(!config.includes(JSON.stringify(root)) && !config.includes('__COUNCIL_ROOT__'));
  assert.equal(await fs.readFile(path.join(workspace,'service/AGENTS.md'),'utf8'),'Keep developer instructions.\n');
  await assert.rejects(fs.stat(path.join(installed,'memory/active_handoff.md')),{code:'ENOENT'});
  await assert.rejects(fs.stat(path.join(installed,'runtime')),{code:'ENOENT'});
  let aliases = 0;
  for(const folder of ['.agents','.gemini','.claude']) for(const name of manifest.skills) {
    assert.equal((await fs.realpath(path.join(home,folder,'skills',name))).toLowerCase(),path.join(installed,'skills',name).toLowerCase()); aliases++;
  }
  assert.equal(aliases,72);
  const before = await fs.readFile(path.join(installed,'source-lock.json'),'utf8');
  await execute('powershell.exe',args,{timeout:60000});
  assert.equal(await fs.readFile(path.join(home,'.codex/config.toml'),'utf8'),config);
  assert.equal(await fs.readFile(path.join(installed,'source-lock.json'),'utf8'),before);
  await execute('powershell.exe',[...args,'-ValidateOnly'],{timeout:60000});
  const report = JSON.parse((await execute(process.execPath,[path.join(installed,'scripts/council-codex.mjs'),'validate'],{timeout:30000})).stdout);
  assert.equal(report.placement.status,'pass'); assert.equal(report.lifecycle.status,'configured');
  assert.equal(report.ready,false);
});
