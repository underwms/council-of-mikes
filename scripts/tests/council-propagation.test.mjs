import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import * as daily from '../council-daily.mjs';
import * as proposals from '../council-proposals.mjs';
import {executeCommand} from '../council-codex.mjs';
const hash=b=>createHash('sha256').update(b).digest('hex');
const child='order-management/shipping/.memory',parent='order-management/.memory';
const approve=r=>({review_id:r.review_id,review_sha256:r.review_sha256,decision:'accept',reason:'User approved this displayed version',authorization:'explicit-user'});
async function fixture(t){
 const directory=path.resolve(import.meta.dirname,'../../work/propagation-tests');await fs.mkdir(directory,{recursive:true});const root=await fs.mkdtemp(path.join(directory,'case-'));
 t.after(async()=>{assert.equal(path.dirname(root),directory);await fs.rm(root,{recursive:true,force:true});});
 const store=path.join(root,parent,'maintenance');await fs.mkdir(store,{recursive:true});await fs.mkdir(path.join(root,child),{recursive:true});await fs.mkdir(path.join(root,'docs'));
 const config={schema_version:1,time_zone:'America/New_York',documents:['docs/api.md'],propagation:{enabled:true,collections:[{root:child,parent},{root:parent,parent:null}]}};
 await fs.writeFile(path.join(store,'config.json'),JSON.stringify(config));await fs.writeFile(path.join(root,'docs/api.md'),'Integrated shipping rule v2\n');
 const target=child+'/rule.md',index=child+'/CONTEXT.md',domain=parent+'/domain.md',domainIndex=parent+'/CONTEXT.md';
 await fs.writeFile(path.join(root,target),'# Shipping\nAccepted v1\n');await fs.writeFile(path.join(root,index),'# Shipping index\n[Rule](rule.md)\n');
 await fs.writeFile(path.join(root,domain),'# Domain\nShipping contributes v1\n');await fs.writeFile(path.join(root,domainIndex),'# Domain index\n[Domain](domain.md)\n');
 const o={workspaceRoot:root,homeDir:path.join(root,'home'),actor:'codex',chat:'first',now:'2026-11-16T15:00:00Z'};
 const run=await daily.dailyScan(o),id={run_id:run.run_id,item_id:run.items[0]};
 await daily.recordDailyScreening(o,{...id,screening:{impact:'potential',summary:'Shipping rule changed',evidence:[{side:'after',start_line:1,end_line:1,quote:'Integrated shipping rule v2'}],knowledge_review:[]}});
 const packet=await daily.dailyReviewPacket(o,{...id,stage:'reevaluate'});
 await daily.finishDailyItem(o,{...id,decision:'proposed',reason:'Align shipping knowledge',screening_sha256:packet.screening_sha256,knowledge_review:[{path:index,sha256:hash('# Shipping index\n[Rule](rule.md)\n'),reason:'Owning pod index'}],proposal:{summary:'Shipping v2',revisions:[{target,operation:'revise',before_sha256:hash('# Shipping\nAccepted v1\n'),proposed_text:'# Shipping\nAccepted v2\n',reason:'Integrated rule v2'}],uncertainties:[]}});
 const review=await proposals.reviewProposal(o,id);
 return {o,root,store,target,index,domain,domainIndex,config,id,review};
}
const tomorrow=f=>({...f.o,now:'2026-11-17T15:00:00Z',chat:'next-day'});
test('only a completed acceptance queues the exact child versions for the parent',async t=>{
 const f=await fixture(t),result=await proposals.decideProposal(f.o,approve(f.review));
 assert.ok(result.propagation,'Acceptance must return its propagation disposition');
 assert.equal(result.status,'accepted');assert.equal(result.propagation.status,'queued');assert.equal(result.propagation.events.length,1);
 const {listPropagation}=await import('../council-propagation.mjs'),list=await listPropagation(f.o,{});
 assert.equal(list.events.length,1);assert.equal(list.events[0].parent,parent);assert.equal(list.events[0].status,'waiting');
 const event=JSON.parse(await fs.readFile(path.join(f.store,'propagation/events',result.propagation.events[0]+'.json'),'utf8'));
 assert.equal(event.change.after_sha256,hash('# Shipping\nAccepted v2\n'));assert.equal(event.change.before_sha256,hash('# Shipping\nAccepted v1\n'));
 const rejected=await fixture(t);assert.equal((await proposals.decideProposal(rejected.o,{...approve(rejected.review),decision:'reject'})).status,'rejected');assert.equal((await listPropagation(rejected.o,{})).events.length,0);
 const failed=await fixture(t);await fs.writeFile(path.join(failed.root,'docs/api.md'),'Later source');assert.equal((await proposals.decideProposal(failed.o,approve(failed.review))).status,'failed');assert.equal((await listPropagation(failed.o,{})).events.length,0);
});
test('queued work waits until next daily claim even without document changes and is shared across clients',async t=>{
 const f=await fixture(t);await proposals.decideProposal(f.o,approve(f.review));
 assert.equal((await daily.dailyScan({...f.o,chat:'later'})).status,'already-attempted');
 const o=tomorrow(f),run=await daily.dailyScan(o);assert.equal(run.items.length,1);const id={run_id:run.run_id,item_id:run.items[0]};
 const packet=await daily.dailyReviewPacket(o,id);assert.equal(packet.source_kind,'propagation');assert.equal(packet.parent_collection,parent);assert.equal(packet.knowledge_index,path.join(f.root,f.domainIndex));
 assert.equal(packet.before.sha256,hash('# Shipping\nAccepted v1\n'));assert.equal(packet.after.sha256,hash('# Shipping\nAccepted v2\n'));
 assert.equal((await daily.dailyScan({...o,actor:'gemini',chat:'second'})).status,'already-attempted');
 assert.equal((await proposals.proposalStatus(o,{target:f.domain})).parent_review.status,'pending-parent-review');
});
async function parentProposal(f,o,id,target=f.domain){
 await daily.recordDailyScreening(o,{...id,screening:{impact:'potential',summary:'Domain explanation may depend on shipping',evidence:[{side:'after',start_line:2,end_line:2,quote:'Accepted v2'}],knowledge_review:[{path:f.domainIndex,sha256:hash('# Domain index\n[Domain](domain.md)\n'),reason:'Inspected parent scope'}]}});
 const packet=await daily.dailyReviewPacket(o,{...id,stage:'reevaluate'});
 return daily.finishDailyItem(o,{...id,decision:'proposed',reason:'Revise domain interpretation',screening_sha256:packet.screening_sha256,knowledge_review:[{path:f.domainIndex,sha256:hash('# Domain index\n[Domain](domain.md)\n'),reason:'Domain route'}],proposal:{summary:'Domain synthesis v2',revisions:[{target,operation:'revise',before_sha256:hash(await fs.readFile(path.join(f.root,target))),proposed_text:'# Domain\nShipping contributes v2; other pods are not assessed.\n',reason:'Scoped synthesis from accepted pod evidence'}],uncertainties:['No enterprise-wide rule inferred']}});
}
test('parent revisions reuse explicit approval and terminate at the domain',async t=>{
 const f=await fixture(t);await proposals.decideProposal(f.o,approve(f.review));const o=tomorrow(f),run=await daily.dailyScan(o),id={run_id:run.run_id,item_id:run.items[0]};
 await parentProposal(f,o,id);assert.equal(await fs.readFile(path.join(f.root,f.domain),'utf8'),'# Domain\nShipping contributes v1\n');
 const review=await proposals.reviewProposal(o,id);assert.deepEqual(review.issues,[]);const missing={...approve(review)};delete missing.authorization;await assert.rejects(proposals.decideProposal(o,missing),/approval/i);
 const result=await proposals.decideProposal(o,approve(review));assert.equal(result.status,'accepted');assert.equal(result.propagation.status,'terminal');
 assert.match(await fs.readFile(path.join(f.root,f.domain),'utf8'),/Shipping contributes v2/);
 assert.equal((await proposals.proposalStatus(o,{target:f.domain})).parent_review.status,'no-pending-parent-review');
 assert.equal((await daily.dailyScan({...o,now:'2026-11-18T15:00:00Z'})).items.length,0);
});

