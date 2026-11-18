import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {executeCommand} from '../council-codex.mjs';
import {installCouncil} from '../council-codex-lib.mjs';

const sha=s=>createHash('sha256').update(s).digest('hex');
async function fixture(t) {
  const parent=path.resolve(import.meta.dirname,'../../work/icm-tests');
  await fs.mkdir(parent,{recursive:true});
  const home=await fs.mkdtemp(path.join(parent,'case-'));
  const repo=path.join(home,'repo');await fs.mkdir(repo);
  const git=(...args)=>execFileSync('git',['-C',repo,...args],{encoding:'utf8'}).trim();
  git('init','-q');git('config','core.autocrlf','false');git('config','user.name','ICM Fixture');git('config','user.email','icm@example.invalid');
  const repository='https://bitbucket.example.invalid/acme/shipping.git';
  git('remote','add','origin',repository);
  await fs.writeFile(path.join(repo,'rule.txt'),'Original rule\n','utf8');
  git('add','rule.txt');git('commit','-qm','baseline');const base=git('rev-parse','HEAD');
  const content='Shipping eligibility uses the destination.\nUnicode: café\n';
  await fs.writeFile(path.join(repo,'rule.txt'),content,'utf8');
  git('commit','-qam','integrated change');const head=git('rev-parse','HEAD');
  const flags=['--home',home,'--workspace',repo,'--model','codex'];
  const call=async(action,record,extra=[])=>{
    const p=path.join(home,'input-'+Math.random().toString(16).slice(2)+'.json');
    if(record)await fs.writeFile(p,JSON.stringify(record),'utf8');
    const r=await executeCommand(['icm',action,...flags,...(record?['--record',p]:[]),...extra]);
    return JSON.parse(r.output);
  };
  const capture=(extra={})=>({event_id:'review-1',previous_event:null,task_id:'shipping-review',pr_url:'https://bitbucket.example.invalid/projects/ACME/repos/shipping/pull-requests/42',repository,base_sha:base,head_sha:head,sources:[{id:'story',origin:'Jira TEST-42 supplied by user',revision:'2026-11-13',excerpt:'Eligibility is based on destination.'}],candidates:[{id:'C1',claim:'Shipping eligibility depends on destination.',scope:'Shipping eligibility in this repository.',source_ids:['story']}],...extra});
  const reconcile=(extra={})=>({event_id:'sync-1',previous_event:'review-1',task_id:'shipping-review',pr_url:capture().pr_url,repository,review_event:'review-1',outcome:'merged',repo_path:repo,merge:{state:'merged',approval:'approved',sha:head,target_sha:head,evidence:{kind:'user-confirmed',origin:'User supplied Bitbucket merge outcome',revision:head,excerpt:'PR 42 approved and merged.'}},decisions:[{id:'C1',status:'confirmed',reason:'Integrated code implements the story.',evidence:[{path:'rule.txt',start_line:1,end_line:2,sha256:sha(content)}]}],architecture:{status:'no-impact',reason:'No boundaries, contracts or data ownership changed.'},...extra});
  t.after(async()=>{assert.equal(path.dirname(home),parent);await fs.rm(home,{recursive:true,force:true});});
  return {home,repo,git,base,head,content,capture,reconcile,call};
}

test('investigation hook captures candidates without promoting them and is idempotent',async t=>{
  const f=await fixture(t);const a=await f.call('investigate',f.capture());
  assert.equal(a.status,'awaiting-sync');assert.equal(a.candidates[0].status,'candidate');
  const first=await fs.readFile(a.record_path,'utf8');
  const b=await f.call('investigate',f.capture());assert.equal(b.duplicate,true);
  assert.equal(await fs.readFile(a.record_path,'utf8'),first);
  await assert.rejects(f.call('investigate',f.capture({head_sha:f.base})),/event.*conflict/i);
});

