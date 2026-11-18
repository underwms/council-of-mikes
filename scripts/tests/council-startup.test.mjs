import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import * as tasks from '../council-task-context.mjs';
import * as memory from '../council-memoryforge.mjs';
import {executeCommand} from '../council-codex.mjs';

async function fixture(t) {
  const parent = path.resolve(import.meta.dirname, '../../work/startup-tests');
  await fs.mkdir(parent, {recursive:true});
  const homeDir = await fs.mkdtemp(path.join(parent,'fixture-'));
  const o = {homeDir,username:'test',workspaceRoot:path.join(homeDir,'workspace'),actor:'codex',chat:'chat-a',cwd:path.join(homeDir,'projectless')};
  await fs.mkdir(o.workspaceRoot,{recursive:true});
  await fs.mkdir(o.cwd,{recursive:true});
  const root = memory.memoryRoot(homeDir,'test');
  await fs.mkdir(path.join(root,'knowledge'),{recursive:true});
  await fs.writeFile(path.join(root,'preferences.md'),'STABLE_FAIR_POLICY');
  await fs.writeFile(path.join(root,'knowledge/CONTEXT.md'),'KNOWLEDGE_ROUTING');
  await fs.writeFile(path.join(root,'current_state.md'),'UNRELATED_LEGACY_TASK');
  await fs.writeFile(path.join(root,'active_handoff.md'),'UNRELATED_HANDOFF');
  await fs.writeFile(path.join(root,'active_session_backlog.md'),'UNRELATED_MILESTONE');
  t.after(async()=>{assert.equal(path.dirname(homeDir),parent);await fs.rm(homeDir,{recursive:true,force:true});});
  return {...o,root};
}
function record(id='shipping',extra={}) {return {id,title:'Shipping audit',summary:'Inspect rounding constraints',state:'PRIVATE_TASK_DETAILS',...extra};}