test('parent screening requires consulting its owning index rather than dismissing a child change blindly',async t=>{
 const f=await fixture(t);await proposals.decideProposal(f.o,approve(f.review));const o=tomorrow(f),run=await daily.dailyScan(o),id={run_id:run.run_id,item_id:run.items[0]};
 const screening={impact:'none',summary:'No domain impact',evidence:[{side:'after',start_line:2,end_line:2,quote:'Accepted v2'}],knowledge_review:[]};
 await assert.rejects(daily.recordDailyScreening(o,{...id,screening}),/parent.*index|parent.*review/i);
 screening.knowledge_review=[{path:f.domainIndex,sha256:hash('# Domain index\n[Domain](domain.md)\n'),reason:'Parent explanation already covers the change'}];
 await daily.recordDailyScreening(o,{...id,screening});await daily.finishDailyItem(o,{...id,decision:'no-impact',reason:'Parent explanation remains valid'});
 assert.equal((await proposals.proposalStatus(o,{target:f.domain})).parent_review.status,'no-pending-parent-review');
});
test('a parent proposal cannot revise its child or a sibling collection',async t=>{
 const f=await fixture(t);await proposals.decideProposal(f.o,approve(f.review));const o=tomorrow(f),run=await daily.dailyScan(o),id={run_id:run.run_id,item_id:run.items[0]};
 await assert.rejects(parentProposal(f,o,id,f.target),/parent collection/);
 const work=JSON.parse(await fs.readFile(path.join(f.store,'work',id.item_id+'.json'),'utf8'));assert.equal(work.finalized,false);
});
test('accepted child drift blocks investigation and remains failed without next-day replay',async t=>{
 const f=await fixture(t);await proposals.decideProposal(f.o,approve(f.review));const o=tomorrow(f),run=await daily.dailyScan(o),id={run_id:run.run_id,item_id:run.items[0]};
 await fs.writeFile(path.join(f.root,f.target),'Unapproved child edit');await assert.rejects(daily.dailyReviewPacket(o,id),/child knowledge changed/);
 await daily.finishDailyItem(o,{...id,decision:'failed',reason:'Accepted child version no longer available'});
 const next={...o,now:'2026-11-18T15:00:00Z'};assert.equal((await daily.dailyScan(next)).items.length,0);
 assert.equal((await proposals.proposalStatus(next,{target:f.domain})).parent_review.status,'parent-review-failed');
});
test('a changed integrated source invalidates a prepared parent approval',async t=>{
 const f=await fixture(t);await proposals.decideProposal(f.o,approve(f.review));const o=tomorrow(f),run=await daily.dailyScan(o),id={run_id:run.run_id,item_id:run.items[0]};await parentProposal(f,o,id);
 const review=await proposals.reviewProposal(o,id);await fs.writeFile(path.join(f.root,'docs/api.md'),'Integrated shipping v3\n');
 assert.equal((await proposals.decideProposal(o,approve(review))).status,'failed');assert.equal(await fs.readFile(path.join(f.root,f.domain),'utf8'),'# Domain\nShipping contributes v1\n');
});
test('late accepted work waits past the current daily claim and interrupted work is not reassigned',async t=>{
 const f=await fixture(t),o=tomorrow(f);assert.equal((await daily.dailyScan(o)).items.length,0);await proposals.decideProposal(o,approve(f.review));
 assert.equal((await daily.dailyScan({...o,chat:'another'})).status,'already-attempted');
 const next={...o,now:'2026-11-18T15:00:00Z'},run=await daily.dailyScan(next);assert.equal(run.items.length,1);
 const later={...next,now:'2026-11-19T15:00:00Z'};assert.equal((await daily.dailyScan(later)).items.length,0);
 assert.equal((await proposals.proposalStatus(later,{target:f.domain})).parent_review.status,'parent-review-failed');
});
test('enqueue duplication is not retried and unmapped accepted notes are reported explicitly',async t=>{
 const f=await fixture(t),accepted=await proposals.decideProposal(f.o,approve(f.review)),p=await import('../council-propagation.mjs');
 assert.equal((await p.enqueuePropagation(f.o,{item_id:f.id.item_id})).status,'already-attempted');assert.equal((await p.listPropagation(f.o,{})).events.length,accepted.propagation.events.length);
 const other=await fixture(t);other.config.propagation.collections=[{root:parent,parent:null}];await fs.writeFile(path.join(other.store,'config.json'),JSON.stringify(other.config));
 const result=await proposals.decideProposal(other.o,approve(other.review));assert.equal(result.status,'accepted');assert.equal(result.propagation.status,'unmapped');assert.deepEqual(result.propagation.unmapped,[other.target]);
 assert.equal((await p.listPropagation(other.o,{})).enqueues[0].status,'unmapped');
});
test('a propagation storage failure remains separate from successful knowledge acceptance and is not repaired',async t=>{
 const f=await fixture(t),directory=path.join(f.store,'propagation');await fs.mkdir(directory,{recursive:true});await fs.writeFile(path.join(directory,'events'),'Storage obstruction');
 const result=await proposals.decideProposal(f.o,approve(f.review));assert.equal(result.status,'accepted');assert.equal(result.propagation.status,'failed');
 assert.equal(await fs.readFile(path.join(f.root,f.target),'utf8'),'# Shipping\nAccepted v2\n');
 await fs.unlink(path.join(directory,'events'));
 const p=await import('../council-propagation.mjs');assert.equal((await p.enqueuePropagation(f.o,{item_id:f.id.item_id})).status,'already-attempted');
 assert.equal((await proposals.proposalStatus(f.o,{target:f.domain})).parent_review.status,'parent-review-failed');
 assert.equal((await daily.dailyScan(tomorrow(f))).items.length,0);
});
test('cyclic or ambiguous collection configuration records scheduling failure without undoing acceptance',async t=>{
 for(const collections of [[{root:child,parent},{root:parent,parent:child}],[{root:child,parent},{root:parent,parent:null},{root:child,parent}]]){
  const f=await fixture(t);f.config.propagation.collections=collections;await fs.writeFile(path.join(f.store,'config.json'),JSON.stringify(f.config));
  const result=await proposals.decideProposal(f.o,approve(f.review));assert.equal(result.status,'accepted');assert.equal(result.propagation.status,'failed');
 }
});
test('a missing enqueue completion is visible without scanning or repairing old acceptances',async t=>{
 const f=await fixture(t),directory=path.join(f.store,'propagation/enqueues');await fs.writeFile(directory,'Unavailable propagation enqueue home');
 const result=await proposals.decideProposal(f.o,approve(f.review));assert.equal(result.status,'accepted');assert.equal(result.propagation.status,'failed');
 await fs.unlink(directory);
 const status=await proposals.proposalStatus(f.o,{target:f.domain});assert.equal(status.parent_review.status,'parent-review-failed');
 assert.equal((await daily.dailyScan(tomorrow(f))).items.length,0);
});
test('the common CLI exposes propagation work and parent qualifications without mutating it',async t=>{
 const f=await fixture(t);await proposals.decideProposal(f.o,approve(f.review));const file=path.join(f.root,'request.json');
 await fs.writeFile(file,'{}');const flags=['--workspace',f.root,'--home',f.o.homeDir,'--chat',f.o.chat,'--record',file];
 const list=JSON.parse((await executeCommand(['daily','propagation-list',...flags])).output);assert.equal(list.events.length,1);
 await fs.writeFile(file,JSON.stringify({target:f.domain}));const result=JSON.parse((await executeCommand(['daily','propagation-status',...flags])).output);assert.equal(result.status,'pending-parent-review');
});
test('an original source needs current mainline freshness even when accepted child bytes still match',async t=>{
 const f=await fixture(t);await proposals.decideProposal(f.o,approve(f.review));
 f.config.mainline={enabled:true,repositories:[{name:'shipping',path:'repo',branch:'main',baseline_commit:'a'.repeat(40),baseline_checked_on:'2026-11-16',baseline_documents:{'docs/api.md':hash('Integrated shipping rule v2\n')},documents:['docs/api.md']}]};
 await fs.writeFile(path.join(f.store,'config.json'),JSON.stringify(f.config));const o=tomorrow(f),run=await daily.dailyScan(o);
 const record=JSON.parse(await fs.readFile(path.join(f.store,'runs',run.run_id+'.json'),'utf8')),item=JSON.parse(await fs.readFile(path.join(f.store,'work',record.propagation_items[0]+'.json'),'utf8'));
 const p=await import('../council-propagation.mjs');await assert.rejects(p.validatePropagationSource(o,item),/mainline freshness/);
 await assert.rejects(daily.dailyReviewPacket(o,{run_id:run.run_id,item_id:item.item_id}),/complete.*mainline.*scan/i);
});
test('no-revision-needed closes parent review with its rationale and does not require publication',async t=>{
 const f=await fixture(t);await proposals.decideProposal(f.o,approve(f.review));const o=tomorrow(f),run=await daily.dailyScan(o),id={run_id:run.run_id,item_id:run.items[0]};
 await daily.recordDailyScreening(o,{...id,screening:{impact:'potential',summary:'Investigate parent interpretation',evidence:[{side:'after',start_line:2,end_line:2,quote:'Accepted v2'}],knowledge_review:[{path:f.domainIndex,sha256:hash('# Domain index\n[Domain](domain.md)\n'),reason:'Owning parent'}]}});
 const packet=await daily.dailyReviewPacket(o,{...id,stage:'reevaluate'});await daily.finishDailyItem(o,{...id,decision:'no-revision-needed',reason:'Existing domain statement remains valid at its stated scope',screening_sha256:packet.screening_sha256,knowledge_review:[{path:f.domainIndex,sha256:hash('# Domain index\n[Domain](domain.md)\n'),reason:'Confirmed scope'}]});
 assert.equal((await proposals.proposalStatus(o,{target:f.domain})).parent_review.status,'no-pending-parent-review');assert.equal(await fs.readFile(path.join(f.root,f.domain),'utf8'),'# Domain\nShipping contributes v1\n');
});
test('tampered propagation identities fail closed and their assignment is never replayed',async t=>{
 const f=await fixture(t),accepted=await proposals.decideProposal(f.o,approve(f.review)),file=path.join(f.store,'propagation/events',accepted.propagation.events[0]+'.json');
 const event=JSON.parse(await fs.readFile(file,'utf8'));event.parent='order-management/other/.memory';await fs.writeFile(file,JSON.stringify(event));
 const run=await daily.dailyScan(tomorrow(f));assert.equal(run.items.length,0);assert.ok(run.failures.some(e=>e.propagation_event));
 const p=await import('../council-propagation.mjs');assert.equal((await p.listPropagation(f.o,{})).failures.length,1);
 const next={...f.o,now:'2026-11-18T15:00:00Z'};assert.equal((await daily.dailyScan(next)).failures.length,0);assert.equal((await proposals.proposalStatus(next,{target:f.domain})).parent_review.status,'parent-review-failed');
});
test('created and retired child notes queue their accepted versions without copying text into the parent',async t=>{
 for(const operation of ['create','retire']){
  const f=await fixture(t),file=path.join(f.store,'stages/02-reevaluate/output',f.id.item_id+'.json'),artifact=JSON.parse(await fs.readFile(file,'utf8'));
  if(operation==='retire'){artifact.proposal.revisions[0].operation='retire';artifact.proposal.revisions[0].proposed_text=null;}
  else{
   artifact.proposal.revisions=[{target:child+'/new.md',operation:'create',before_sha256:null,proposed_text:'# New accepted pod rule\n',reason:'New supported scope'},
    {target:f.index,operation:'revise',before_sha256:hash('# Shipping index\n[Rule](rule.md)\n'),proposed_text:'# Shipping index\n[Rule](rule.md)\n[New](new.md)\n',reason:'Discover new pod knowledge'}];
  }
  await fs.writeFile(file,JSON.stringify(artifact));const review=await proposals.reviewProposal(f.o,f.id),result=await proposals.decideProposal(f.o,approve(review));assert.equal(result.status,'accepted');assert.equal(result.propagation.events.length,operation==='create'?2:1);
  assert.equal(await fs.readFile(path.join(f.root,f.domain),'utf8'),'# Domain\nShipping contributes v1\n');
 }
});
test('an unreadable queued event consumes its attempt and is not reconsidered the following day',async t=>{
 const f=await fixture(t),accepted=await proposals.decideProposal(f.o,approve(f.review)),eventId=accepted.propagation.events[0];
 await fs.writeFile(path.join(f.store,'propagation/events',eventId+'.json'),'INVALID_QUEUE_PAYLOAD');
 const run=await daily.dailyScan(tomorrow(f));assert.equal(run.failures.length,1);
 const next=await daily.dailyScan({...f.o,now:'2026-11-18T15:00:00Z'});assert.equal(next.failures.length,0);assert.equal(next.items.length,0);
});
test('a real mainline fetch with no changed documents preserves and completes queued parent work',async t=>{
 const f=await fixture(t);await proposals.decideProposal(f.o,approve(f.review));
 const execute=promisify(execFile),git=async(cwd,...args)=>(await execute('git',['-C',cwd,...args],{encoding:'utf8',windowsHide:true})).stdout.trim();
 const publisher=path.join(f.root,'publisher');await fs.mkdir(publisher);await git(publisher,'init','-b','main');await fs.writeFile(path.join(publisher,'api.cs'),'Integrated shipping rule v2\n');await git(publisher,'add','api.cs');await git(publisher,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Integrated fixture');
 const revision=await git(publisher,'rev-parse','HEAD');await git(f.root,'clone','--branch','main',publisher,path.join(f.root,'repo'));
 f.config.mainline={enabled:true,repositories:[{name:'shipping',path:'repo',branch:'main',baseline_commit:revision,baseline_checked_on:'2026-11-16',baseline_documents:{'docs/api.md':hash('Integrated shipping rule v2\n')},documents:['docs/api.md']}]};
 await fs.writeFile(path.join(f.store,'config.json'),JSON.stringify(f.config));
 const o=tomorrow(f),claim=await daily.dailyScan(o);assert.equal(claim.mainline_pending,true);
 const mainline=await import('../council-mainline.mjs'),refreshed=await mainline.scanMainline(o,{run_id:claim.run_id});assert.equal(refreshed.refresh_items.length,0);
 const scan=await daily.continueDailyScan(o,{run_id:claim.run_id});assert.equal(scan.items.length,1);const id={run_id:claim.run_id,item_id:scan.items[0]};
 assert.equal((await daily.dailyReviewPacket(o,id)).source_kind,'propagation');await parentProposal(f,o,id);
 const review=await proposals.reviewProposal(o,id);assert.deepEqual(review.issues,[]);assert.equal((await proposals.decideProposal(o,approve(review))).status,'accepted');
 assert.equal(JSON.parse(await fs.readFile(path.join(f.store,'runs',claim.run_id+'.json'),'utf8')).status,'completed');
});