test('final-sync hook verifies local integration, publishes evidence and preserves review history',async t=>{
  const f=await fixture(t);await f.call('investigate',f.capture());
  const result=await f.call('reconcile',f.reconcile());assert.equal(result.status,'reconciled');
  const note=await fs.readFile(result.note_path,'utf8');
  assert.match(note,/confirmed/);assert.match(note,/café/);assert.match(note,new RegExp(f.head));
  const record=JSON.parse(await fs.readFile(result.record_path,'utf8'));assert.equal(record.events.length,2);
  assert.equal(record.events[0].input.sources[0].origin,'Jira TEST-42 supplied by user');
  const sources=JSON.parse(await fs.readFile(result.sources_path,'utf8'));
  assert.equal(sources.sources[0].revision,f.head);assert.match(sources.sources[0].excerpt,/destination/);
  await fs.unlink(result.note_path);
  const replay=await f.call('reconcile',f.reconcile());assert.equal(replay.duplicate,true);
  assert.equal(await fs.readFile(result.note_path,'utf8'),note);
});

test('new investigations require a current predecessor, preserve candidates and mark omitted claims needs-review',async t=>{
  const f=await fixture(t);await f.call('investigate',f.capture());
  const revised=f.capture({event_id:'review-2',previous_event:'review-1',head_sha:f.base,candidates:[],none_reason:'Prior claim needs reassessment.'});
  const result=await f.call('investigate',revised);assert.equal(result.candidates[0].status,'needs-review');
  await assert.rejects(f.call('reconcile',f.reconcile({previous_event:'review-2'})),/review.*stale/i);
  await assert.rejects(f.call('investigate',{...revised,event_id:'late-review',previous_event:'review-1'}),/predecessor/i);
});

test('sync cannot manufacture merge approval, change repository identity, or confirm without evidence',async t=>{
  const f=await fixture(t);await f.call('investigate',f.capture());
  await assert.rejects(f.call('reconcile',f.reconcile({merge:undefined})),/merge/i);
  const bad=f.reconcile();bad.merge.approval='unknown';await assert.rejects(f.call('reconcile',bad),/approval/i);
  await assert.rejects(f.call('reconcile',f.reconcile({repository:'another-repository'})),/repository/i);
  const noEvidence=f.reconcile();noEvidence.decisions[0].evidence=[];
  await assert.rejects(f.call('reconcile',noEvidence),/evidence/i);
  const noArchitecture=f.reconcile();delete noArchitecture.architecture;
  await assert.rejects(f.call('reconcile',noArchitecture),/architecture/i);
});

test('synced target, remote, evidence hash and candidate coverage must match',async t=>{
  const f=await fixture(t);await f.call('investigate',f.capture());
  const wrong=f.reconcile();wrong.merge.target_sha=f.base;await assert.rejects(f.call('reconcile',wrong),/target/i);
  const hash=f.reconcile();hash.decisions[0].evidence[0].sha256='0'.repeat(64);
  await assert.rejects(f.call('reconcile',hash),/hash/i);
  await assert.rejects(f.call('reconcile',f.reconcile({decisions:[]})),/candidate/i);
  f.git('remote','set-url','origin','https://bitbucket.example.invalid/acme/other.git');
  await assert.rejects(f.call('reconcile',f.reconcile()),/remote/i);
});

test('unresolved decisions stay pending and closure without merge never confirms proposals',async t=>{
  const f=await fixture(t);await f.call('investigate',f.capture());
  const pending=await f.call('reconcile',f.reconcile({decisions:[{id:'C1',status:'needs-review',reason:'Integration needs human interpretation.',evidence:[]}],architecture:{status:'pending',reason:'Documentation impact is unresolved.'}}));
  assert.equal(pending.status,'needs-review');
  const closedPr=f.capture({pr_url:f.capture().pr_url+'0'});await f.call('investigate',closedPr);
  const bad=f.reconcile({event_id:'closed',pr_url:closedPr.pr_url,outcome:'closed'});
  await assert.rejects(f.call('reconcile',bad),/closed/i);
  const closed=await f.call('reconcile',{...bad,merge:undefined,repo_path:undefined,decisions:[{id:'C1',status:'rejected',reason:'Closed without merge.',evidence:[]}],architecture:{status:'no-impact',reason:'No change integrated.'}});
  assert.equal(closed.status,'closed');assert.equal(closed.candidates[0].status,'rejected');
  await assert.rejects(f.call('reconcile',f.reconcile({event_id:'rewrite-as-closed',previous_event:'sync-1',outcome:'closed',merge:undefined,repo_path:undefined,decisions:[{id:'C1',status:'rejected',reason:'Conflicting closure assertion.',evidence:[]}]})),/merged.*closed/i);
});

