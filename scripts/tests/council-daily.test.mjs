import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {dailyScan,finishDailyItem} from '../council-daily.mjs';
import * as daily from '../council-daily.mjs';
import {readStartupContext} from '../council-memoryforge.mjs';
async function fixture(t){
 const parent=path.resolve(import.meta.dirname,'../../work/daily-tests');await fs.mkdir(parent,{recursive:true});
 const root=await fs.mkdtemp(path.join(parent,'case-'));t.after(async()=>{assert.equal(path.dirname(root),parent);await fs.rm(root,{recursive:true,force:true});});
 const store=path.join(root,'order-management/.memory/maintenance');await fs.mkdir(store,{recursive:true});
 await fs.mkdir(path.join(root,'docs'));await fs.writeFile(path.join(root,'docs/a.md'),'first');
 await fs.writeFile(path.join(store,'config.json'),JSON.stringify({schema_version:1,time_zone:'America/New_York',documents:['docs/a.md']}));
 return {workspaceRoot:root,chat:'first',actor:'codex',now:'2026-11-16T15:00:00Z',store};
}
test('one atomic daily claim across clients, with durable work before checkpoints',async t=>{
 const o=await fixture(t);const results=await Promise.all([dailyScan(o),dailyScan({...o,actor:'gemini',chat:'second'})]);
 assert.equal(results.filter(r=>r.status==='claimed').length,1);assert.equal(results.filter(r=>r.status==='already-attempted').length,1);
 const claimed=results.find(r=>r.status==='claimed');assert.equal(claimed.items.length,1);
 const item=JSON.parse(await fs.readFile(path.join(o.store,'work',claimed.items[0]+'.json'),'utf8'));
 assert.equal(item.status,'failed');assert.equal(item.finalized,false);assert.equal(item.reason,'completion-not-recorded');
 const cp=JSON.parse(await fs.readFile(path.join(o.store,'checkpoints.json'),'utf8'));assert.ok(cp.documents['docs/a.md']);
});
test('failed work never replays; next day scans only new document changes',async t=>{
 const o=await fixture(t),run=await dailyScan(o);
 await finishDailyItem(o,{run_id:run.run_id,item_id:run.items[0],decision:'failed',reason:'screen failed'});
 await assert.rejects(finishDailyItem(o,{run_id:run.run_id,item_id:run.items[0],decision:'no-impact',reason:'retry'}),/finalized/);
 const next=await dailyScan({...o,now:'2026-11-17T15:00:00Z'});assert.equal(next.items.length,0);
 await fs.writeFile(path.join(o.workspaceRoot,'docs/a.md'),'second');
 const later=await dailyScan({...o,now:'2026-11-18T15:00:00Z'});assert.equal(later.items.length,1);
});

test('Eastern calendar date controls once-per-day behavior and interruption is not resumed',async t=>{
 const o=await fixture(t);await dailyScan({...o,now:'2026-11-17T03:59:00Z'});
 assert.equal((await dailyScan({...o,now:'2026-11-17T04:59:00Z'})).status,'already-attempted');
 assert.equal((await dailyScan({...o,now:'2026-11-17T05:01:00Z'})).status,'claimed');
});
test('bad document paths fail individually and unchanged inaccessible inputs are not replayed',async t=>{
 const o=await fixture(t);await fs.writeFile(path.join(o.store,'config.json'),JSON.stringify({schema_version:1,time_zone:'America/New_York',documents:['../outside','docs/a.md']}));
 const r=await dailyScan(o);assert.equal(r.failures.length,1);assert.equal(r.items.length,1);
 assert.equal((await dailyScan(o)).status,'already-attempted');
});
test('malformed configuration consumes the day instead of retrying initialization',async t=>{
 const o=await fixture(t);await fs.writeFile(path.join(o.store,'config.json'),'broken JSON');
 assert.equal((await dailyScan(o)).status,'failed');
 assert.equal((await dailyScan(o)).status,'already-attempted');
});
test('real onboarding hands semantic work only to the first chat across clients',async t=>{
 const o=await fixture(t),options={...o,homeDir:path.join(o.workspaceRoot,'home'),username:'test',cwd:o.workspaceRoot};
 const first=await readStartupContext(options);assert.match(first,/maintenance available/);assert.match(first,/daily-maintenance.md/);
 await daily.claimDaily(options,{run_id:"2026-11-16"});
 const second=await readStartupContext({...options,chat:'other',actor:'gemini'});assert.doesNotMatch(second,/maintenance assigned to this chat/);
 assert.match(second,/Start fresh/);
});
test('review packet exposes verified line-numbered snapshots and rejects tampering',async t=>{
 const o=await fixture(t),r=await dailyScan(o);assert.equal(typeof daily.dailyReviewPacket,'function');
 const p=await daily.dailyReviewPacket(o,{run_id:r.run_id,item_id:r.items[0]});
 assert.equal(p.before,null);assert.deepEqual(p.after.lines,[{number:1,text:'first'}]);
 const file=path.join(o.store,'snapshots',p.after.sha256+'.md');await fs.writeFile(file,'tampered');
 await assert.rejects(daily.dailyReviewPacket(o,{run_id:r.run_id,item_id:r.items[0]}),/fingerprint/);
});




test('removed documents retain their before evidence in the next daily review packet',async t=>{
 const o=await fixture(t);await dailyScan(o);await fs.unlink(path.join(o.workspaceRoot,'docs/a.md'));
 const tomorrow={...o,now:'2026-11-17T15:00:00Z'},r=await dailyScan(tomorrow);
 const p=await daily.dailyReviewPacket(tomorrow,{run_id:r.run_id,item_id:r.items[0]});
 assert.equal(p.after,null);assert.equal(p.before.lines[0].text,'first');
});


test('review packets reject unknown items, wrong owners, malformed hashes and completed work',async t=>{
 const o=await fixture(t),r=await dailyScan(o),identity={run_id:r.run_id,item_id:r.items[0]};
 await assert.rejects(daily.dailyReviewPacket(o,{...identity,item_id:'bad'}),/identity/);
 await assert.rejects(daily.dailyReviewPacket({...o,chat:'other'},identity),/owner/);
 await assert.rejects(daily.dailyReviewPacket(o,{...identity,item_id:'0'.repeat(64)}),/Unknown/);
 await finishDailyItem(o,{...identity,decision:'failed',reason:'Stopped'});await assert.rejects(daily.dailyReviewPacket(o,identity),/finalized/);
 const tomorrow={...o,now:'2026-11-17T15:00:00Z'};await fs.writeFile(path.join(o.workspaceRoot,'docs/a.md'),'second');const next=await dailyScan(tomorrow);
 const file=path.join(o.store,'work',next.items[0]+'.json'),item=JSON.parse(await fs.readFile(file,'utf8'));item.after='../outside';await fs.writeFile(file,JSON.stringify(item));
 await assert.rejects(daily.dailyReviewPacket(tomorrow,{run_id:next.run_id,item_id:next.items[0]}),/fingerprint/);
});
