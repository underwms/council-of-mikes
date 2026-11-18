import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import * as daily from '../council-daily.mjs';
import {readStartupContext} from '../council-memoryforge.mjs';
import {executeCommand} from '../council-codex.mjs';

async function fixture(t) {
  const parent=path.resolve(import.meta.dirname,'../../work/daily-claim-tests');
  await fs.mkdir(parent,{recursive:true});
  const workspaceRoot=await fs.mkdtemp(path.join(parent,'case-'));
  t.after(async()=>{assert.equal(path.dirname(workspaceRoot),parent);await fs.rm(workspaceRoot,{recursive:true,force:true});});
  const store=path.join(workspaceRoot,'order-management/.memory/maintenance');
  await fs.mkdir(store,{recursive:true});await fs.mkdir(path.join(workspaceRoot,'docs'));
  await fs.writeFile(path.join(workspaceRoot,'docs/a.md'),'source');
  await fs.writeFile(path.join(store,'config.json'),JSON.stringify({schema_version:1,time_zone:'America/New_York',documents:['docs/a.md']}));
  return {workspaceRoot,store,homeDir:path.join(workspaceRoot,'home'),actor:'codex',chat:'claim-a',cwd:parent,now:'2026-11-18T15:00:00Z'};
}
const runFile=o=>path.join(o.store,'runs/2026-11-18.json');