test('squash-style integration is checked by actual content and later pending decisions can be resolved',async t=>{
  const f=await fixture(t);await f.call('investigate',f.capture({head_sha:f.base}));
  const pending=await f.call('reconcile',f.reconcile({decisions:[{id:'C1',status:'needs-review',reason:'Awaiting interpretation.',evidence:[]}]}));
  assert.equal(pending.status,'needs-review');
  const completed=await f.call('reconcile',f.reconcile({event_id:'sync-2',previous_event:'sync-1'}));
  assert.equal(completed.status,'reconciled');
  const differentMerge=f.reconcile({event_id:'different-merge',previous_event:'sync-2'});differentMerge.merge.sha=f.base;differentMerge.merge.evidence.revision=f.base;
  await assert.rejects(f.call('reconcile',differentMerge),/integration.*identity/i);
});

test('unsafe paths, wrong line ranges, missing PRs and unsupported actions fail without recording success',async t=>{
  const f=await fixture(t);
  await assert.rejects(f.call('reconcile',f.reconcile({previous_event:null})),/investigation/i);
  await assert.rejects(f.call('unknown'),/usage/i);
  await f.call('investigate',f.capture());
  for(const entry of [{path:'../outside'},{path:'C:/secrets'},{start_line:0},{end_line:999}]) {
    const r=f.reconcile();Object.assign(r.decisions[0].evidence[0],entry);
    await assert.rejects(f.call('reconcile',r),/path|line range/i);
  }
  const unmerged=f.reconcile();
  f.git('checkout','-q','--orphan','unmerged-fixture');f.git('rm','-q','--cached','rule.txt');
  await fs.writeFile(path.join(f.repo,'unrelated.txt'),'unrelated\n');f.git('add','unrelated.txt');f.git('commit','-qm','unrelated history');
  unmerged.merge.target_sha=f.git('rev-parse','HEAD');
  await assert.rejects(f.call('reconcile',unmerged),/verification/i);
});

test('installation carries the ICM dependency and the installed CLI starts independently',async t=>{
  const f=await fixture(t);const payload=path.join(f.home,'payload');
  await fs.mkdir(path.join(payload,'skills/example'),{recursive:true});await fs.mkdir(path.join(payload,'rules'));
  await fs.writeFile(path.join(payload,'manifest.json'),JSON.stringify({skills:['example']}));
  await fs.writeFile(path.join(payload,'AGENTS.md'),'Fixture instructions.');
  await fs.writeFile(path.join(payload,'rules/workspace.md'),'Fixture rules.');
  await fs.writeFile(path.join(payload,'skills/example/SKILL.md'),'---\nname: example\ndescription: Fixture\n---\nFixture.');
  const homeDir=path.join(f.home,'installed-home'),workspaceRoot=path.join(f.home,'installed-workspace');
  await fs.mkdir(workspaceRoot);
  await installCouncil({homeDir,workspaceRoot,payloadRoot:payload,scriptRoot:path.resolve(import.meta.dirname,'..'),nodePath:process.execPath});
  const installed=path.join(homeDir,'.council','scripts','council-codex.mjs');
  const result=JSON.parse(execFileSync(process.execPath,[installed,'icm','list'],{encoding:'utf8'}));
  assert.deepEqual(result,{records:[]});
});

