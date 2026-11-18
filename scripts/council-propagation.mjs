/** Durable parent reevaluation work. No semantic decisions, retries or knowledge writes. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {maintenanceIO as io} from './council-daily.mjs';
import {mainlineStatus} from './council-mainline.mjs';
const encode=v=>JSON.stringify(v,null,2)+'\n';
const key=p=>process.platform==='win32'?path.resolve(p).toLowerCase():path.resolve(p);
const digest=s=>typeof s==='string'&&/^[a-f0-9]{64}$/.test(s);
const inside=(root,file)=>{const r=path.relative(key(root),key(file));return r===''||r!=='..'&&!r.startsWith('..'+path.sep)&&!path.isAbsolute(r);};
async function maybe(file){try{return await io.json(file);}catch(e){if(e.code==='ENOENT')return null;throw e;}}
async function state(o){const s=await io.settings(o);if(!s)throw Error('Knowledge maintenance disabled');return s;}
async function files(store,folder){try{return (await fs.readdir(await io.safe(store,folder))).filter(n=>/^[a-f0-9]{64}\.json$/.test(n)).sort();}catch(e){if(e.code==='ENOENT')return [];throw e;}}
async function collection(o,reference){
 if(typeof reference!=='string'||path.isAbsolute(reference)||!reference.replaceAll('\\','/').endsWith('/.memory'))throw Error('Invalid collection root');
 return io.safe(o.workspaceRoot,reference);
}
async function routes(o,s){
 const config=s.config.propagation;if(!config?.enabled)return null;
 if(config.enabled!==true||!Array.isArray(config.collections)||!config.collections.length||config.collections.length>100)throw Error('Invalid propagation configuration');
 const rows=[],seen=new Set();
 for(const row of config.collections){
  const absolute=await collection(o,row.root);if(seen.has(key(absolute)))throw Error('Duplicate collection root');seen.add(key(absolute));rows.push({...row,absolute});
 }
 for(const row of rows){
  if(row.parent!==null){const parent=await collection(o,row.parent);if(!seen.has(key(parent)))throw Error('Parent collection is not registered');}
  if(rows.some(other=>other!==row&&(inside(row.absolute,other.absolute)||inside(other.absolute,row.absolute))))throw Error('Overlapping collections');
  const visited=new Set();let at=row;
  while(at){if(visited.has(key(at.absolute)))throw Error('Propagation routes contain a cycle');visited.add(key(at.absolute));at=at.parent===null?null:rows.find(r=>key(r.absolute)===key(path.resolve(o.workspaceRoot,at.parent)));}
 }
 return rows;
}
async function ownerRoute(o,rows,target){
 const file=await io.knowledgePath(o,target);return rows.find(r=>inside(r.absolute,file))||null;
}
async function receipt(o,s,itemId){
 if(!digest(itemId))throw Error('Invalid source acceptance identity');
 const file=await io.safe(s.store,`proposals/decisions/${itemId}.json`),bytes=await fs.readFile(file),value=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
 if(value.status!=='accepted'||value.item_id!==itemId||!Array.isArray(value.changes))throw Error('Source is not a completed acceptance');
 return {bytes,value,sha256:io.hash(bytes)};
}
export async function enqueuePropagation(o,input){
 const s=await state(o);if(!s.config.propagation?.enabled)return {status:'disabled',events:[]};
 const accepted=await receipt(o,s,input.item_id),directory=await io.safe(s.store,'propagation/enqueues');await fs.mkdir(directory,{recursive:true});
 const file=await io.safe(directory,input.item_id+'.json'),record={schema_version:1,item_id:input.item_id,source_receipt_sha256:accepted.sha256,status:'failed',reason:'completion-not-recorded',events:[],unmapped:[],terminal:[],started_at:io.time(o)};
 try{await fs.writeFile(file,encode(record),{flag:'wx'});}catch(e){if(e.code==='EEXIST')return {status:'already-attempted',item_id:input.item_id,events:[]};throw e;}
 try{
  const rows=await routes(o,s),events=await io.safe(s.store,'propagation/events');await fs.mkdir(events,{recursive:true});
  for(const change of accepted.value.changes){
   const route=await ownerRoute(o,rows,change.target);
   if(!route){record.unmapped.push(change.target);continue;}
   if(route.parent===null){record.terminal.push(change.target);continue;}
   if(path.extname(change.target).toLowerCase()!=='.md'||!digest(change.after_sha256)||change.before_sha256!==null&&!digest(change.before_sha256))throw Error('Invalid accepted knowledge version');
   for(const sha of [change.before_sha256,change.after_sha256])if(sha!==null)await io.snapshot(s.store,sha);
   const event_id=io.hash(encode({source_receipt_sha256:accepted.sha256,target:key(await io.knowledgePath(o,change.target)),parent:key(path.resolve(o.workspaceRoot,route.parent))}));
   const event={schema_version:1,event_id,source_item_id:input.item_id,source_receipt_sha256:accepted.sha256,child:route.root,parent:route.parent,change,accepted_at:accepted.value.finished_at,queued_at:io.time(o),queued_day:io.day(o,s.config.time_zone)};
   await fs.writeFile(await io.safe(events,event_id+'.json'),encode(event),{flag:'wx'});record.events.push(event_id);await io.atomic(file,record);
  }
  record.status=record.events.length?'queued':record.unmapped.length?'unmapped':'terminal';delete record.reason;
 }catch{record.status='failed';record.reason='propagation-not-queued-or-incomplete';}
 record.finished_at=io.time(o);await io.atomic(file,record);return record;
}
async function eventRecord(o,s,id){
 if(!digest(id))throw Error('Invalid propagation identity');const event=await io.json(await io.safe(s.store,`propagation/events/${id}.json`));
 if(event.event_id!==id||!digest(event.source_receipt_sha256)||!digest(event.source_item_id)||!/^\d{4}-\d{2}-\d{2}$/.test(event.queued_day))throw Error('Invalid propagation record');
 const rows=await routes(o,s);if(!rows)throw Error('Propagation disabled');const row=rows.find(r=>r.root===event.child);
 if(!row||row.parent!==event.parent||!(await ownerRoute(o,rows,event.change.target))||!inside(row.absolute,await io.knowledgePath(o,event.change.target)))throw Error('Propagation route changed or invalid');
 const accepted=await receipt(o,s,event.source_item_id);if(accepted.sha256!==event.source_receipt_sha256||!accepted.value.changes.some(c=>encode(c)===encode(event.change)))throw Error('Accepted source version changed');
 const expected=io.hash(encode({source_receipt_sha256:accepted.sha256,target:key(await io.knowledgePath(o,event.change.target)),parent:key(path.resolve(o.workspaceRoot,event.parent))}));
 if(expected!==id)throw Error('Propagation identity mismatch');
 return event;
}
async function validateLineage(o,s,item,seen){
 if(seen.size>=32||seen.has(item.item_id))throw Error('Evidence lineage is cyclic or too deep');seen.add(item.item_id);
 if(item.source_kind==='propagation'){
  const event=await eventRecord(o,s,item.propagation_event);
  if(item.document!==event.change.target||item.before!==event.change.before_sha256||item.after!==event.change.after_sha256||item.parent_collection!==event.parent)throw Error('Propagation work identity mismatch');
  const bytes=await fs.readFile(await io.knowledgePath(o,event.change.target));if(io.hash(bytes)!==event.change.after_sha256)throw Error('Accepted child knowledge changed');
  for(const sha of [item.before,item.after])if(sha!==null)await io.snapshot(s.store,sha);
  const origin=await io.json(await io.safe(s.store,`work/${event.source_item_id}.json`));if(!origin.finalized||origin.status!=='proposed')throw Error('Source proposal history unavailable');
  await validateLineage(o,s,origin,seen);return event;
 }
 const file=await io.safe(o.workspaceRoot,item.document);let actual;
 try{actual=io.hash(await fs.readFile(file));}catch(e){if(e.code!=='ENOENT')throw e;actual='deleted';}
 if(actual!==item.after)throw Error('Original integrated evidence changed');
 await io.snapshot(s.store,item.before);await io.snapshot(s.store,item.after);
 if(s.config.mainline?.enabled){const repo=s.config.mainline.repositories.find(r=>r.documents.includes(item.document));if(!repo||(await mainlineStatus(o,{repo:repo.name})).status!=='current')throw Error('Original mainline freshness unresolved');}
}
export async function validatePropagationSource(o,item){const s=await state(o);return validateLineage(o,s,item,new Set());}
export async function validatePropagationTargets(o,item,proposal){
 if(item.source_kind!=='propagation'||!proposal)return;
 const parent=await collection(o,item.parent_collection);
 for(const revision of proposal.revisions)if(!inside(parent,await io.knowledgePath(o,revision.target)))throw Error('Propagation proposals may target only their parent collection');
}
export async function validateParentReview(o,item,review){
 if(item.source_kind!=='propagation')return;
 const index=path.join(await collection(o,item.parent_collection),'CONTEXT.md');let found=false;
 for(const entry of review)if(key(await io.knowledgePath(o,entry.path))===key(index))found=true;
 if(!found)throw Error('Propagation requires a parent index knowledge review');
}
export async function assignPropagation(o,run){
 const s=await state(o);if(!await routes(o,s))return;
 run.propagation_items=[];const attempts=await io.safe(s.store,'propagation/attempts');await fs.mkdir(attempts,{recursive:true});
 for(const name of await files(s.store,'propagation/events')){
  const id=name.slice(0,-5),attempt=await io.safe(attempts,name),marker={event_id:id,run_id:run.run_id,owner:run.owner,status:'failed',reason:'completion-not-recorded',attempted_at:io.time(o)};let event,claimed=false;
  try{await fs.access(attempt);continue;}catch(e){if(e.code!=='ENOENT')throw e;}
  try{
   event=await io.json(await io.safe(s.store,'propagation/events/'+name));if(event.queued_day>=run.run_id)continue;
   try{await fs.writeFile(attempt,encode(marker),{flag:'wx'});claimed=true;}catch(e){if(e.code==='EEXIST')continue;throw e;}
   await eventRecord(o,s,id);
   const item={schema_version:1,run_id:run.run_id,item_id:id,source_kind:'propagation',propagation_event:id,parent_collection:event.parent,document:event.change.target,before:event.change.before_sha256,after:event.change.after_sha256,status:'failed',reason:'completion-not-recorded',finalized:false};
   await fs.writeFile(await io.safe(s.store,`work/${id}.json`),encode(item),{flag:'wx'});run.items.push(id);run.propagation_items.push(id);
   await io.atomic(await io.safe(s.store,`runs/${run.run_id}.json`),run);
  }catch{
   if(!claimed)try{await fs.writeFile(attempt,encode(marker),{flag:'wx'});}catch(e){if(e.code==='EEXIST')continue;}
   run.failures.push({propagation_event:id,reason:'propagation-assignment-failed'});await io.atomic(await io.safe(s.store,`runs/${run.run_id}.json`),run);
  }
 }
}
async function eventStatus(o,s,event){
 const attempt=await maybe(await io.safe(s.store,`propagation/attempts/${event.event_id}.json`));if(!attempt)return 'waiting';
 const work=await maybe(await io.safe(s.store,`work/${event.event_id}.json`));
 if(!work?.finalized){const today=io.day(o,s.config.time_zone);return attempt.run_id===today?'pending':'failed';}
 if(work.status!=='proposed')return work.status;
 const decision=await maybe(await io.safe(s.store,`proposals/decisions/${event.event_id}.json`));return decision?.status||'proposed';
}
async function inventory(o,s){
 const events=[],failures=[],enqueues=[];if(!await routes(o,s))return {events,failures,enqueues};
 for(const name of await files(s.store,'propagation/events')){
  try{const event=await eventRecord(o,s,name.slice(0,-5));events.push({...event,status:await eventStatus(o,s,event)});}catch{failures.push({event_id:name.slice(0,-5),reason:'Propagation record unavailable or invalid'});}
 }
 for(const name of await files(s.store,'proposals/decisions')){
  try{
   const r=await io.json(await io.safe(s.store,'proposals/decisions/'+name));if(r.status!=='accepted'||!r.propagation_expected)continue;
   const enqueue=await maybe(await io.safe(s.store,'propagation/enqueues/'+name));
   if(!enqueue||enqueue.status==='failed')enqueues.push({item_id:r.item_id,status:'failed',targets:r.changes.map(c=>c.target)});
   else if(enqueue.unmapped?.length)enqueues.push({item_id:r.item_id,status:'unmapped',targets:enqueue.unmapped});
  }catch{failures.push({reason:'Propagation enqueue history unavailable or invalid'});}
 }
 return {events,failures,enqueues};
}
export async function listPropagation(o,input={}){
 const s=await state(o),all=await inventory(o,s),limit=input.limit??50,offset=input.offset??0;
 if(!Number.isInteger(limit)||limit<1||limit>200||!Number.isInteger(offset)||offset<0)throw Error('Invalid propagation page');
 return {...all,events:all.events.slice(offset,offset+limit),total:all.events.length,offset};
}
export async function propagationStatus(o,input){
 const s=await state(o),rows=await routes(o,s);if(!rows)return {status:'disabled',events:[],failures:0};
 const target=await io.knowledgePath(o,input.target),all=await inventory(o,s),relevant=all.events.filter(e=>inside(path.resolve(o.workspaceRoot,e.parent),target));
 const unresolved=relevant.filter(e=>!['no-impact','no-revision-needed','accepted','rejected'].includes(e.status));
 let failedEnqueues=0;for(const e of all.enqueues.filter(e=>e.status==='failed'))for(const reference of e.targets){const route=await ownerRoute(o,rows,reference);if(route?.parent&&inside(path.resolve(o.workspaceRoot,route.parent),target)){failedEnqueues++;break;}}
 const failures=all.failures.length+failedEnqueues;
 return {status:failures||unresolved.some(e=>e.status==='failed')?'parent-review-failed':unresolved.length?'pending-parent-review':'no-pending-parent-review',events:relevant.map(e=>({event_id:e.event_id,status:e.status,child:e.child,parent:e.parent})),failures};
}