test('Codex startup offers work without claiming from a projectless hook',async t=>{
  const o=await fixture(t),context=await readStartupContext(o);
  assert.match(context,/maintenance available/);assert.match(context,/daily claim/);
  await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
  assert.equal(await daily.dailyStartup({...o,chat:undefined}),'');
});
test('agent-side denied write leaves day unclaimed for a capable chat',async t=>{
  const o=await fixture(t),open=fs.open;
  fs.open=async(file,...args)=>{if(String(file).includes('.memoryforge-access-'))throw Object.assign(Error('fixture denial'),{code:'EACCES'});return open(file,...args);};
  let result;try{result=await daily.claimDaily(o,{run_id:'2026-11-18'});}finally{fs.open=open;}
  assert.equal(result.status,'unavailable');assert.equal(result.reason,'write-access-unavailable');
  await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
  const accepted=await daily.claimDaily({...o,chat:'capable-chat'},{run_id:'2026-11-18'});
  assert.equal(accepted.status,'claimed');assert.equal(accepted.items.length,1);
});
test('registered document write denial also leaves day unclaimed and removes probes',async t=>{
  const o=await fixture(t),open=fs.open;
  fs.open=async(file,...args)=>{if(path.dirname(String(file))===path.join(o.workspaceRoot,'docs')&&String(file).includes('.memoryforge-access-'))throw Object.assign(Error('fixture denial'),{code:'EPERM'});return open(file,...args);};
  let result;try{result=await daily.claimDaily(o,{run_id:'2026-11-18'});}finally{fs.open=open;}
  assert.equal(result.status,'unavailable');await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
  assert(!(await fs.readdir(o.store)).some(p=>p.startsWith('.memoryforge-access-')));
});
test('claim refuses another date and never reopens an existing failed run',async t=>{
  const o=await fixture(t);
  await assert.rejects(daily.claimDaily(o,{run_id:'2026-11-17'}),/same-day/);
  await fs.mkdir(path.dirname(runFile(o)),{recursive:true});const before='{"status":"failed","reason":"completion-not-recorded"}\n';
  await fs.writeFile(runFile(o),before);
  assert.equal((await daily.claimDaily(o,{run_id:'2026-11-18'})).status,'already-attempted');
  assert.equal(await fs.readFile(runFile(o),'utf8'),before);assert.equal(await daily.dailyStartup(o),'');
});
test('present read-only document leaves day unclaimed',{skip:process.platform!=='win32'},async t=>{
  const o=await fixture(t),target=path.join(o.workspaceRoot,'docs/a.md');
  await fs.chmod(target,0o444);
  try{
    const result=await daily.claimDaily(o,{run_id:'2026-11-18'});
    assert.equal(result.status,'unavailable');await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
    assert.equal(await fs.readFile(target,'utf8'),'source');
  }finally{await fs.chmod(target,0o666);}
});
test('present checkpoint write denial leaves day unclaimed',async t=>{
  const o=await fixture(t),target=path.join(o.store,'checkpoints.json'),open=fs.open;
  const before=JSON.stringify({schema_version:1,documents:{}});await fs.writeFile(target,before);
  fs.open=async(file,...args)=>{if(String(file)===target&&args[0]==='r+')throw Object.assign(Error('fixture file ACL'),{code:'EACCES'});return open(file,...args);};
  let result;try{result=await daily.claimDaily(o,{run_id:'2026-11-18'});}finally{fs.open=open;}
  assert.equal(result.status,'unavailable');await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
  assert.equal(await fs.readFile(target,'utf8'),before);
});
test('Git object directory denial leaves mainline day unclaimed',async t=>{
  const o=await fixture(t),repo=path.join(o.workspaceRoot,'repo'),open=fs.open;
  await fs.mkdir(repo);await promisify(execFile)('git',['init',repo],{windowsHide:true});
  await fs.writeFile(path.join(o.store,'config.json'),JSON.stringify({schema_version:1,time_zone:'America/New_York',documents:['docs/a.md'],mainline:{enabled:true,repositories:[{path:'repo'}]}}));
  fs.open=async(file,...args)=>{if(path.dirname(String(file))===path.join(repo,'.git/objects')&&String(file).includes('.memoryforge-access-'))throw Object.assign(Error('fixture Git ACL'),{code:'EACCES'});return open(file,...args);};
  let result;try{result=await daily.claimDaily(o,{run_id:'2026-11-18'});}finally{fs.open=open;}
  assert.equal(result.status,'unavailable');await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
});
test('concurrent capable commands have only one daily owner',async t=>{
  const o=await fixture(t),input={run_id:'2026-11-18'};
  const results=await Promise.all([daily.claimDaily(o,input),daily.claimDaily({...o,chat:'claim-b'},input)]);
  assert.equal(results.filter(r=>r.status==='claimed').length,1);
  assert.equal(results.filter(r=>r.status==='already-attempted').length,1);
});
test('successful mainline preflight checks Git destinations before claiming',async t=>{
  const o=await fixture(t),repo=path.join(o.workspaceRoot,'repo');
  await fs.mkdir(repo);await promisify(execFile)('git',['init',repo],{windowsHide:true});
  await fs.writeFile(path.join(o.store,'config.json'),JSON.stringify({schema_version:1,time_zone:'America/New_York',documents:['docs/a.md'],mainline:{enabled:true,repositories:[{name:'repo',path:'repo',branch:'main',baseline_commit:'0'.repeat(40),documents:['docs/a.md']}]}}));
  const result=await daily.claimDaily(o,{run_id:'2026-11-18'});
  assert.equal(result.status,'claimed');assert.equal(result.mainline_pending,true);
  assert(!(await fs.readdir(path.join(repo,'.git/objects'))).some(p=>p.startsWith('.memoryforge-access-')));
});
test('invalid mainline registry cannot claim a day',async t=>{
  const o=await fixture(t);
  await fs.writeFile(path.join(o.store,'config.json'),JSON.stringify({schema_version:1,time_zone:'America/New_York',documents:['docs/a.md'],mainline:{enabled:true,repositories:null}}));
  assert.equal((await daily.claimDaily(o,{run_id:'2026-11-18'})).status,'unavailable');
  await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
});
test('unreadable daily receipt path never creates a claim',async t=>{
  const o=await fixture(t),lstat=fs.lstat;
  fs.lstat=async(file,...args)=>{if(String(file)===runFile(o))throw Object.assign(Error('fixture read ACL'),{code:'EACCES'});return lstat(file,...args);};
  try{await assert.rejects(daily.claimDaily(o,{run_id:'2026-11-18'}),{code:'EACCES'});}finally{fs.lstat=lstat;}
  await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
});
test('a file replacing an output directory prevents a claim',async t=>{
  const o=await fixture(t);await fs.writeFile(path.join(o.store,'stages'),'not a directory');
  assert.equal((await daily.claimDaily(o,{run_id:'2026-11-18'})).status,'unavailable');
  await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
});
test('directory access denial prevents a claim',async t=>{
  const o=await fixture(t),stat=fs.stat;
  fs.stat=async(file,...args)=>{if(String(file)===o.store)throw Object.assign(Error('fixture directory ACL'),{code:'EACCES'});return stat(file,...args);};
  let result;try{result=await daily.claimDaily(o,{run_id:'2026-11-18'});}finally{fs.stat=stat;}
  assert.equal(result.status,'unavailable');await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
});
test('missing filesystem root terminates preflight without claiming',async t=>{
  const o=await fixture(t),stat=fs.stat;
  fs.stat=async()=>{throw Object.assign(Error('fixture volume unavailable'),{code:'ENOENT'});};
  let result;try{result=await daily.claimDaily(o,{run_id:'2026-11-18'});}finally{fs.stat=stat;}
  assert.equal(result.status,'unavailable');await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
});
test('a date rollover during preflight cannot claim the next day',async t=>{
  const o=await fixture(t);let reads=0;
  Object.defineProperty(o,'now',{get(){return ++reads>3?'2026-11-19T15:00:00Z':'2026-11-18T15:00:00Z';}});
  await assert.rejects(daily.claimDaily(o,{run_id:'2026-11-18'}),/same-day/);
  await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
});
test('missing input cannot claim; omitted actor defaults to Codex opportunity',async t=>{
  const o=await fixture(t);await assert.rejects(daily.claimDaily(o,undefined),/same-day/);
  assert.match(await daily.dailyStartup({...o,actor:undefined}),/maintenance available/);
  await assert.rejects(fs.stat(runFile(o)),{code:'ENOENT'});
});
test('daily claim is exposed through the normal CLI record route',async t=>{
  const o=await fixture(t),record=path.join(o.workspaceRoot,'request.json');
  await fs.writeFile(record,JSON.stringify({run_id:new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}));
  const result=await executeCommand(['daily','claim','--workspace',o.workspaceRoot,'--home',o.homeDir,'--chat',o.chat,'--record',record]);
  assert.equal(result.exitCode,0);assert.equal(JSON.parse(result.output).status,'claimed');
});
