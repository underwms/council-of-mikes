import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import * as memory from '../council-memoryforge.mjs';
import * as tasks from '../council-task-context.mjs';
import {executeCommand} from '../council-codex.mjs';
import {buildHooks} from '../council-codex-lib.mjs';

async function fixture(t) {
  const parent=path.resolve(import.meta.dirname,'../../work/worker-startup-tests');
  await fs.mkdir(parent,{recursive:true});
  const homeDir=await fs.mkdtemp(path.join(parent,'fixture-'));
  t.after(async()=>{assert.equal(path.dirname(homeDir),parent);await fs.rm(homeDir,{recursive:true,force:true});});
  const o={homeDir,username:'test',workspaceRoot:path.join(homeDir,'workspace'),actor:'codex',chat:'parent-chat',now:'2026-11-17T15:00:00Z'};
  o.cwd=o.workspaceRoot;
  const root=memory.memoryRoot(homeDir,'test');
  await fs.mkdir(path.join(root,'knowledge'),{recursive:true});
  await fs.mkdir(o.workspaceRoot,{recursive:true});
  await fs.writeFile(path.join(root,'preferences.md'),'STABLE_PREFERENCES');
  await fs.writeFile(path.join(root,'knowledge/CONTEXT.md'),'STABLE_KNOWLEDGE_INDEX');
  for(const name of ['current_state.md','active_handoff.md','active_session_backlog.md']) await fs.writeFile(path.join(root,name),'UNRELATED_LEGACY_SENTINEL');
  return {...o,root};
}
function stableOnly(text) {
  assert.match(text,/STABLE_PREFERENCES/);
  assert.match(text,/STABLE_KNOWLEDGE_INDEX/);
  assert.match(text.split(/\r?\n/).filter(line=>!line.includes('Knowledge index:')).join('\n'),/worker/i);
  assert.doesNotMatch(text,/PRIVATE_TASK_SENTINEL|PRIVATE_TITLE_SENTINEL|UNRELATED_LEGACY_SENTINEL|Start fresh|Selected task metadata|Saved task state|Task catalogue unavailable|Explicit selected namespace|maintenance assigned to this chat/);
}
async function bindParent(o) {
  await tasks.saveTask(o,{id:'parent-task',title:'PRIVATE_TITLE_SENTINEL',summary:'private summary',state:'PRIVATE_TASK_SENTINEL'});
  await tasks.selectTask(o,'parent-task');
}

test('worker startup ignores selected parent state and leaves catalogue unchanged',async t=>{
  const o=await fixture(t);await bindParent(o);
  const file=path.join(o.root,'task-context.json'),before=await fs.readFile(file);
  stableOnly(await memory.readStartupContext({...o,startupMode:'worker'}));
  assert.deepEqual(await fs.readFile(file),before);
});

test('worker startup skips corrupt catalogue and configured daily work',async t=>{
  const o=await fixture(t),file=path.join(o.root,'task-context.json');
  await fs.writeFile(file,'not JSON');
  const store=path.join(o.workspaceRoot,'order-management/.memory/maintenance');
  await fs.mkdir(store,{recursive:true});await fs.mkdir(path.join(o.workspaceRoot,'docs'));
  await fs.writeFile(path.join(o.workspaceRoot,'docs/a.md'),'synthetic daily document');
  await fs.writeFile(path.join(store,'config.json'),JSON.stringify({schema_version:1,time_zone:'America/New_York',documents:['docs/a.md']}));
  stableOnly(await memory.readStartupContext({...o,startupMode:'worker'}));
  assert.deepEqual(await fs.readdir(store),['config.json']);
  assert.equal(await fs.readFile(file,'utf8'),'not JSON');
});

