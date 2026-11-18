import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import * as daily from '../council-daily.mjs';
import {executeCommand} from '../council-codex.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex');
async function fixture(t){
 const parent=path.resolve(import.meta.dirname,'../../work/proposal-tests');await fs.mkdir(parent,{recursive:true});const root=await fs.mkdtemp(path.join(parent,'case-'));
 t.after(async()=>{assert.equal(path.dirname(root),parent);await fs.rm(root,{recursive:true,force:true});});
 const store=path.join(root,'order-management/.memory/maintenance');await fs.mkdir(store,{recursive:true});await fs.mkdir(path.join(root,'docs'));
 await fs.writeFile(path.join(root,'docs/api.md'),'Integrated rule v2\n');
 await fs.writeFile(path.join(store,'config.json'),JSON.stringify({schema_version:1,time_zone:'America/New_York',documents:['docs/api.md']}));
 const target='order-management/.memory/rule.md',index='order-management/.memory/CONTEXT.md';
 await fs.writeFile(path.join(root,target),'# Rule\nEstablished v1\n');await fs.writeFile(path.join(root,index),'# Knowledge\n[Rule](rule.md)\n');
 const o={workspaceRoot:root,homeDir:path.join(root,'home'),actor:'codex',chat:'daily-owner',now:'2026-11-16T15:00:00Z'},run=await daily.dailyScan(o),id={run_id:run.run_id,item_id:run.items[0]};
 const screening={impact:'potential',summary:'The integrated rule changed',evidence:[{side:'after',start_line:1,end_line:1,quote:'Integrated rule v2'}],knowledge_review:[]};
 await daily.recordDailyScreening(o,{...id,screening});const packet=await daily.dailyReviewPacket(o,{...id,stage:'reevaluate'});
 const proposal={summary:'Align the rule with integrated source',revisions:[{target,operation:'revise',before_sha256:hash('# Rule\nEstablished v1\n'),proposed_text:'# Rule\nEstablished v2\n',reason:'Integrated behavior changed'}],uncertainties:[]};
 const finished=await daily.finishDailyItem(o,{...id,decision:'proposed',reason:proposal.summary,screening_sha256:packet.screening_sha256,knowledge_review:[{path:index,sha256:hash('# Knowledge\n[Rule](rule.md)\n'),reason:'Existing knowledge route'}],proposal});
 const p=await import('../council-proposals.mjs');
 return {o:{...o,chat:'reviewer',now:'2026-11-17T15:00:00Z'},id,root,store,target,index,proposal,artifact:finished.path,p};
}
const request=(review,decision='accept')=>({review_id:review.review_id,review_sha256:review.review_sha256,decision,reason:'Explicit user decision for the displayed version',authorization:'explicit-user'});
test('a memory directory without a child segment resolves without examining a missing segment',async t=>{
 const f=await fixture(t),target='order-management/.memory';
 assert.equal(await daily.maintenanceIO.knowledgePath(f.o,target),path.join(f.root,target));
 assert.equal((await fs.stat(path.join(f.root,target))).isDirectory(),true);
});
test('missing uppercase memory is rejected by the simulated case-sensitive fallback',async t=>{
 const f=await fixture(t),descriptor=Object.getOwnPropertyDescriptor(process,'platform'),target='absent-case-sensitive-domain/.MEMORY/rule.md';
 if(!descriptor?.configurable||!Object.hasOwn(descriptor,'value')){t.skip('process.platform descriptor cannot be safely restored');return;}
 await assert.rejects(fs.stat(path.join(f.root,'absent-case-sensitive-domain')),{code:'ENOENT'});
 try{
  Object.defineProperty(process,'platform',{...descriptor,value:'linux'});
  await assert.rejects(daily.maintenanceIO.knowledgePath(f.o,target),/knowledge target must be in domain\/pod \.memory/i);
 }finally{Object.defineProperty(process,'platform',descriptor);}
 assert.deepEqual(Object.getOwnPropertyDescriptor(process,'platform'),descriptor);
 await assert.rejects(fs.stat(path.join(f.root,'absent-case-sensitive-domain')),{code:'ENOENT'});
});
test('a missing domain memory directory supports reviewed knowledge creation',async t=>{
 const f=await fixture(t),target='new-domain/.memory/rule.md',index='new-domain/.memory/CONTEXT.md',directory=path.join(f.root,'new-domain/.memory');
 assert.equal(await daily.maintenanceIO.knowledgePath(f.o,target),path.join(f.root,target));
 await assert.rejects(fs.stat(directory),{code:'ENOENT'});
 const artifact=JSON.parse(await fs.readFile(f.artifact,'utf8'));
 artifact.proposal.revisions=[
  {target,operation:'create',before_sha256:null,proposed_text:'# New domain rule\n',reason:'Add supported knowledge'},
  {target:index,operation:'create',before_sha256:null,proposed_text:'# Domain knowledge\n[Rule](rule.md)\n',reason:'Route the new rule'}
 ];
 await fs.writeFile(f.artifact,JSON.stringify(artifact));
 const review=await f.p.reviewProposal(f.o,f.id);assert.deepEqual(review.issues,[]);
 assert.equal((await f.p.decideProposal(f.o,request(review))).status,'accepted');
 assert.equal(await fs.readFile(path.join(f.root,target),'utf8'),'# New domain rule\n');
 assert.equal(await fs.readFile(path.join(f.root,index),'utf8'),'# Domain knowledge\n[Rule](rule.md)\n');
});
test('missing Windows maintenance aliases remain outside knowledge scope',{skip:process.platform!=='win32'},async t=>{
 const f=await fixture(t),existingMemory=path.join(f.root,'empty-domain/.memory');await fs.mkdir(existingMemory,{recursive:true});
 for(const target of ['empty-domain/.memory/Maintenance/history.md','absent-domain/.MeMoRy/MaInTeNaNcE/history.md']){
  await assert.rejects(daily.maintenanceIO.knowledgePath(f.o,target),/maintenance|knowledge/i);
  const artifact=JSON.parse(await fs.readFile(f.artifact,'utf8'));artifact.proposal.revisions=[{target,operation:'create',before_sha256:null,proposed_text:'# Disallowed history\n',reason:'Fixture boundary check'}];
  await fs.writeFile(f.artifact,JSON.stringify(artifact));await assert.rejects(f.p.reviewProposal(f.o,f.id),/maintenance|knowledge/i);
  await assert.rejects(fs.stat(path.join(f.root,target)),{code:'ENOENT'});
 }
});
test('a knowledge directory identity access failure does not fall back to a permitted name',async t=>{
 const f=await fixture(t),realpath=fs.realpath,memory=path.join(f.root,'order-management/.memory');let failures=0;
 try{
  fs.realpath=async(file,...args)=>{if(path.resolve(file)===memory){failures++;throw Object.assign(Error('Fixture identity access denied'),{code:'EACCES'});}return realpath(file,...args);};
  await assert.rejects(daily.maintenanceIO.knowledgePath(f.o,f.target),{code:'EACCES'});
  await assert.rejects(f.p.reviewProposal(f.o,f.id),{code:'EACCES'});
 }finally{fs.realpath=realpath;}
 assert.equal(failures,2);assert.equal(await fs.readFile(path.join(f.root,f.target),'utf8'),'# Rule\nEstablished v1\n');
});
test('maintenance case aliases cannot be reviewed or used as knowledge',async t=>{
 const f=await fixture(t),protectedFile=path.join(f.store,'protected.md'),alias='order-management/.memory/Maintenance/protected.md';
 await fs.writeFile(protectedFile,'Immutable maintenance history');
 let same=false;try{same=(await fs.stat(path.join(f.root,alias))).ino===(await fs.stat(protectedFile)).ino;}catch(e){if(e.code!=='ENOENT')throw e;}
 if(!same){t.skip('Fixture filesystem has distinct maintenance case names');return;}
 await assert.rejects(daily.maintenanceIO.knowledgePath(f.o,alias),/knowledge|maintenance|scope/i);
 const artifact=JSON.parse(await fs.readFile(f.artifact,'utf8'));artifact.proposal.revisions[0].target=alias;artifact.proposal.revisions[0].before_sha256=hash('Immutable maintenance history');
 await fs.writeFile(f.artifact,JSON.stringify(artifact));
 await assert.rejects(f.p.reviewProposal(f.o,f.id),/knowledge|maintenance|scope/i);
 assert.equal(await fs.readFile(protectedFile,'utf8'),'Immutable maintenance history');
});
test('two workspaces cannot accept concurrent revisions of one central target',async t=>{
 const a=await fixture(t),b=await fixture(t),central=path.join(a.o.homeDir,'.council/memory/knowledge'),target=path.join(central,'rule.md');
 await fs.mkdir(central,{recursive:true});await fs.writeFile(target,'# Central v1\n');
 const reviews=[];
 for(const [f,text] of [[a,'# Approved A\n'],[b,'# Approved B\n']]){
  f.o.homeDir=a.o.homeDir;const artifact=JSON.parse(await fs.readFile(f.artifact,'utf8'));
  artifact.proposal.revisions=[{target,operation:'revise',before_sha256:hash('# Central v1\n'),proposed_text:text,reason:'Shared central rule'}];await fs.writeFile(f.artifact,JSON.stringify(artifact));
  reviews.push(await f.p.reviewProposal(f.o,f.id));assert.deepEqual(reviews.at(-1).issues,[]);
 }
 let arrived,release;const paused=new Promise(r=>arrived=r),gate=new Promise(r=>release=r),rename=fs.rename;let pending,first=true;
 try{
  fs.rename=async(from,to)=>{if(first&&to===target){first=false;arrived();await gate;}return rename(from,to);};
  pending=a.p.decideProposal(a.o,request(reviews[0]));
  await Promise.race([paused,pending.then(()=>{throw Error('First decision ended before the target write boundary');})]);
  const rejected=await b.p.decideProposal(b.o,request(reviews[1]));
  assert.equal(rejected.status,'failed');assert.equal(rejected.written.length,0);assert.equal(await fs.readFile(target,'utf8'),'# Central v1\n');
  await assert.rejects(b.p.decideProposal(b.o,request(reviews[1])),/exist|decided|attempt/i);
 }finally{release();if(pending)await pending;fs.rename=rename;}
 assert.equal((await a.p.listProposals(a.o,{status:'accepted'})).total,1);assert.equal(await fs.readFile(target,'utf8'),'# Approved A\n');
});
test('completed proposals are reviewable across chats/days and stay pending without a decision',async t=>{
 const f=await fixture(t),list=await f.p.listProposals(f.o,{});assert.equal(list.proposals.length,1);assert.equal(list.proposals[0].status,'pending');
 const review=await f.p.reviewProposal(f.o,f.id);assert.equal(review.proposal.summary,f.proposal.summary);assert.deepEqual(review.issues,[]);
 assert.equal(await fs.readFile(path.join(f.root,f.target),'utf8'),'# Rule\nEstablished v1\n');
 assert.equal((await f.p.proposalStatus(f.o,{target:f.target})).status,'needs-review');
 if(process.platform==='win32')assert.equal((await f.p.proposalStatus(f.o,{target:f.target.replace('rule.md','RULE.md')})).status,'needs-review');
});
test('accept requires explicit approval of the exact review and preserves before/after evidence',async t=>{
 const f=await fixture(t),r=await f.p.reviewProposal(f.o,f.id),a=request(r);
 const missing={...a};delete missing.authorization;await assert.rejects(f.p.decideProposal(f.o,missing),/explicit|approval/i);
 await assert.rejects(f.p.decideProposal(f.o,{...a,review_sha256:'0'.repeat(64)}),/fingerprint|version/i);
 const result=await f.p.decideProposal(f.o,a);assert.equal(result.status,'accepted');assert.equal(await fs.readFile(path.join(f.root,f.target),'utf8'),'# Rule\nEstablished v2\n');
 assert.equal(await fs.readFile(path.join(f.store,'snapshots',hash('# Rule\nEstablished v1\n')+'.md'),'utf8'),'# Rule\nEstablished v1\n');
 assert.equal((await f.p.proposalStatus(f.o,{target:f.target})).status,'no-pending-review');
 await assert.rejects(f.p.decideProposal(f.o,a),/exist|decided|attempt/i);
});
test('reject changes no knowledge and can close a proposal whose target is now stale',async t=>{
 const f=await fixture(t),r=await f.p.reviewProposal(f.o,f.id);await fs.writeFile(path.join(f.root,f.target),'Independent correction');
 const result=await f.p.decideProposal(f.o,request(r,'reject'));assert.equal(result.status,'rejected');assert.equal(await fs.readFile(path.join(f.root,f.target),'utf8'),'Independent correction');
 assert.equal((await f.p.listProposals(f.o,{})).proposals.length,0);
});
test('stale sources or targets fail acceptance durably without replay or knowledge writes',async t=>{
 const f=await fixture(t),r=await f.p.reviewProposal(f.o,f.id);await fs.writeFile(path.join(f.root,'docs/api.md'),'A later integrated rule\n');
 const result=await f.p.decideProposal(f.o,request(r));assert.equal(result.status,'failed');assert.equal(await fs.readFile(path.join(f.root,f.target),'utf8'),'# Rule\nEstablished v1\n');
 await assert.rejects(f.p.decideProposal(f.o,request(r)),/exist|decided|attempt/i);assert.equal((await f.p.proposalStatus(f.o,{target:f.target})).status,'needs-review');
});
test('editing an output creates a new review version and cannot change an earlier approval',async t=>{
 const f=await fixture(t),r=await f.p.reviewProposal(f.o,f.id),artifact=JSON.parse(await fs.readFile(f.artifact,'utf8'));artifact.proposal.revisions[0].proposed_text='# Rule\nAmended v2\n';await fs.writeFile(f.artifact,JSON.stringify(artifact));
 const amended=await f.p.reviewProposal(f.o,f.id);assert.notEqual(amended.review_id,r.review_id);
 const result=await f.p.decideProposal(f.o,request(r));assert.equal(result.status,'failed');assert.equal(await fs.readFile(path.join(f.root,f.target),'utf8'),'# Rule\nEstablished v1\n');
});
test('the latest explicitly reviewed amendment can be accepted before any terminal decision',async t=>{
 const f=await fixture(t),first=await f.p.reviewProposal(f.o,f.id),artifact=JSON.parse(await fs.readFile(f.artifact,'utf8'));artifact.proposal.revisions[0].proposed_text='# Rule\nApproved amended v2\n';await fs.writeFile(f.artifact,JSON.stringify(artifact));
 const latest=await f.p.reviewProposal(f.o,f.id);assert.notEqual(latest.review_id,first.review_id);
 assert.equal((await f.p.decideProposal(f.o,request(latest))).status,'accepted');assert.equal(await fs.readFile(path.join(f.root,f.target),'utf8'),'# Rule\nApproved amended v2\n');
});
test('retirement preserves the old version and applies the exact reviewed tombstone',async t=>{
 const f=await fixture(t),artifact=JSON.parse(await fs.readFile(f.artifact,'utf8'));artifact.proposal.revisions[0].operation='retire';artifact.proposal.revisions[0].proposed_text=null;await fs.writeFile(f.artifact,JSON.stringify(artifact));
 const r=await f.p.reviewProposal(f.o,f.id),after=await fs.readFile(path.join(f.store,'snapshots',r.changes[0].after_sha256+'.md'),'utf8');assert.match(after,/Status: retired/);
 assert.equal((await f.p.decideProposal(f.o,request(r))).status,'accepted');assert.equal(await fs.readFile(path.join(f.root,f.target),'utf8'),after);assert.doesNotMatch(after,/Established v1/);
});
test('creating knowledge requires a route from its owning index and applies the approved index edit',async t=>{
 const f=await fixture(t),artifact=JSON.parse(await fs.readFile(f.artifact,'utf8')),target='order-management/.memory/notes/new.md';
 artifact.proposal.revisions=[{target,operation:'create',before_sha256:null,proposed_text:'# New rule\nSupported v2\n',reason:'New integrated rule'}];await fs.writeFile(f.artifact,JSON.stringify(artifact));
 const unrouted=await f.p.reviewProposal(f.o,f.id);assert.ok(unrouted.issues.some(i=>i.scope==='routing'));
 artifact.proposal.revisions.push({target:f.index,operation:'revise',before_sha256:hash('# Knowledge\n[Rule](rule.md)\n'),proposed_text:'# Knowledge\n[Rule](rule.md)\n[New rule](notes/new.md)\n',reason:'Make the new note discoverable'});await fs.writeFile(f.artifact,JSON.stringify(artifact));
 const routed=await f.p.reviewProposal(f.o,f.id);assert.deepEqual(routed.issues,[]);assert.equal((await f.p.decideProposal(f.o,request(routed))).status,'accepted');
 assert.equal(await fs.readFile(path.join(f.root,target),'utf8'),'# New rule\nSupported v2\n');assert.match(await fs.readFile(path.join(f.root,f.index),'utf8'),/notes\/new.md/);
});
test('a changed target blocks acceptance without changing that target',async t=>{
 const f=await fixture(t),r=await f.p.reviewProposal(f.o,f.id);await fs.writeFile(path.join(f.root,f.target),'Concurrent correction');
 const result=await f.p.decideProposal(f.o,request(r));assert.equal(result.status,'failed');assert.equal(result.written.length,0);assert.equal(await fs.readFile(path.join(f.root,f.target),'utf8'),'Concurrent correction');
});
test('preparing an unchanged proposal against changed target content produces a new review version',async t=>{
 const f=await fixture(t),before=await f.p.reviewProposal(f.o,f.id);await fs.writeFile(path.join(f.root,f.target),'A separate corrected version');
 const after=await f.p.reviewProposal(f.o,f.id);assert.notEqual(after.review_id,before.review_id);assert.ok(after.issues.some(i=>i.scope==='knowledge-and-targets'));
});
test('busy knowledge target locks are not reclaimed or silently retried',async t=>{
 const f=await fixture(t),r=await f.p.reviewProposal(f.o,f.id);
 const lock=path.resolve(f.root,f.target)+'.council-proposal.lock';await fs.writeFile(lock,'Another decision owns this');
 const result=await f.p.decideProposal(f.o,request(r));assert.equal(result.status,'failed');assert.equal(result.written.length,0);assert.equal(await fs.readFile(lock,'utf8'),'Another decision owns this');
 await assert.rejects(f.p.decideProposal(f.o,request(r)),/exist|decided|attempt/i);
});
test('accepted history is preserved even when the editable original output is later changed',async t=>{
 const f=await fixture(t),r=await f.p.reviewProposal(f.o,f.id);await f.p.decideProposal(f.o,request(r));await fs.writeFile(f.artifact,'Edited historical output');
 const list=await f.p.listProposals(f.o,{status:'accepted'});assert.equal(list.proposals.length,1);assert.deepEqual(list.failures,[]);assert.equal((await f.p.proposalStatus(f.o,{target:f.target})).status,'no-pending-review');
});
test('an unapproved edit of an accepted knowledge file is visible during retrieval',async t=>{
 const f=await fixture(t),r=await f.p.reviewProposal(f.o,f.id);await f.p.decideProposal(f.o,request(r));await fs.writeFile(path.join(f.root,f.target),'Unapproved later edit');
 const result=await f.p.proposalStatus(f.o,{target:f.target});assert.equal(result.status,'needs-review');assert.equal(result.accepted_version_matches,false);
});
test('approval is scoped to its workspace even when two proposal contents are identical',async t=>{
 const a=await fixture(t),b=await fixture(t),ra=await a.p.reviewProposal(a.o,a.id),rb=await b.p.reviewProposal(b.o,b.id);
 assert.notEqual(ra.review_id,rb.review_id);await assert.rejects(b.p.decideProposal(b.o,request(ra)));
 assert.equal(await fs.readFile(path.join(b.root,b.target),'utf8'),'# Rule\nEstablished v1\n');
});
test('partial application is recorded as failed and both intended targets remain qualified',async t=>{
 const f=await fixture(t),other='order-management/.memory/other.md';await fs.writeFile(path.join(f.root,other),'Other v1');
 const artifact=JSON.parse(await fs.readFile(f.artifact,'utf8'));artifact.proposal.revisions.push({target:other,operation:'revise',before_sha256:hash('Other v1'),proposed_text:'Other v2',reason:'Related integrated change'});await fs.writeFile(f.artifact,JSON.stringify(artifact));
 const r=await f.p.reviewProposal(f.o,f.id),rename=fs.rename;let result;
 try{fs.rename=async(from,to)=>{if(to===path.join(f.root,other))throw Object.assign(Error('Injected fixture failure'),{code:'EIO'});return rename(from,to);};result=await f.p.decideProposal(f.o,request(r));}finally{fs.rename=rename;}
 assert.equal(result.status,'failed');assert.equal(result.written.length,1);assert.equal(await fs.readFile(path.join(f.root,f.target),'utf8'),'# Rule\nEstablished v2\n');assert.equal(await fs.readFile(path.join(f.root,other),'utf8'),'Other v1');
 assert.equal((await f.p.proposalStatus(f.o,{target:f.target})).status,'needs-review');assert.equal((await f.p.proposalStatus(f.o,{target:other})).status,'needs-review');
});
test('a later accepted version can resolve the direct-target qualification from an older failed proposal',async t=>{
 const f=await fixture(t),r=await f.p.reviewProposal(f.o,f.id);await fs.writeFile(path.join(f.root,'docs/api.md'),'Integrated rule v3\n');await f.p.decideProposal(f.o,request(r));
 const o={...f.o,chat:'another-daily-owner',now:'2026-11-18T15:00:00Z'},run=await daily.dailyScan(o),id={run_id:run.run_id,item_id:run.items[0]};
 await daily.recordDailyScreening(o,{...id,screening:{impact:'potential',summary:'The next integrated rule requires review',evidence:[{side:'after',start_line:1,end_line:1,quote:'Integrated rule v3'}],knowledge_review:[]}});const packet=await daily.dailyReviewPacket(o,{...id,stage:'reevaluate'});
 await daily.finishDailyItem(o,{...id,decision:'proposed',reason:'Update to integrated v3',screening_sha256:packet.screening_sha256,knowledge_review:[{path:f.index,sha256:hash('# Knowledge\n[Rule](rule.md)\n'),reason:'Current routes'}],proposal:{summary:'Establish v3',revisions:[{target:f.target,operation:'revise',before_sha256:hash('# Rule\nEstablished v1\n'),proposed_text:'# Rule\nEstablished v3\n',reason:'Later integrated source'}],uncertainties:[]}});
 const next=await f.p.reviewProposal(o,id);assert.equal((await f.p.decideProposal(o,request(next))).status,'accepted');assert.equal((await f.p.proposalStatus(o,{target:f.target})).status,'no-pending-review');
});
test('pending target status must inspect records beyond the first listing page',async t=>{
 const f=await fixture(t),original=JSON.parse(await fs.readFile(path.join(f.store,'work',f.id.item_id+'.json'),'utf8')),artifact=JSON.parse(await fs.readFile(f.artifact,'utf8'));
 assert.ok(BigInt('0x'+f.id.item_id)>200n);
 for(let i=0;i<200;i++){
  const id=i.toString(16).padStart(64,'0'),item={...original,item_id:id},copy=structuredClone(artifact);copy.item_id=id;copy.proposal.revisions[0].target='order-management/.memory/unrelated.md';
  await fs.writeFile(path.join(f.store,'work',id+'.json'),JSON.stringify(item));await fs.writeFile(path.join(f.store,'stages/02-reevaluate/output',id+'.json'),JSON.stringify(copy));
 }
 assert.equal((await f.p.proposalStatus(f.o,{target:f.target})).status,'needs-review');
});
async function enableMainline(f,checkedOn){
 const file=path.join(f.store,'config.json'),config=JSON.parse(await fs.readFile(file,'utf8'));
 config.mainline={enabled:true,repositories:[{name:'sample',path:'repo',branch:'main',baseline_commit:'a'.repeat(40),baseline_checked_on:checkedOn,baseline_documents:{'docs/api.md':hash('Integrated rule v2\n')},documents:['docs/api.md']}]};await fs.writeFile(file,JSON.stringify(config));
}
test('acceptance requires current integrated-mainline freshness when that mode is enabled',async t=>{
 const stale=await fixture(t);await enableMainline(stale,'2026-11-16');const blocked=await stale.p.reviewProposal(stale.o,stale.id);assert.ok(blocked.issues.some(i=>i.scope==='source'));
 assert.equal((await stale.p.decideProposal(stale.o,request(blocked))).status,'failed');
 const current=await fixture(t);await enableMainline(current,'2026-11-17');const review=await current.p.reviewProposal(current.o,current.id);assert.deepEqual(review.issues,[]);assert.equal((await current.p.decideProposal(current.o,request(review))).status,'accepted');
});
test('an invalid proposal ledger entry is reported without exposing its raw contents',async t=>{
 const f=await fixture(t);await fs.writeFile(path.join(f.store,'work','0'.repeat(64)+'.json'),'BROKEN_PRIVATE_PAYLOAD');
 const list=await f.p.listProposals(f.o,{});assert.equal(list.failures.length,1);assert.doesNotMatch(JSON.stringify(list),/BROKEN_PRIVATE_PAYLOAD/);assert.equal((await f.p.proposalStatus(f.o,{target:f.target})).record_failures,1);
});
test('common CLI supports pending review, an exact user decision and accepted status',async t=>{
 const f=await fixture(t),file=path.join(f.root,'decision.json');
 const invoke=async(action,record)=>{await fs.writeFile(file,JSON.stringify(record));return JSON.parse((await executeCommand(['daily',action,'--workspace',f.root,'--home',f.o.homeDir,'--chat',f.o.chat,'--record',file])).output);};
 assert.equal((await invoke('proposal-list',{})).total,1);const r=await invoke('proposal-review',f.id);assert.equal((await invoke('proposal-status',{target:f.target})).status,'needs-review');
 assert.equal((await invoke('proposal-decide',request(r))).status,'accepted');assert.equal((await invoke('proposal-list',{status:'accepted'})).total,1);
});
test('acceptance cannot rewrite runtime tooling or collection workflow instructions as knowledge',async t=>{
 const f=await fixture(t),original=JSON.parse(await fs.readFile(f.artifact,'utf8'));
 for(const target of ['order-management/.memory/tool.mjs',path.join(f.o.homeDir,'.council/memory/knowledge/tools/loader.md'),path.join(f.o.homeDir,'.council/memory/knowledge/workflows/02-retrieve/CONTEXT.md')]){
  const artifact=structuredClone(original);artifact.proposal.revisions[0].target=target;await fs.writeFile(f.artifact,JSON.stringify(artifact));await assert.rejects(f.p.reviewProposal(f.o,f.id),/Markdown|workflow|tool|history/i);
 }
});