test('tracked candidate bound cannot grow beyond what reconciliation can cover',async t=>{
  const f=await fixture(t);const candidates=Array.from({length:40},(_,i)=>({id:'C'+i,claim:'Scoped claim '+i,scope:'Fixture only',source_ids:['story']}));
  await f.call('investigate',f.capture({candidates}));
  await assert.rejects(f.call('investigate',f.capture({event_id:'overflow',previous_event:'review-1',candidates:[{...candidates[0],id:'extra'}]})),/candidate.*full/i);
  const list=await f.call('list');assert.equal(list.records[0].last_event,'review-1');
});

test('updated architecture is captured from the checked target and namespace writes reject linked storage',async t=>{
  const f=await fixture(t);await f.call('investigate',f.capture());
  const r=f.reconcile();r.architecture={status:'updated',reason:'Fixture documentation verified at synced target.',documents:[r.decisions[0].evidence[0]]};
  const done=await f.call('reconcile',r);const record=JSON.parse(await fs.readFile(done.record_path,'utf8'));
  assert.equal(record.events[1].verified.documents[0].revision,f.head);
  const other=await fixture(t);const destination=path.join(other.home,'.council','memory','knowledge');
  await fs.mkdir(path.dirname(destination),{recursive:true});
  await fs.symlink(other.repo,destination,process.platform==='win32'?'junction':'dir');
  await assert.rejects(other.call('investigate',other.capture()),/directory|storage/i);
  await assert.rejects(other.call('list'),/directory|storage/i);
  await assert.rejects(fs.access(path.join(other.repo,'pr','CONTEXT.md')));
});

test('invalid private JSON and oversized input fail without leaking the selected content',async t=>{
  const f=await fixture(t);const p=path.join(f.home,'private-input.json');
  for(const bytes of [Buffer.from('SECRET'),Buffer.from([0xff]),Buffer.from('x'.repeat(1024*1024+1))]) {
    await fs.writeFile(p,bytes);
    await assert.rejects(executeCommand(['icm','investigate','--home',f.home,'--workspace',f.repo,'--record',p]),error=>!error.message.includes('SECRET'));
  }
});

test('a committed event survives failed projection and a duplicate repairs it without duplicating history',async t=>{
  const f=await fixture(t);const original=await f.call('investigate',f.capture());
  await fs.unlink(original.note_path);await fs.mkdir(original.note_path);
  await assert.rejects(f.call('reconcile',f.reconcile()));
  const durable=JSON.parse(await fs.readFile(original.record_path,'utf8'));assert.equal(durable.events.length,2);
  await fs.rmdir(original.note_path);
  const repaired=await f.call('reconcile',f.reconcile());assert.equal(repaired.duplicate,true);
  assert.match(await fs.readFile(repaired.note_path,'utf8'),/confirmed/);
  assert.equal(JSON.parse(await fs.readFile(repaired.record_path,'utf8')).events.length,2);
});

test('malformed investigation and reconciliation receipts cannot replace valid knowledge',async t=>{
  const f=await fixture(t);const saved=await f.call('investigate',f.capture());
  const original=await fs.readFile(saved.record_path,'utf8');
  const invalidReviews=[null,[],{event_id:'../escape'},{base_sha:'short'},{repository:'two repositories'},
    {sources:'not an array'},{sources:[],candidates:f.capture().candidates},
    {sources:[...f.capture().sources,...f.capture().sources]},
    {candidates:[{...f.capture().candidates[0],claim:''}]},{none_reason:'Conflicting empty-capture reason.'}];
  for(const change of invalidReviews) {
    const input=change===null?null:Array.isArray(change)?change:{...f.capture(),event_id:'invalid',previous_event:'review-1',...change};
    if(input===null) {
      const p=path.join(f.home,'null.json');await fs.writeFile(p,'null');
      await assert.rejects(executeCommand(['icm','investigate','--home',f.home,'--workspace',f.repo,'--record',p]));
    }else await assert.rejects(f.call('investigate',input));
  }
  const mutations=[r=>{r.outcome='unknown';},r=>{r.decisions[0].status='automatic';},r=>{r.architecture.status='unknown';},
    r=>{r.architecture={status:'updated',reason:'No supporting documents.',documents:[]};},r=>{r.architecture.documents=[];},
    r=>{r.merge.evidence.kind='inferred';},r=>{r.repo_path='relative/path';},
    r=>{r.decisions[0].evidence[0].sha256='invalid';},r=>{r.decisions[0].evidence[0].end_line=50;}];
  for(const mutate of mutations) {const input=f.reconcile();mutate(input);await assert.rejects(f.call('reconcile',input));}
  await assert.rejects(executeCommand(['icm','investigate','--home',f.home,'--workspace',f.repo]),/record/i);
  assert.equal(await fs.readFile(saved.record_path,'utf8'),original);
});

