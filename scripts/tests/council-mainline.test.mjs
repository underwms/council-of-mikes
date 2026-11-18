import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {readFileSync,existsSync} from 'node:fs';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {createHash} from 'node:crypto';
import * as daily from '../council-daily.mjs';
import {executeCommand} from '../council-codex.mjs';
const exec=promisify(execFile),hash=b=>createHash('sha256').update(b).digest('hex');
const git=async(cwd,...args)=>(await exec('git',['-C',cwd,...args],{encoding:'utf8',windowsHide:true})).stdout.trim();
async function fixture(t,now='2026-11-16T15:00:00Z'){
 const parent=path.resolve(import.meta.dirname,'../../work/mainline-tests');await fs.mkdir(parent,{recursive:true});
 const root=await fs.mkdtemp(path.join(parent,'case-'));t.after(async()=>{assert.equal(path.dirname(root),parent);await fs.rm(root,{recursive:true,force:true});});
 const remote=path.join(root,'origin.git'),publisher=path.join(root,'publisher'),workspace=path.join(root,'workspace');
 await fs.mkdir(remote);await git(remote,'init','--bare');await fs.mkdir(publisher);await git(publisher,'init','-b','main');
 await fs.writeFile(path.join(publisher,'api.cs'),'Established v1\n');await git(publisher,'add','api.cs');await git(publisher,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Initial fixture');
 const initial=await git(publisher,'rev-parse','HEAD');await git(publisher,'branch','master');await git(publisher,'remote','add','origin',remote);await git(publisher,'push','origin','main','master');
 await fs.mkdir(workspace);const repo=path.join(workspace,'repo');await git(workspace,'clone','--branch','main',remote,repo);
 await git(repo,'checkout','-b','feature');await fs.writeFile(path.join(repo,'api.cs'),'Unmerged experiment\n');await fs.writeFile(path.join(repo,'untracked.txt'),'Keep this');
 const store=path.join(workspace,'order-management/.memory/maintenance');await fs.mkdir(store,{recursive:true});await fs.mkdir(path.join(workspace,'docs'));
 await fs.writeFile(path.join(workspace,'docs/api.md'),'# API\nEstablished v1\n');
 const repository={name:'sample',path:'repo',branch:'main',baseline_commit:initial,baseline_checked_on:'2026-11-16',baseline_documents:{'docs/api.md':hash('# API\nEstablished v1\n')},documents:['docs/api.md']};
 await fs.writeFile(path.join(store,'config.json'),JSON.stringify({schema_version:1,time_zone:'America/New_York',documents:repository.documents,mainline:{enabled:true,repositories:[repository]}}));
 const o={workspaceRoot:workspace,homeDir:path.join(root,'home'),actor:'codex',chat:'first',now};
 return {o,root,store,repo,publisher,initial,repository};
}
async function integrate(f,text='Established v2\n',branch='main'){
 await git(f.publisher,'checkout',branch);await fs.writeFile(path.join(f.publisher,'api.cs'),text);await git(f.publisher,'add','api.cs');await git(f.publisher,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Integrated fixture change');await git(f.publisher,'push','origin',branch);return git(f.publisher,'rev-parse','HEAD');
}
async function prepare(f){const claim=await daily.dailyScan(f.o);const m=await import('../council-mainline.mjs');const result=await m.scanMainline(f.o,{run_id:claim.run_id});return {m,claim,result,id:{run_id:claim.run_id,refresh_id:result.refresh_items[0]}};}
test('daily claim waits for mainline refresh before observing document changes',async t=>{
 const f=await fixture(t);await integrate(f);const claim=await daily.dailyScan(f.o);
 assert.equal(claim.mainline_pending,true);assert.equal(claim.items.length,0);
 await assert.rejects(fs.access(path.join(f.store,'checkpoints.json')));
 assert.equal((await daily.dailyScan({...f.o,chat:'other'})).status,'already-attempted');
});
test('network fetch observes both branches and documents main without altering feature work',async t=>{
 const f=await fixture(t),commit=await integrate(f),{m,id,result}=await prepare(f);
 assert.equal(result.refresh_items.length,1);const p=await m.mainlinePacket(f.o,id);
 assert.equal(p.commit,commit);assert.equal(p.branch,'main');assert.deepEqual(p.changed_paths,['api.cs']);
 const source=await m.mainlineSource(f.o,{...id,path:'api.cs'});assert.equal(source.text,'Established v2\n');
 assert.equal(await git(f.repo,'rev-parse','refs/memoryforge/mainline/master'),f.initial);
 assert.equal(await git(f.repo,'branch','--show-current'),'feature');assert.equal(await fs.readFile(path.join(f.repo,'api.cs'),'utf8'),'Unmerged experiment\n');assert.equal(await fs.readFile(path.join(f.repo,'untracked.txt'),'utf8'),'Keep this');
});
test('updated documentation enters the existing scanner only after all refresh items finish',async t=>{
 const f=await fixture(t);await integrate(f);const {m,id}=await prepare(f),p=await m.mainlinePacket(f.o,id);
 await assert.rejects(daily.continueDailyScan(f.o,{run_id:id.run_id}),/refresh|mainline/i);
 const stage=path.join(f.store,'stages/00-mainline-refresh/output',id.refresh_id+'.md');await fs.mkdir(path.dirname(stage),{recursive:true});await fs.writeFile(stage,'# API\nEstablished v2\n');
 await m.finishMainline(f.o,{...id,decision:'updated',reason:'Integrated API behavior changed',documents:[{path:'docs/api.md',staged_path:path.relative(f.o.workspaceRoot,stage),before_sha256:p.documents[0].sha256}],evidence:[{path:'api.cs',revision:p.commit,sha256:hash('Established v2\n')}]});
 const scan=await daily.continueDailyScan(f.o,{run_id:id.run_id});assert.equal(scan.items.length,1);
 await assert.rejects(daily.continueDailyScan(f.o,{run_id:id.run_id}),/exist|scan/i);
 assert.equal((await m.mainlineStatus(f.o,{repo:'sample'})).status,'current');
});
test('no-impact source review preserves documents and never retries the same revision',async t=>{
 const f=await fixture(t);await integrate(f,'Established v1\n// Internal rename\n');const {m,id}=await prepare(f);const before=await fs.readFile(path.join(f.o.workspaceRoot,'docs/api.md'));
 await m.finishMainline(f.o,{...id,decision:'no-doc-change',reason:'Only an internal name changed',evidence:[{path:'api.cs',revision:await git(f.publisher,'rev-parse','HEAD'),sha256:hash('Established v1\n// Internal rename\n')}]});
 await daily.continueDailyScan(f.o,{run_id:id.run_id});assert.deepEqual(await fs.readFile(path.join(f.o.workspaceRoot,'docs/api.md')),before);
 const tomorrow={...f.o,now:'2026-11-17T15:00:00Z'},next=await daily.dailyScan(tomorrow),r=await m.scanMainline(tomorrow,{run_id:next.run_id});assert.deepEqual(r.refresh_items,[]);
 await daily.continueDailyScan(tomorrow,{run_id:next.run_id});
 assert.equal((await m.mainlineStatus(tomorrow,{repo:'sample'})).status,'current');
});
test('failed revisions stay failed while unchanged feature edits do not trigger mainline work',async t=>{
 const f=await fixture(t);await integrate(f);const {m,id}=await prepare(f);
 await m.finishMainline(f.o,{...id,decision:'failed',reason:'Source investigation unavailable'});await daily.continueDailyScan(f.o,{run_id:id.run_id});
 const tomorrow={...f.o,now:'2026-11-17T15:00:00Z'},next=await daily.dailyScan(tomorrow),r=await m.scanMainline(tomorrow,{run_id:next.run_id});assert.deepEqual(r.refresh_items,[]);
 assert.equal((await m.mainlineStatus(tomorrow,{repo:'sample'})).status,'needs-review');
 await assert.rejects(m.finishMainline(tomorrow,{...id,decision:'failed',reason:'retry'}),/owner|day|final/i);
});
test('unchanged mainline stays current despite dirty feature source and docs outside a refresh are not scanned',async t=>{
 const f=await fixture(t),{m,id,result}=await prepare(f);assert.deepEqual(result.refresh_items,[]);
 assert.equal((await m.mainlineStatus(f.o,{repo:'sample'})).status,'current');
 const publicationLock=path.join(f.store,'runs',id.run_id+'.publication');await fs.writeFile(publicationLock,'busy');
 await assert.rejects(daily.continueDailyScan(f.o,{run_id:id.run_id}),/EEXIST/);await fs.unlink(publicationLock);
 const cpFile=path.join(f.store,'mainline-checkpoints.json'),cpText=await fs.readFile(cpFile,'utf8'),broken=JSON.parse(cpText);broken.repositories.sample.documented='unmerged-branch';await fs.writeFile(cpFile,JSON.stringify(broken));
 await assert.rejects(m.mainlineStatus(f.o,{repo:'sample'}),/checkpoint/i);await fs.writeFile(cpFile,cpText);
 await fs.writeFile(path.join(f.o.workspaceRoot,'docs/api.md'),'An unreviewed local explanation');
 assert.equal((await m.mainlineStatus(f.o,{repo:'sample'})).status,'needs-review');
 assert.equal((await daily.continueDailyScan(f.o,{run_id:id.run_id})).items.length,0);
});
test('configured master is fetched and used independently of main',async t=>{
 const f=await fixture(t);f.repository.branch='master';const file=path.join(f.store,'config.json'),config=JSON.parse(await fs.readFile(file,'utf8'));config.mainline.repositories=[f.repository];await fs.writeFile(file,JSON.stringify(config));
 const commit=await integrate(f,'Established on master\n','master'),{m,id}=await prepare(f),p=await m.mainlinePacket(f.o,id);
 assert.equal(p.branch,'master');assert.equal(p.commit,commit);assert.equal((await m.mainlineSource(f.o,{...id,path:'api.cs',side:'before'})).text,'Established v1\n');
 await assert.rejects(m.mainlinePacket({...f.o,chat:'other'},id),/owner/);
 await assert.rejects(m.mainlinePacket({...f.o,now:'2026-11-17T15:00:00Z'},id),/owner/);
});
test('network failures are durable and do not fall back to cached origin refs',async t=>{
 const f=await fixture(t);await git(f.repo,'remote','set-url','origin',path.join(f.root,'missing-origin.git'));
 const {m,id,result}=await prepare(f);assert.deepEqual(result.refresh_items,[]);assert.equal(result.observations.sample.status,'failed');
 assert.equal((await m.mainlineStatus(f.o,{repo:'sample'})).status,'unavailable');
 await assert.rejects(m.scanMainline(f.o,{run_id:id.run_id}),/EEXIST/);
 const done=await daily.continueDailyScan(f.o,{run_id:id.run_id});assert.equal(done.failures.length,1);assert.equal(done.items.length,0);
});
test('publication and source validation reject feature evidence, stale targets and out-of-scope replacements',async t=>{
 const f=await fixture(t),commit=await integrate(f),{m,id}=await prepare(f),p=await m.mainlinePacket(f.o,id);
 await assert.rejects(m.mainlineSource(f.o,{...id,path:'../outside'}),/path/i);
 await assert.rejects(m.mainlineSource(f.o,{...id,path:'api.cs',side:'feature'}),/side/);
 await assert.rejects(m.mainlineSource(f.o,{...id,path:'.env'}),/Sensitive/);
 const stage=path.join(f.store,'stages/00-mainline-refresh/output',id.refresh_id+'.md');await fs.mkdir(path.dirname(stage),{recursive:true});await fs.writeFile(stage,'# API\nEstablished v2\n');
 const input={...id,decision:'updated',reason:'Changed integrated API',documents:[{path:'docs/api.md',staged_path:path.relative(f.o.workspaceRoot,stage),before_sha256:p.documents[0].sha256}],evidence:[{path:'api.cs',revision:commit,sha256:hash('Established v2\n')}]};
 const changes=[x=>{x.evidence=[];},x=>{x.evidence[0].revision='a'.repeat(40);},x=>{x.evidence[0].sha256=hash('Unmerged experiment\n');},x=>{x.documents[0].path='src/api.cs';},x=>{x.documents[0].before_sha256='0'.repeat(64);},x=>{x.documents[0].staged_path='docs/api.md';},x=>{x.documents.push({...x.documents[0]});}];
 for(const mutate of changes){const bad=structuredClone(input);mutate(bad);await assert.rejects(m.finishMainline(f.o,bad));}
 await assert.rejects(fs.access(path.join(f.store,'refresh',id.refresh_id+'.final')));
 await fs.writeFile(path.join(f.o.workspaceRoot,'docs/api.md'),'Local concurrent documentation edit');await assert.rejects(m.finishMainline(f.o,input),/fingerprint/);
 await m.finishMainline(f.o,{...id,decision:'failed',reason:'Concurrent document change; no retry'});assert.equal((await daily.continueDailyScan(f.o,{run_id:id.run_id})).items.length,0);
});
test('an interrupted terminal publication stays blocked while the document scan can continue',async t=>{
 const f=await fixture(t);await integrate(f);const {m,id}=await prepare(f),packet=await m.mainlinePacket(f.o,id);
 const input={...id,decision:'no-doc-change',reason:'Fixture failure at receipt write',evidence:[{path:'api.cs',revision:packet.commit,sha256:hash('Established v2\n')}]};
 const lock=path.join(f.store,'runs',id.run_id+'.publication');await fs.writeFile(lock,'busy');
 await assert.rejects(m.finishMainline(f.o,input),/EEXIST/);await fs.unlink(lock);
 const output=path.join(f.store,'stages/00-mainline-refresh/output',id.refresh_id+'.json');await fs.mkdir(path.dirname(output),{recursive:true});await fs.writeFile(output,'occupied');
 await assert.rejects(m.finishMainline(f.o,input),/EEXIST/);
 const result=await daily.continueDailyScan(f.o,{run_id:id.run_id});assert.equal(result.items.length,0);assert.equal(result.failures[0].reason,'refresh-completion-not-recorded');
 assert.equal((await m.mainlineStatus(f.o,{repo:'sample'})).status,'needs-review');
});
test('the common CLI executes the full mainline-to-document-scan handoff',async t=>{
 const f=await fixture(t,new Date().toISOString());await integrate(f);const claim=await daily.dailyScan(f.o),record=path.join(f.root,'input.json');
 const invoke=async(action,value)=>{await fs.writeFile(record,JSON.stringify(value));return JSON.parse((await executeCommand(['daily',action,'--workspace',f.o.workspaceRoot,'--home',f.o.homeDir,'--chat',f.o.chat,'--record',record])).output);};
 const prepared=await invoke('mainline-scan',{run_id:claim.run_id}),id={run_id:claim.run_id,refresh_id:prepared.refresh_items[0]};
 const packet=await invoke('mainline-packet',id),source=await invoke('mainline-source',{...id,path:'api.cs'});
 const result=await invoke('mainline-finish',{...id,decision:'no-doc-change',reason:'CLI fixture source review; no architecture edit needed',evidence:[{path:source.path,revision:source.revision,sha256:source.sha256}]});assert.equal(result.status,'no-doc-change');
 assert.equal((await invoke('mainline-status',{repo:'sample'})).revision,packet.commit);assert.ok((await invoke('scan-documents',{run_id:claim.run_id})).items);
});
test('a date rollover during network observation cannot assign source work to yesterday',async t=>{
 const f=await fixture(t);await integrate(f);const claim=await daily.dailyScan(f.o),m=await import('../council-mainline.mjs'),runFile=path.join(f.store,'runs',claim.run_id+'.json');let rolled=false;
 Object.defineProperty(f.o,'now',{get(){rolled ||= Boolean(JSON.parse(readFileSync(runFile,'utf8')).mainline_observations.sample);return rolled?'2026-11-17T15:00:00Z':'2026-11-16T15:00:00Z';}});
 const result=await m.scanMainline(f.o,{run_id:claim.run_id});assert.equal(rolled,true);assert.deepEqual(result.refresh_items,[]);assert.equal(result.observations.sample.status,'failed');
 await assert.rejects(fs.access(path.join(f.store,'mainline-checkpoints.json')));
});
test('a date rollover at publication cannot publish yesterday documentation',async t=>{
 const f=await fixture(t);await integrate(f);const {m,id}=await prepare(f),p=await m.mainlinePacket(f.o,id);const lock=path.join(f.store,'runs',id.run_id+'.publication');let rolled=false;
 Object.defineProperty(f.o,'now',{get(){rolled ||= existsSync(lock);return rolled?'2026-11-17T15:00:00Z':'2026-11-16T15:00:00Z';}});
 await assert.rejects(m.finishMainline(f.o,{...id,decision:'no-doc-change',reason:'Late completion',evidence:[{path:'api.cs',revision:p.commit,sha256:hash('Established v2\n')}]}),/expired/);
 await assert.rejects(fs.access(lock));await assert.rejects(fs.access(path.join(f.store,'refresh',id.refresh_id+'.final')));
 assert.equal(await fs.readFile(path.join(f.o.workspaceRoot,'docs/api.md'),'utf8'),'# API\nEstablished v1\n');
});