test('worker startup handles missing catalogue and absent native identities without creating state',async t=>{
  const o=await fixture(t);delete o.chat;
  stableOnly(await memory.readStartupContext({...o,startupMode:'worker'}));
  await assert.rejects(fs.stat(path.join(o.root,'task-context.json')),{code:'ENOENT'});
  const output=await memory.handleHook({hook_event_name:'SubagentStart'},{...o});
  assert.ok(output.hookSpecificOutput,'SubagentStart must return stable worker context');assert.equal(output.hookSpecificOutput.hookEventName,'SubagentStart');stableOnly(output.hookSpecificOutput.additionalContext);
});

test('startup rejects unknown mode and conflicting worker namespace or task selectors',async t=>{
  const o=await fixture(t);
  await assert.rejects(memory.readStartupContext({...o,startupMode:'unknown'}),/startup.*mode|mode.*startup/i);
  for(const conflict of [{memoryScope:'workspace-session',session:'selected'},{session:'selected'},{project:'selected'},{task:'selected'}]) {
    await assert.rejects(memory.readStartupContext({...o,startupMode:'worker',...conflict}),/worker|startup/i);
  }
  stableOnly(await memory.readStartupContext({...o,startupMode:'worker',memoryScope:'legacy-shared'}));
});

test('CLI exposes worker onboard fallback and rejects worker flag on nonstartup commands',async t=>{
  const o=await fixture(t),base=['--home',o.homeDir,'--workspace',o.workspaceRoot,'--username','test'];
  const result=await executeCommand(['onboard',...base,'--startup-mode','worker']);
  assert.equal(result.exitCode,0);stableOnly(result.output);
  const hooked=await executeCommand(['hook',...base,'--startup-mode','worker'],{input:JSON.stringify({hook_event_name:'SessionStart',session_id:'parent-chat',cwd:o.workspaceRoot})});
  const context=JSON.parse(hooked.output);assert.equal(context.hookSpecificOutput.hookEventName,'SessionStart');stableOnly(context.hookSpecificOutput.additionalContext);
  await assert.rejects(executeCommand(['hook',...base,'--startup-mode','worker'],{input:'{}'}),/event|worker|startup/i);
  for(const command of [['tasks','list'],['validate']]) await assert.rejects(executeCommand([...command,...base,'--startup-mode','worker'],{input:'{}'}),/startup.*mode|startup-mode/i);
});

test('Codex SubagentStart is event-correct and cannot overwrite parent receipt or bind child',async t=>{
  const o=await fixture(t);await bindParent(o);
  await memory.handleHook({hook_event_name:'SessionStart',session_id:o.chat,cwd:o.workspaceRoot,source:'startup'},o);
  const receipt=await tasks.receiptPath(o),beforeReceipt=await fs.readFile(receipt),file=path.join(o.root,'task-context.json'),beforeCatalogue=await fs.readFile(file);
  const output=await memory.handleHook({hook_event_name:'SubagentStart',session_id:o.chat,agent_id:'child-agent',cwd:o.workspaceRoot},o);
  assert.ok(output.hookSpecificOutput,'SubagentStart must return stable worker context');assert.equal(output.hookSpecificOutput.hookEventName,'SubagentStart');stableOnly(output.hookSpecificOutput.additionalContext);
  assert.deepEqual(await fs.readFile(receipt),beforeReceipt);assert.deepEqual(await fs.readFile(file),beforeCatalogue);
  assert.equal(await tasks.getBinding({...o,chat:'child-agent'}),null);
});

test('SubagentStart bypasses binding lookup before workspace resolution and excludes Gemini qualification',async t=>{
  const o=await fixture(t);await fs.writeFile(path.join(o.root,'task-context.json'),'not JSON');
  const payload={hook_event_name:'SubagentStart',session_id:o.chat,agent_id:'child-agent',cwd:path.join(o.workspaceRoot,'missing')};
  const output=await memory.handleHook(payload,o);
  assert.ok(output.hookSpecificOutput,'SubagentStart must return stable worker context');assert.equal(output.hookSpecificOutput.hookEventName,'SubagentStart');stableOnly(output.hookSpecificOutput.additionalContext);
  assert.deepEqual(await memory.handleHook(payload,{...o,actor:'gemini'}),{});
});