test('a busy record and a full history preserve the last committed event',async t=>{
  const f=await fixture(t);const initial=await f.call('investigate',f.capture());
  const lock=path.join(path.dirname(initial.record_path),'record.lock');await fs.writeFile(lock,'fixture-owned');
  await assert.rejects(f.call('investigate',f.capture({event_id:'blocked',previous_event:'review-1'})),/busy/i);
  await fs.unlink(lock);
  let previous='review-1',last;
  const sources=Array.from({length:40},(_,i)=>({id:'S'+i,origin:'Synthetic story evidence',revision:'fixture',excerpt:'e'.repeat(7900)}));
  for(let i=0;i<4;i++) {
    const input=f.capture({event_id:'large-'+i,previous_event:previous,sources,candidates:[],none_reason:'No reusable claims in synthetic source.'});
    try {last=await f.call('investigate',input);previous=input.event_id;}
    catch(error) {assert.match(error.message,/full/i);assert.equal((await f.call('list')).records[0].last_event,previous);return;}
  }
  assert.fail('A bounded history must reject an oversized event sequence: '+last.last_event);
});

test('an empty candidate set can reconcile and invalid record directories fail closed',async t=>{
  const f=await fixture(t);await f.call('investigate',f.capture({candidates:[],none_reason:'Routine implementation details only.'}));
  const done=await f.call('reconcile',f.reconcile({decisions:[]}));assert.equal(done.status,'reconciled');
  await fs.writeFile(path.join(path.dirname(path.dirname(done.record_path)),'a'.repeat(64)),'not a record directory');
  await assert.rejects(f.call('list'),/directory/i);
});

test('no-candidate investigations are explicit and list is metadata-only within selected namespace',async t=>{
  const f=await fixture(t);await assert.rejects(f.call('investigate',f.capture({candidates:[]})),/reason/i);
  await f.call('investigate',f.capture({candidates:[],none_reason:'Only routine local defects.'}));
  const list=await f.call('list');assert.equal(list.records.length,1);
  assert(!JSON.stringify(list).includes('Eligibility is based'));
  const isolated=await f.call('list',null,['--memory-scope','workspace-session','--session','isolated']);
  assert.equal(isolated.records.length,0);
});

test('concurrent PR events serialize and malformed or corrupt records fail closed',async t=>{
  const f=await fixture(t);const initial=await f.call('investigate',f.capture());
  const attempts=await Promise.allSettled(['a','b'].map(event_id=>f.call('investigate',f.capture({event_id,previous_event:'review-1'}))));
  assert.equal(attempts.filter(x=>x.status==='fulfilled').length,1);
  const record=await fs.readFile(initial.record_path,'utf8');await fs.writeFile(initial.record_path,record.replace('destination','MUTATED'));
  await assert.rejects(f.call('list'),/integrity|corrupt/i);
  await assert.rejects(f.call('investigate',f.capture({pr_url:'https://user:secret@bitbucket.example.invalid/pr/42'})),/PR URL/i);
  await assert.rejects(f.call('investigate',f.capture({pr_url:f.capture().pr_url+'00',repository:'https://user:secret@bitbucket.example.invalid/acme/shipping.git'})),/repository/i);
  await assert.rejects(f.call('investigate',f.capture({transcript:'not an allowlisted field'})),/field/i);
});
