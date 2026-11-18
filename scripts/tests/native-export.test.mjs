import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const execute=promisify(execFile);
const root=path.resolve(import.meta.dirname,'../..');

test('native export installs by default and validates without an author workspace script',async t=>{
 const parent=path.join(root,'work/native-export-tests');await fs.mkdir(parent,{recursive:true});
 const base=await fs.mkdtemp(path.join(parent,'fixture-'));
 t.after(async()=>{assert.equal(path.dirname(base),parent);await fs.rm(base,{recursive:true,force:true});});
 const home=path.join(base,'Developer Profile'),workspace=path.join(base,'Developer Workspace');
 await fs.mkdir(workspace,{recursive:true});await fs.mkdir(home,{recursive:true});
 const args=['-NoProfile','-NonInteractive','-File',path.join(root,'setup-council.ps1'),'-WorkspaceRoot',workspace,'-HomeRoot',home,'-NodePath',process.execPath];
 await execute('powershell.exe',args,{timeout:60000});
 const installed=path.join(home,'.council');
 for(const excluded of ['council','visualizer','runtime','council.ps1','scripts/install-engine-runtime.ps1'])await assert.rejects(fs.stat(path.join(installed,excluded)),{code:'ENOENT'});
 await execute('powershell.exe',[...args,'-ValidateOnly'],{timeout:60000});
 await execute('powershell.exe',['-NoProfile','-NonInteractive','-File',path.join(installed,'scripts/validate-workspace.ps1'),'-WorkspaceRoot',workspace],{timeout:60000});
 await assert.rejects(fs.stat(path.join(workspace,'scripts/validate-workspace.ps1')),{code:'ENOENT'});
 const instructions=await fs.readFile(path.join(home,'.codex/AGENTS.md'),'utf8');
 assert(instructions.includes(installed));assert(!instructions.includes('__COUNCIL_ROOT__'));
 const fragment=await fs.readFile(path.join(installed,'adapters/gemini/settings-fragment.json'),'utf8');
 assert(!fragment.includes('__COUNCIL_ROOT__'));
  assert.deepEqual(JSON.parse(fragment).context.fileFiltering.customIgnoreFilePaths,[path.join(installed,'exclusions/global.ignore')]);
});