test('reverting to an older accepted version does not satisfy the latest approval',async t=>{
 const f=await fixture(t),first=await f.p.reviewProposal(f.o,f.id);assert.equal((await f.p.decideProposal(f.o,request(first))).status,'accepted');
 await fs.writeFile(path.join(f.root,'docs/api.md'),'Integrated rule v3\n');
 const o={...f.o,chat:'next-daily-owner',now:'2026-11-18T15:00:00Z'},run=await daily.dailyScan(o),id={run_id:run.run_id,item_id:run.items[0]};
 await daily.recordDailyScreening(o,{...id,screening:{impact:'potential',summary:'Next integrated rule',evidence:[{side:'after',start_line:1,end_line:1,quote:'Integrated rule v3'}],knowledge_review:[]}});
 const packet=await daily.dailyReviewPacket(o,{...id,stage:'reevaluate'});
 await daily.finishDailyItem(o,{...id,decision:'proposed',reason:'Integrated v3',screening_sha256:packet.screening_sha256,knowledge_review:[{path:f.index,sha256:hash('# Knowledge\n[Rule](rule.md)\n'),reason:'Current route'}],proposal:{summary:'Establish v3',revisions:[{target:f.target,operation:'revise',before_sha256:hash('# Rule\nEstablished v2\n'),proposed_text:'# Rule\nEstablished v3\n',reason:'Later source'}],uncertainties:[]}});
 const latest=await f.p.reviewProposal(o,id);assert.equal((await f.p.decideProposal(o,request(latest))).status,'accepted');
 assert.equal((await f.p.proposalStatus(o,{target:f.target})).status,'no-pending-review');
 await fs.writeFile(path.join(f.root,f.target),'# Rule\nEstablished v2\n');
 const drift=await f.p.proposalStatus(o,{target:f.target});assert.equal(drift.status,'needs-review');assert.equal(drift.accepted_version_matches,false);
});