test('Codex installer registers worker startup',async t=>{
  const o=await fixture(t);
  const built=buildHooks({...o,nodePath:process.execPath,councilRoot:path.join(o.homeDir,'.council')});
  assert.ok(built.hooks.SubagentStart,'Codex must register SubagentStart');
  assert.ok(built.hooks.SubagentStart.some(group=>group.hooks.some(h=>/council-codex\.mjs/.test(h.command))));
});

test('default user chat startup retains selected state and unbound task menu',async t=>{
  const o=await fixture(t);await bindParent(o);
  assert.match(await memory.readStartupContext(o),/PRIVATE_TASK_SENTINEL/);
  assert.match(await memory.readStartupContext({...o,chat:'other-chat'}),/Start fresh/);
});

test('explicit worker SessionStart adds worker context without parent receipt writes',async t=>{
  const o=await fixture(t);await bindParent(o);
  await memory.handleHook({hook_event_name:'SessionStart',session_id:o.chat,cwd:o.workspaceRoot,source:'startup'},o);
  const receipt=await tasks.receiptPath(o),before=await fs.readFile(receipt);
  const output=await memory.handleHook({hook_event_name:'SessionStart',session_id:o.chat,cwd:o.workspaceRoot,source:'startup'},{...o,startupMode:'worker'});
  assert.ok(output.hookSpecificOutput);assert.equal(output.hookSpecificOutput.hookEventName,'SessionStart');stableOnly(output.hookSpecificOutput.additionalContext);
  assert.deepEqual(await fs.readFile(receipt),before);
});

test('explicit worker Stop skips corrupt binding storage and lifecycle logging',async t=>{
  const o=await fixture(t),file=path.join(o.root,'task-context.json');await fs.writeFile(file,'not JSON');
  const before=await fs.readdir(o.root);
  const output=await memory.handleHook({hook_event_name:'Stop',session_id:o.chat,turn_id:'turn-one',cwd:o.workspaceRoot},{...o,startupMode:'worker'});
  assert.deepEqual(output,{});assert.deepEqual(await fs.readdir(o.root),before);assert.equal(await fs.readFile(file,'utf8'),'not JSON');
});

test('worker startup reports missing stable files without task-menu fallback',async t=>{
  const o=await fixture(t);await fs.unlink(path.join(o.root,'preferences.md'));await fs.unlink(path.join(o.root,'knowledge/CONTEXT.md'));
  const text=await memory.readStartupContext({...o,startupMode:'worker'});
  assert.match(text,/No saved preferences/);assert.match(text,/Index unavailable/);assert.match(text,/worker/i);
  assert.doesNotMatch(text,/Start fresh|UNRELATED_LEGACY_SENTINEL|Task catalogue unavailable/);
});

test('SubagentStart defaults to Codex output when actor is absent',async t=>{
  const o=await fixture(t);delete o.actor;
  const output=await memory.handleHook({hook_event_name:'SubagentStart',session_id:o.chat,cwd:o.workspaceRoot},o);
  assert.equal(output.hookSpecificOutput.hookEventName,'SubagentStart');stableOnly(output.hookSpecificOutput.additionalContext);
});

test('explicit worker Gemini SessionStart uses Gemini output shape',async t=>{
  const o=await fixture(t);
  const output=await memory.handleHook({hook_event_name:'SessionStart',session_id:o.chat,cwd:o.workspaceRoot},{...o,actor:'gemini',startupMode:'worker'});
  assert.equal(Object.hasOwn(output.hookSpecificOutput,'hookEventName'),false);stableOnly(output.hookSpecificOutput.additionalContext);
});

test('explicit user startup mode preserves selected task state',async t=>{
  const o=await fixture(t);await bindParent(o);
  const text=await memory.readStartupContext({...o,startupMode:'user'});
  assert.match(text,/PRIVATE_TASK_SENTINEL/);assert.match(text,/Selected task metadata/);
});