test('unbound startup loads stable context and routes without loading legacy task state',async t=>{
  const o=await fixture(t); assert.equal(typeof memory.readStartupContext,'function');
  const text=await memory.readStartupContext(o);
  assert(text.includes('STABLE_FAIR_POLICY')); assert(text.includes('KNOWLEDGE_ROUTING'));
  assert(!text.includes('UNRELATED_')); assert(text.includes('Start fresh'));
});
test('suggestions contain metadata only and project matches take priority',async t=>{
  const o=await fixture(t); const projectRoot=path.join(o.workspaceRoot,'shipping');
  await tasks.saveTask(o,record('shipping',{project_root:projectRoot,project_id:'project-one'}));
  await tasks.saveTask(o,record('orders',{title:'Orders audit',project_id:'project-two',state:'OTHER_TASK_SECRET'}));
  const project=await tasks.suggestTasks({...o,project:'project-one'});
  assert.deepEqual(project.tasks.map(x=>x.id),['shipping']); assert(!JSON.stringify(project).includes('PRIVATE_TASK_DETAILS'));
  const nested=await tasks.suggestTasks({...o,cwd:path.join(projectRoot,'src')});
  assert.deepEqual(nested.tasks.map(x=>x.id),['shipping']);
  assert.equal((await tasks.suggestTasks(o)).tasks.length,2);
  assert.equal((await tasks.suggestTasks({...o,project:'missing'})).tasks.length,0);
});
test('selection persists by client/chat and restores only selected task',async t=>{
  const o=await fixture(t);await tasks.saveTask(o,record());await tasks.selectTask(o,'shipping');
  const selected=await memory.readStartupContext(o);assert(selected.includes('PRIVATE_TASK_DETAILS'));assert(!selected.includes('UNRELATED_'));
  assert(!(await memory.readStartupContext({...o,chat:'chat-b'})).includes('PRIVATE_TASK_DETAILS'));
  assert(!(await memory.readStartupContext({...o,actor:'gemini'})).includes('PRIVATE_TASK_DETAILS'));
});
test('Start fresh is a persistent explicit binding and does not resume suggestions',async t=>{
  const o=await fixture(t);await tasks.saveTask(o,record());await tasks.selectTask(o,'shipping');await tasks.startFresh(o);
  const restored=await memory.readStartupContext(o);assert(!restored.includes('PRIVATE_TASK_DETAILS'));assert(!restored.includes('Shipping audit'));assert(restored.includes('fresh'));
});
test('paused selection and checkpoint preserve pause; explicit resume is required',async t=>{
  const o=await fixture(t);await tasks.saveTask(o,record());await tasks.selectTask(o,'shipping');
  await tasks.setTaskStatus(o,'shipping','paused',{reason:'User said pin it'});
  assert((await memory.readStartupContext(o)).includes('paused'));
  await tasks.saveTask(o,record('shipping',{summary:'Checkpointed while paused'}));
  assert.equal((await tasks.getSelectedTask(o)).status,'paused');
  await assert.rejects(tasks.setTaskStatus(o,'shipping','open'),/explicit.*resume/i);
  await tasks.setTaskStatus(o,'shipping','open',{resume:true});assert.equal((await tasks.getSelectedTask(o)).status,'open');
});
test('explicit namespace overrides binding and excludes other task state',async t=>{
  const o=await fixture(t);await tasks.saveTask(o,record());await tasks.selectTask(o,'shipping');
  const selected={...o,memoryScope:'workspace-session',session:'chosen'};
  const dir=memory.memoryRoot(o.homeDir,'test',selected);await fs.mkdir(dir,{recursive:true});await fs.writeFile(path.join(dir,'current_state.md'),'EXPLICIT_TASK');
  const text=await memory.readStartupContext(selected);assert(text.includes('EXPLICIT_TASK'));assert(!text.includes('PRIVATE_TASK_DETAILS'));assert(!text.includes('UNRELATED_'));
});
test('unknown tasks and invalid identities cannot bind or overwrite other records',async t=>{
  const o=await fixture(t);await assert.rejects(tasks.selectTask(o,'missing'),/Unknown task/);
  await assert.rejects(tasks.saveTask(o,record('../escape')),/Invalid task/);
  await assert.rejects(tasks.selectTask({...o,chat:''},'shipping'),/chat identity/i);
  await assert.rejects(tasks.saveTask(o,record('oversized',{state:'x'.repeat(5001)})),/state/i);
  await assert.rejects(tasks.saveTask(o,record('status',{status:'paused'})),/status/i);
});
test('concurrent writes retain independent tasks and corrupted catalogue fails closed',async t=>{
  const o=await fixture(t);await Promise.all(Array.from({length:8},(_,i)=>tasks.saveTask(o,record('task-'+i))));
  assert.equal((await tasks.suggestTasks({...o,limit:10})).tasks.length,8);
  await fs.writeFile(path.join(o.root,'task-context.json'),'{broken');
  await assert.rejects(tasks.saveTask(o,record('new')),/catalogue/i);
  const text=await memory.readStartupContext(o);assert(text.includes('unavailable'));assert(!text.includes('UNRELATED_'));
});
test('startup runs outside workspace while lifecycle logging stays inside',async t=>{
  const o=await fixture(t);const payload={hook_event_name:'SessionStart',session_id:'chat-a',source:'startup',cwd:o.cwd};
  const output=await memory.handleHook(payload,o);assert(output.hookSpecificOutput.additionalContext.includes('KNOWLEDGE_ROUTING'));
  await memory.handleHook({...payload,hook_event_name:'Stop',turn_id:'one'},o);
  assert.equal(await fs.readFile(path.join(o.root,'active_session_backlog.md'),'utf8'),'UNRELATED_MILESTONE');
  const receipt=JSON.parse(await fs.readFile(await tasks.receiptPath(o),'utf8'));assert.equal(receipt.event,'SessionStart');assert.equal(receipt.source,'startup');assert(!JSON.stringify(receipt).includes('UNRELATED_'));
});
test('task-bound lifecycle records go to the task namespace, not legacy state',async t=>{
  const o=await fixture(t);await tasks.saveTask(o,record());await tasks.selectTask(o,'shipping');
  await memory.handleHook({hook_event_name:'Stop',session_id:'chat-a',turn_id:'turn',cwd:o.workspaceRoot},o);
  const log=await fs.readFile(path.join(o.root,'tasks/shipping/active_session_backlog.md'),'utf8');assert(log.includes('Agent turn ended'));
  assert.equal(await fs.readFile(path.join(o.root,'active_session_backlog.md'),'utf8'),'UNRELATED_MILESTONE');
});
test('default onboard and task CLI preserve explicit selection and status semantics',async t=>{
  const o=await fixture(t);const flags=['--home',o.homeDir,'--workspace',o.workspaceRoot,'--username','test','--chat','chat-a'];
  const recordPath=path.join(o.homeDir,'record.json');await fs.writeFile(recordPath,JSON.stringify(record()));
  assert(!(await executeCommand(['onboard',...flags])).output.includes('UNRELATED_'));
  await executeCommand(['tasks','save',...flags,'--record',recordPath]);
  await executeCommand(['tasks','select',...flags,'--task','shipping']);
  assert((await executeCommand(['onboard',...flags])).output.includes('PRIVATE_TASK_DETAILS'));
  await executeCommand(['tasks','status',...flags,'--task','shipping','--status','paused','--reason','User asked to park it']);
  await assert.rejects(executeCommand(['tasks','status',...flags,'--task','shipping','--status','open']),/explicit.*resume/i);
  await executeCommand(['tasks','status',...flags,'--task','shipping','--status','open','--resume','true']);
  await executeCommand(['tasks','fresh',...flags]);assert(!(await executeCommand(['onboard',...flags])).output.includes('PRIVATE_TASK_DETAILS'));
});
test('startup remains bounded without splitting Unicode and invalid scope is rejected',async t=>{
  const o=await fixture(t);await fs.writeFile(path.join(o.root,'preferences.md'),'\u20ac'.repeat(1000));await fs.writeFile(path.join(o.root,'knowledge/CONTEXT.md'),'\u20ac'.repeat(3000));
  await tasks.saveTask(o,record('big',{state:'\u20ac'.repeat(1600)}));await tasks.selectTask(o,'big');
  const context=await memory.readStartupContext(o);assert(Buffer.byteLength(context,'utf8')<=12000);assert(!context.includes('\ufffd'));
  await assert.rejects(memory.readStartupContext({...o,memoryScope:'invalid'}),/memory scope/i);
});
test('completed tasks leave suggestions, history survives checkpoints, and clients remain isolated',async t=>{
  const o=await fixture(t);await tasks.saveTask(o,record());await tasks.selectTask(o,'shipping');
  await tasks.setTaskStatus(o,'shipping','blocked',{reason:'Awaiting source access'});
  await tasks.setTaskStatus(o,'shipping','completed');assert.equal((await tasks.suggestTasks(o)).tasks.length,0);
  assert((await memory.readStartupContext(o)).includes('COMPLETED'));
  await tasks.saveTask(o,record('shipping',{state:'Updated historical summary'}));
  assert.equal((await tasks.getSelectedTask(o)).status,'completed');
  await tasks.setTaskStatus(o,'shipping','open',{resume:true});
  const catalogue=await tasks.readCatalogue(o);assert.equal(catalogue.tasks.shipping.history.length,3);
  await assert.rejects(tasks.selectTask({...o,actor:'unknown'},'shipping'),/client/);
  assert(!(await memory.readStartupContext({...o,chat:undefined})).includes('Updated historical summary'));
});
test('fresh and explicit-namespace lifecycle logs preserve isolation',async t=>{
  const o=await fixture(t);await tasks.startFresh(o);
  await memory.handleHook({hook_event_name:'Stop',session_id:'chat-a',turn_id:'fresh',cwd:o.workspaceRoot},o);
  assert.equal(await fs.readFile(path.join(o.root,'active_session_backlog.md'),'utf8'),'UNRELATED_MILESTONE');
  const explicit={...o,memoryScope:'workspace-session',session:'scope-a',actor:'gemini'};
  const output=await memory.handleHook({hook_event_name:'SessionStart',session_id:'chat-a',source:'resume',cwd:o.cwd},explicit);
  assert(output.hookSpecificOutput.additionalContext.includes('Explicit selected namespace'));
  await memory.handleHook({hook_event_name:'AfterAgent',session_id:'chat-a',timestamp:'one',cwd:o.workspaceRoot},explicit);
  assert((await fs.readFile(path.join(memory.memoryRoot(o.homeDir,'test',explicit),'active_session_backlog.md'),'utf8')).includes('Agent turn ended'));
});
test('catalogue bounds and schema failures never replace saved history or leak default state',async t=>{
  const o=await fixture(t);await tasks.saveTask(o,record());const p=path.join(o.root,'task-context.json'),saved=await fs.readFile(p);
  for(const invalid of [{schema_version:9,tasks:{},bindings:{}},{schema_version:1,tasks:{bad:{}},bindings:{}},{schema_version:1,tasks:{},bindings:{invalid:{}}}]) {
    await fs.writeFile(p,JSON.stringify(invalid));await assert.rejects(tasks.readCatalogue(o),/catalogue/);
  }
  await fs.writeFile(p,Buffer.alloc(2*1024*1024+1,32));await assert.rejects(tasks.saveTask(o,record()),/catalogue/);
  assert(!(await memory.readStartupContext(o)).includes('UNRELATED_'));await fs.writeFile(p,saved);
  await assert.rejects(tasks.saveTask(o,record('invalid',{project_root:'relative'})),/project root/);
  await assert.rejects(tasks.setTaskStatus(o,'shipping','paused'),/reason/);
  await assert.rejects(tasks.setTaskStatus(o,'missing','completed'),/Unknown task/);
  await assert.rejects(tasks.setTaskStatus(o,'shipping','invalid'),/status/);
  await assert.rejects(tasks.suggestTasks({...o,limit:11}),/limit/);
  assert.deepEqual(await fs.readFile(p),saved);
});
test('native startup supplies its own opaque identity for a later selection command',async t=>{
  const o=await fixture(t);const output=await memory.handleHook({hook_event_name:'SessionStart',session_id:'native-gemini-chat',source:'startup',cwd:o.cwd},{...o,actor:'gemini'});
  assert(output.hookSpecificOutput.additionalContext.includes('native-gemini-chat'));
  assert(output.hookSpecificOutput.additionalContext.includes('"actor":"gemini"'));
});
test('invalid task record JSON is rejected without disclosing its contents',async t=>{
  const o=await fixture(t);const recordPath=path.join(o.homeDir,'bad-record.json');await fs.writeFile(recordPath,'{"PRIVATE_RECORD_MARKER": invalid}');
  await assert.rejects(executeCommand(['tasks','save','--home',o.homeDir,'--workspace',o.workspaceRoot,'--record',recordPath]),e=>!e.message.includes('PRIVATE_RECORD_MARKER')&&/task record/i.test(e.message));
});
