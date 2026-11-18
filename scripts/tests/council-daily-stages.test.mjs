import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import * as daily from '../council-daily.mjs';
import {executeCommand} from '../council-codex.mjs';

const digest=text=>createHash('sha256').update(text).digest('hex');
async function fixture(t,now='2026-11-16T15:00:00Z'){
 const parent=path.resolve(import.meta.dirname,'../../work/daily-stage-tests');await fs.mkdir(parent,{recursive:true});
 const root=await fs.mkdtemp(path.join(parent,'case-'));t.after(async()=>{assert.equal(path.dirname(root),parent);await fs.rm(root,{recursive:true,force:true});});
 const store=path.join(root,'order-management/.memory/maintenance');await fs.mkdir(store,{recursive:true});
 await fs.mkdir(path.join(root,'docs'));await fs.writeFile(path.join(root,'docs/a.md'),'Routing changed\n');
 await fs.writeFile(path.join(store,'config.json'),JSON.stringify({schema_version:1,time_zone:'America/New_York',documents:['docs/a.md']}));
 const o={workspaceRoot:root,store,chat:'first',actor:'codex',now};
 const r=await daily.dailyScan(o),id={run_id:r.run_id,item_id:r.items[0]};
 const knowledge='order-management/.memory/CONTEXT.md';await fs.writeFile(path.join(root,knowledge),'# Knowledge\n');
 const screening={impact:'potential',summary:'Routing could affect maintained explanations',evidence:[{side:'after',start_line:1,end_line:1,quote:'Routing changed'}],knowledge_review:[]};
 const review=[{path:knowledge,sha256:digest('# Knowledge\n'),reason:'Checked current routing index'}];
 return {o,id,screening,review};
}
async function screen(f){return daily.recordDailyScreening(f.o,{...f.id,screening:f.screening});}
test('screening is a durable independent handoff and cannot generate revisions',async t=>{
 const f=await fixture(t);assert.equal(typeof daily.recordDailyScreening,'function');
 await assert.rejects(daily.recordDailyScreening(f.o,{...f.id,screening:f.screening,proposal:{}}),/screening|proposal/i);
 const result=await screen(f);const artifact=JSON.parse(await fs.readFile(result.path,'utf8'));
 assert.deepEqual(artifact.screening,f.screening);
 const work=JSON.parse(await fs.readFile(path.join(f.o.store,'work',f.id.item_id+'.json'),'utf8'));assert.equal(work.finalized,false);
 await assert.rejects(screen(f),/exist|recorded/i);
});
test('reevaluation consumes the edited stage file and records the exact handoff version',async t=>{
 const f=await fixture(t),saved=await screen(f);const edited=JSON.parse(await fs.readFile(saved.path,'utf8'));edited.screening.summary='Human clarified the affected routing';await fs.writeFile(saved.path,JSON.stringify(edited));
 const packet=await daily.dailyReviewPacket(f.o,{...f.id,stage:'reevaluate'});assert.equal(packet.screening.summary,edited.screening.summary);
 const result=await daily.finishDailyItem(f.o,{...f.id,decision:'no-revision-needed',reason:'Existing knowledge remains accurate',screening_sha256:packet.screening_sha256,knowledge_review:f.review});
 const output=JSON.parse(await fs.readFile(result.path,'utf8'));assert.equal(output.screening_sha256,digest(JSON.stringify(edited)));assert.equal(output.decision,'no-revision-needed');
 assert.equal(await fs.readFile(path.join(f.o.workspaceRoot,f.review[0].path),'utf8'),'# Knowledge\n');
 await assert.rejects(daily.finishDailyItem(f.o,{...f.id,decision:'failed',reason:'retry'}),/finalized/);
});
test('reevaluation cannot bypass screening or use a stale edited handoff',async t=>{
 const f=await fixture(t);
 await assert.rejects(daily.dailyReviewPacket(f.o,{...f.id,stage:'reevaluate'}),/screen|ENOENT/i);
 await assert.rejects(daily.finishDailyItem(f.o,{...f.id,decision:'proposed',reason:'bypass',screening:f.screening,proposal:{}}));
 const saved=await screen(f),p=await daily.dailyReviewPacket(f.o,{...f.id,stage:'reevaluate'});
 const a=JSON.parse(await fs.readFile(saved.path,'utf8'));a.screening.summary='Changed after packet';await fs.writeFile(saved.path,JSON.stringify(a));
 await assert.rejects(daily.finishDailyItem(f.o,{...f.id,decision:'no-revision-needed',reason:'stale',screening_sha256:p.screening_sha256,knowledge_review:f.review}),/fingerprint|handoff/i);
 await daily.finishDailyItem(f.o,{...f.id,decision:'failed',reason:'Stale handoff; no retry'});
});
test('no-impact screening terminates without invoking reevaluation',async t=>{
 const f=await fixture(t);f.screening.impact='none';await screen(f);
 await assert.rejects(daily.dailyReviewPacket(f.o,{...f.id,stage:'reevaluate'}),/impact|reevaluation/i);
 const result=await daily.finishDailyItem(f.o,{...f.id,decision:'no-impact',reason:'Formatting only'});assert.equal(result.status,'no-impact');
 await assert.rejects(fs.access(path.join(f.o.store,'stages/02-reevaluate/output',f.id.item_id+'.json')));
});
test('stage handoffs reject invented evidence, identity edits, wrong owners and next-day execution',async t=>{
 const f=await fixture(t),bad=structuredClone(f.screening);bad.evidence[0].quote='invented';
 await assert.rejects(daily.recordDailyScreening(f.o,{...f.id,screening:bad}),/quote/);
 await assert.rejects(daily.recordDailyScreening({...f.o,chat:'other'},{...f.id,screening:f.screening}),/owner/);
 await assert.rejects(daily.recordDailyScreening({...f.o,now:'2026-11-17T15:00:00Z'},{...f.id,screening:f.screening}),/owner/);
 const saved=await screen(f),a=JSON.parse(await fs.readFile(saved.path,'utf8'));a.item_id='0'.repeat(64);await fs.writeFile(saved.path,JSON.stringify(a));
 await assert.rejects(daily.dailyReviewPacket(f.o,{...f.id,stage:'reevaluate'}),/identity/);
});
test('proposals persist separately and cannot write application or knowledge files',async t=>{
 const f=await fixture(t);await screen(f);const p=await daily.dailyReviewPacket(f.o,{...f.id,stage:'reevaluate'});
 const input={...f.id,decision:'proposed',reason:'New routing explanation needed',screening_sha256:p.screening_sha256,knowledge_review:f.review,proposal:{summary:'Add a note',revisions:[{target:'order-management/.memory/new.md',operation:'create',before_sha256:null,proposed_text:'Proposed routing explanation',reason:'New source routing'}],uncertainties:['Synthetic source scope only']}};
 const invalid=structuredClone(input);invalid.proposal.revisions[0].target='src/app.cs';await assert.rejects(daily.finishDailyItem(f.o,invalid),/\.memory/);
 const result=await daily.finishDailyItem(f.o,input);assert.deepEqual(JSON.parse(await fs.readFile(result.path,'utf8')).proposal,input.proposal);
 await assert.rejects(fs.access(path.join(f.o.workspaceRoot,'order-management/.memory/new.md')));
});
test('screening rejects revision payloads nested in the assessment',async t=>{
 const f=await fixture(t);f.screening.revisions=[{target:'note.md',proposed_text:'not screening'}];
 await assert.rejects(screen(f),/revision|screening/i);
});
test('deleting an output does not permit repeating its recorded screening attempt',async t=>{
 const f=await fixture(t),saved=await screen(f);await fs.unlink(saved.path);
 await assert.rejects(screen(f),/EEXIST/);
 await daily.finishDailyItem(f.o,{...f.id,decision:'failed',reason:'Handoff deleted; no recovery'});
});
test('completion preserves the consumed handoff even if the editable output later changes',async t=>{
 const f=await fixture(t),saved=await screen(f),packet=await daily.dailyReviewPacket(f.o,{...f.id,stage:'reevaluate'});
 const original=await fs.readFile(saved.path,'utf8');
 await daily.finishDailyItem(f.o,{...f.id,decision:'no-revision-needed',reason:'Existing knowledge remains accurate',screening_sha256:packet.screening_sha256,knowledge_review:f.review});
 await fs.writeFile(saved.path,'human edited after completion');
 assert.equal(await fs.readFile(path.join(f.o.store,'snapshots',packet.screening_sha256+'.json'),'utf8'),original);
});
test('reevaluation requires consulted knowledge and rejects proposals for no-revision-needed',async t=>{
 const f=await fixture(t);await screen(f);const packet=await daily.dailyReviewPacket(f.o,{...f.id,stage:'reevaluate'});
 const a={...f.id,decision:'no-revision-needed',reason:'Investigated',screening_sha256:packet.screening_sha256,knowledge_review:[]};
 await assert.rejects(daily.finishDailyItem(f.o,a),/reviewed knowledge/);
 a.knowledge_review=f.review;a.proposal={};await assert.rejects(daily.finishDailyItem(f.o,a),/cannot include/);
 a.proposal=undefined;a.knowledge_review[0].sha256='0'.repeat(64);await assert.rejects(daily.finishDailyItem(f.o,a),/fingerprint/);
});
test('reevaluation rejects stale targets and malformed proposal batches',async t=>{
 const f=await fixture(t);await screen(f);const packet=await daily.dailyReviewPacket(f.o,{...f.id,stage:'reevaluate'});
 const a={...f.id,decision:'proposed',reason:'Routing update',screening_sha256:packet.screening_sha256,knowledge_review:f.review,proposal:{summary:'Update',revisions:[{target:'order-management/.memory/new.md',operation:'create',before_sha256:null,proposed_text:'New knowledge',reason:'Source changed'}],uncertainties:[]}};
 const cases=[x=>{delete x.proposal;},x=>{x.proposal.revisions.push({...x.proposal.revisions[0]});},x=>{x.proposal.revisions[0].operation='revise';},x=>{x.proposal.revisions[0].operation='overwrite';},x=>{x.proposal.revisions[0].proposed_text='';},x=>{x.proposal.revisions[0]={target:f.review[0].path,operation:'retire',before_sha256:f.review[0].sha256,proposed_text:'not null',reason:'Retire'};},x=>{x.proposal.revisions[0]={target:f.review[0].path,operation:'revise',before_sha256:'0'.repeat(64),proposed_text:'Revision',reason:'Source changed'};}];
 for(const mutate of cases){const bad=structuredClone(a);mutate(bad);await assert.rejects(daily.finishDailyItem(f.o,bad));}
 await daily.finishDailyItem(f.o,{...f.id,decision:'failed',reason:'Test finalization after rejected fixtures'});
});
test('screening rejects malformed ranges, too many sources and out-of-scope knowledge',async t=>{
 const f=await fixture(t);
 const cases=[s=>{s.evidence[0].end_line=1000;},s=>{s.evidence[0].side='unknown';},s=>{s.knowledge_review=Array.from({length:31},()=>f.review[0]);},s=>{s.knowledge_review=[{...f.review[0],path:null}];},s=>{s.knowledge_review=[{...f.review[0],path:path.join(f.o.workspaceRoot,'application.cs')}];},s=>{s.knowledge_review=[{...f.review[0],path:'order-management/.memory/maintenance/config.json'}];}];
 for(const mutate of cases){const s=structuredClone(f.screening);mutate(s);await assert.rejects(daily.recordDailyScreening(f.o,{...f.id,screening:s}));}
});
test('central knowledge retirement remains a proposal and absolute outside targets are rejected',async t=>{
 const f=await fixture(t);f.o.homeDir=path.join(f.o.workspaceRoot,'home');const directory=path.join(f.o.homeDir,'.council/memory/knowledge');await fs.mkdir(directory,{recursive:true});
 const target=path.join(directory,'old.md');await fs.writeFile(target,'Historical note');await screen(f);
 const packet=await daily.dailyReviewPacket(f.o,{...f.id,stage:'reevaluate'});
 const a={...f.id,decision:'proposed',reason:'Retirement candidate',screening_sha256:packet.screening_sha256,knowledge_review:f.review,proposal:{summary:'Retire old note',revisions:[{target,operation:'retire',before_sha256:digest('Historical note'),proposed_text:null,reason:'Historical only'}],uncertainties:[]}};
 const bad=structuredClone(a);bad.proposal.revisions[0].target=path.join(f.o.workspaceRoot,'application.cs');await assert.rejects(daily.finishDailyItem(f.o,bad),/scope|relative/);
 await daily.finishDailyItem(f.o,a);assert.equal(await fs.readFile(target,'utf8'),'Historical note');
});
test('CLI routes screen, stage packets and finalization through the persistent files',async t=>{
 // The production CLI uses the real clock; isolate its run from fixed-clock unit fixtures.
 const f=await fixture(t,new Date().toISOString()),record=path.join(f.o.workspaceRoot,'assessment.json');
 const command=async(action,value)=>{await fs.writeFile(record,JSON.stringify(value));return executeCommand(['daily',action,'--workspace',f.o.workspaceRoot,'--chat',f.o.chat,'--model','codex','--record',record]);};
 const saved=JSON.parse((await command('screen',{...f.id,screening:f.screening})).output);assert.equal(saved.impact,'potential');
 const p=JSON.parse((await command('packet',{...f.id,stage:'reevaluate'})).output);assert.match(p.contract,/02-reevaluate/);
 const done=JSON.parse((await command('finish',{...f.id,decision:'no-revision-needed',reason:'Knowledge already accurate',screening_sha256:p.screening_sha256,knowledge_review:f.review})).output);assert.equal(done.status,'no-revision-needed');
 await assert.rejects(command('unknown',f.id),/Use daily/);
 await fs.writeFile(record,'x'.repeat(40001));await assert.rejects(executeCommand(['daily','screen','--workspace',f.o.workspaceRoot,'--chat',f.o.chat,'--record',record]),/Invalid daily/);
});
test('invalid or edited screening files fail closed before reevaluation',async t=>{
 const f=await fixture(t);await assert.rejects(daily.dailyReviewPacket(f.o,{...f.id,stage:'unknown'}),/stage/);
 const saved=await screen(f),original=await fs.readFile(saved.path,'utf8');
 for(const text of ['x'.repeat(40001),'null','{broken',JSON.stringify({...JSON.parse(original),schema_version:99}),JSON.stringify({...JSON.parse(original),proposal:{}})]){
  await fs.writeFile(saved.path,text);await assert.rejects(daily.dailyReviewPacket(f.o,{...f.id,stage:'reevaluate'}));
 }
 await fs.writeFile(saved.path,Buffer.from([0xff]));await assert.rejects(daily.dailyReviewPacket(f.o,{...f.id,stage:'reevaluate'}));
});
test('finish cannot substitute inline screening or mismatch the saved impact',async t=>{
 const f=await fixture(t);await screen(f);
 await assert.rejects(daily.finishDailyItem(f.o,{...f.id,decision:'no-impact',reason:'Wrong outcome'}),/conflicts/);
 await assert.rejects(daily.finishDailyItem(f.o,{...f.id,decision:'no-impact',reason:'Inline bypass',screening:f.screening}),/inline/);
 const file=path.join(f.o.store,'stages/01-screen/output',f.id.item_id+'.json'),a=JSON.parse(await fs.readFile(file,'utf8'));a.screening.impact='none';await fs.writeFile(file,JSON.stringify(a));
 await assert.rejects(daily.finishDailyItem(f.o,{...f.id,decision:'no-revision-needed',reason:'Wrong stage',screening_sha256:digest(JSON.stringify(a)),knowledge_review:f.review}),/potential/);
});
