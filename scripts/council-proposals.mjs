/** Explicit user decisions over saved knowledge proposals. Never invoked by daily automation. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {maintenanceIO as io} from './council-daily.mjs';
import {mainlineStatus} from './council-mainline.mjs';
import {enqueuePropagation,validatePropagationSource,validatePropagationTargets,validateParentReview,propagationStatus} from './council-propagation.mjs';
const encode=v=>JSON.stringify(v,null,2)+'\n';
const decode=b=>new TextDecoder('utf-8',{fatal:true}).decode(b);
const digest=s=>typeof s==='string'&&/^[a-f0-9]{64}$/.test(s);
const pathKey=p=>process.platform==='win32'?path.resolve(p).toLowerCase():path.resolve(p);
const workspaceId=o=>io.hash(pathKey(o.workspaceRoot));
async function knowledgeTarget(o,reference){
 if(typeof reference!=='string'||path.extname(reference).toLowerCase()!=='.md')throw Error('Acceptance targets must be Markdown knowledge documents');
 const full=await io.knowledgePath(o,reference);
 if(o.homeDir){
  const relative=path.relative(path.join(o.homeDir,'.council/memory/knowledge'),full),section=relative.split(path.sep)[0].toLowerCase();
  if(['tools','workflows','baselines'].includes(section))throw Error('Collection tooling, workflow instructions and baseline history are not knowledge acceptance targets');
 }
 return full;
}
async function environment(o){
 const s=await io.settings(o);if(!s)throw Error('Knowledge maintenance disabled');return s;
}
async function optionalJson(file){try{return await io.json(file);}catch(e){if(e.code==='ENOENT')return null;throw e;}}
async function candidate(o,input){
 const s=await environment(o);
 if(!input||!/^\d{4}-\d{2}-\d{2}$/.test(input.run_id)||!digest(input.item_id))throw Error('Invalid proposal identity');
 const item=await io.json(await io.safe(s.store,`work/${input.item_id}.json`));
 if(item.run_id!==input.run_id||item.item_id!==input.item_id||!item.finalized||item.status!=='proposed')throw Error('Only finalized proposals may be reviewed');
 const file=await io.safe(s.store,`stages/02-reevaluate/output/${input.item_id}.json`),bytes=await fs.readFile(file);
 if(bytes.length>40000)throw Error('Proposal artifact too large');
 const artifact=JSON.parse(decode(bytes));
 if(artifact.run_id!==input.run_id||artifact.item_id!==input.item_id||artifact.decision!=='proposed'||artifact.screening_sha256!==item.screening_sha256)throw Error('Proposal artifact identity mismatch');
 validateShape(artifact.proposal);
 return {...s,item,file,bytes,artifact,proposal_sha256:io.hash(bytes)};
}
function validateShape(p){
 if(!p||typeof p.summary!=='string'||!p.summary.trim()||!Array.isArray(p.revisions)||!p.revisions.length||p.revisions.length>20||!Array.isArray(p.uncertainties))throw Error('Invalid knowledge proposal');
 for(const r of p.revisions){
  if(!r||typeof r.target!=='string'||!['create','revise','retire'].includes(r.operation)||typeof r.reason!=='string')throw Error('Invalid knowledge revision');
  if(r.operation==='create'?r.before_sha256!==null:!digest(r.before_sha256))throw Error('Invalid prior knowledge fingerprint');
  if(r.operation==='retire'?r.proposed_text!==null:typeof r.proposed_text!=='string'||!r.proposed_text.trim())throw Error('Invalid proposed knowledge text');
 }
}
async function snapshotBytes(store,sha,kind){
 if(!digest(sha))throw Error('Invalid snapshot identity');const bytes=await fs.readFile(await io.safe(store,`snapshots/${sha}.${kind}`));
 if(bytes.length>256*1024||io.hash(bytes)!==sha)throw Error('Snapshot fingerprint mismatch');return bytes;
}
async function currentBytes(file){try{const bytes=await fs.readFile(file);if(bytes.length>256*1024)throw Error('Knowledge document too large');decode(bytes);return bytes;}catch(e){if(e.code==='ENOENT')return null;throw e;}}
function retirement(store,reviewId,r){
 const history=path.join(store,'snapshots',r.before_sha256+'.md').replaceAll('\\','/');
 return `# Retired knowledge\n\nStatus: retired\nReview: ${reviewId}\n\n${r.reason}\n\n[Historical version](<${history}>)\n`;
}
async function plannedChanges(o,s,reviewId){
 const changes=[],seen=new Set();
 for(const r of s.artifact.proposal.revisions){
  const target=await knowledgeTarget(o,r.target),key=pathKey(target);if(seen.has(key))throw Error('Duplicate knowledge target');seen.add(key);
  const before=await currentBytes(target);if(before)await io.captureSnapshot(s.store,before,'md');
  const after=Buffer.from(r.operation==='retire'?retirement(s.store,reviewId,r):r.proposed_text,'utf8');
  if(after.length>256*1024)throw Error('Proposed knowledge too large');
  const after_sha256=await io.captureSnapshot(s.store,after,'md');
  changes.push({target:r.target,operation:r.operation,before_sha256:r.before_sha256,observed_before_sha256:before?io.hash(before):null,after_sha256,reason:r.reason});
 }
 return changes;
}
async function checkSource(o,s){
 if(s.item.source_kind==='propagation'){await validatePropagationSource(o,s.item);return {status:'current',scope:'Accepted child versions and integrated-source lineage'};}
 const bytes=await currentBytes(await io.safe(o.workspaceRoot,s.item.document)),actual=bytes?io.hash(bytes):'deleted';
 if(actual!==s.item.after)throw Error('Source document changed since proposal');
 if(s.config.mainline?.enabled){
  const repo=s.config.mainline.repositories.find(r=>r.documents.includes(s.item.document));if(!repo)throw Error('Proposal source is not registered mainline documentation');
  const status=await mainlineStatus(o,{repo:repo.name});if(status.status!=='current')throw Error('Integrated mainline freshness is unresolved');
  return status;
 }
 return {status:'current',scope:'Registered document identity; mainline mode disabled'};
}
async function checkAssessment(o,s){
 if(s.item.proposal_sha256)await snapshotBytes(s.store,s.item.proposal_sha256,'json');
 const screening=JSON.parse(decode(await snapshotBytes(s.store,s.item.screening_sha256,'json'))).screening;
 await io.validateAssessment(o,{decision:'proposed',screening:{...screening,knowledge_review:s.artifact.knowledge_review},proposal:s.artifact.proposal},{before:await io.snapshot(s.store,s.item.before),after:await io.snapshot(s.store,s.item.after)});
 await validatePropagationTargets(o,s.item,s.artifact.proposal);
 await validateParentReview(o,s.item,s.artifact.knowledge_review);
}
function knowledgeRoot(o,reference){
 if(path.isAbsolute(reference))return path.join(o.homeDir,'.council/memory/knowledge');
 const parts=reference.replaceAll('\\','/').split('/');return path.join(o.workspaceRoot,...parts.slice(0,parts.indexOf('.memory')+1));
}
async function scopedPath(o,full){
 const relative=path.relative(o.workspaceRoot,full);
 const inside=relative!==''&&relative!=='..'&&!relative.startsWith('..'+path.sep)&&!path.isAbsolute(relative);
 return knowledgeTarget(o,inside?relative:full);
}
function links(text,from){
 const result=[],clean=text.replace(/```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`/g,'');
 for(const match of clean.matchAll(/\[[^\]\n]+\]\(([^)\n]+)\)/g)){
  let reference=match[1].trim().replace(/^<|>$/g,'').split('#')[0];
  if(!reference||/^[a-z][a-z0-9+.-]*:/i.test(reference)&&! /^[A-Za-z]:[\\/]/.test(reference))continue;
  try{reference=decodeURIComponent(reference);}catch{continue;}
  result.push(path.resolve(path.dirname(from),reference));
 }
 return result;
}
async function routed(o,target,root,overlay){
 const queue=[path.join(root,'CONTEXT.md')],seen=new Set();
 while(queue.length){
  const next=queue.shift(),key=pathKey(next);if(key===pathKey(target))return true;if(seen.has(key))continue;seen.add(key);
  if(seen.size>100)throw Error('Knowledge routing exceeds bounded review scope');
  let file;try{file=await scopedPath(o,next);}catch{continue;}
  let text=overlay.get(pathKey(file));if(text===undefined){const bytes=await currentBytes(file);if(!bytes)continue;text=decode(bytes);}
  for(const link of links(text,file)){if(pathKey(link)===pathKey(target))return true;if(path.basename(link).toLowerCase()==='context.md')queue.push(link);}
 }
 return false;
}
async function checkRouting(o,s){
 const overlay=new Map();for(const r of s.artifact.proposal.revisions)overlay.set(pathKey(await knowledgeTarget(o,r.target)),r.operation==='retire'?'':r.proposed_text);
 for(const r of s.artifact.proposal.revisions)if(r.operation==='create'&&!await routed(o,await knowledgeTarget(o,r.target),knowledgeRoot(o,r.target),overlay))throw Error('New knowledge lacks an index route');
}
async function issues(o,s){
 const result=[];
 for(const [scope,check] of [['source',()=>checkSource(o,s)],['knowledge-and-targets',()=>checkAssessment(o,s)],['routing',()=>checkRouting(o,s)]]){
  try{await check();}catch{result.push({scope,reason:'Required source, evidence or target identity is stale, invalid or unavailable'});}
 }
 return result;
}
async function writeOnce(file,value){try{await fs.writeFile(file,encode(value),{flag:'wx',encoding:'utf8'});}catch(e){if(e.code!=='EEXIST')throw e;}}
export async function reviewProposal(o,input){
 const s=await candidate(o,input),workspace_id=workspaceId(o),observed=[];
 for(const r of s.artifact.proposal.revisions){const bytes=await currentBytes(await knowledgeTarget(o,r.target));observed.push({target:r.target,sha256:bytes?io.hash(bytes):null});}
 let observed_source;try{const bytes=await currentBytes(await io.safe(o.workspaceRoot,s.item.document));observed_source=bytes?io.hash(bytes):'deleted';}catch{observed_source='unavailable';}
 const review_id=io.hash(encode({workspace_id,run_id:input.run_id,item_id:input.item_id,proposal_sha256:s.proposal_sha256,observed,observed_source}));
 const directory=await io.safe(s.store,'proposals/reviews');await fs.mkdir(directory,{recursive:true});
 await io.captureSnapshot(s.store,s.bytes,'json');
 const changes=await plannedChanges(o,s,review_id),file=await io.safe(directory,review_id+'.json');
 await writeOnce(file,{schema_version:1,workspace_id,review_id,run_id:input.run_id,item_id:input.item_id,summary:s.artifact.proposal.summary,proposal_sha256:s.proposal_sha256,original_proposal_sha256:s.item.proposal_sha256||null,changes,prepared_at:io.time(o)});
 const bytes=await fs.readFile(file),review=JSON.parse(decode(bytes));
 if(review.review_id!==review_id||review.proposal_sha256!==s.proposal_sha256)throw Error('Review identity mismatch');
 const preview=await previewReview(s,review);
 return {...review,review_sha256:io.hash(bytes),proposal:s.artifact.proposal,issues:await issues(o,s),preview_path:preview};
}
async function previewReview(s,r){
 const directory=await io.safe(s.store,'stages/03-accept-proposal/output');await fs.mkdir(directory,{recursive:true});
 const lines=['# Knowledge proposal review','',`Review: ${r.review_id}`,`Proposal version: ${r.proposal_sha256}`,'',s.artifact.proposal.summary,'','This is proposed knowledge. A decision requires explicit user approval of this exact review version.',''];
 for(const change of r.changes){
  const after=decode(await snapshotBytes(s.store,change.after_sha256,'md'));
  lines.push(`## ${change.target}`,'',`Operation: ${change.operation}`,`Expected prior version: ${change.before_sha256||'absent'}`,`Observed prior version: ${change.observed_before_sha256||'absent'}`,'',change.reason,'','Proposed resulting content:','',...after.split('\n').map(line=>'> '+line),'');
  if(change.before_sha256){
   try{await snapshotBytes(s.store,change.before_sha256,'md');lines.push(`[Prior content snapshot](<${path.join(s.store,'snapshots',change.before_sha256+'.md').replaceAll('\\','/')}>)`,'');}catch{lines.push('The proposed prior content snapshot is unavailable.','');}
  }
 }
 const file=await io.safe(directory,r.review_id+'.md');await fs.writeFile(file,lines.join('\n'),'utf8');return file;
}
async function frozenReview(o,input){
 const s=await environment(o);if(!digest(input?.review_id)||!digest(input?.review_sha256))throw Error('Exact reviewed version fingerprint required');
 const bytes=await fs.readFile(await io.safe(s.store,`proposals/reviews/${input.review_id}.json`));
 if(io.hash(bytes)!==input.review_sha256)throw Error('Reviewed version fingerprint mismatch');
 const review=JSON.parse(decode(bytes));if(review.review_id!==input.review_id||review.workspace_id!==workspaceId(o))throw Error('Review identity or workspace mismatch');
 return {...s,review};
}
function assertAuthorization(o,input){
 io.owner(o);
 if(input?.authorization!=='explicit-user')throw Error('Explicit user approval is required');
 if(!['accept','reject'].includes(input.decision)||typeof input.reason!=='string'||!input.reason.trim()||input.reason.length>4000)throw Error('Invalid user decision');
}
async function lockTargets(o,s,changes,locks){
 const targets=[];for(const c of changes)targets.push(await knowledgeTarget(o,c.target));
 for(const target of targets.sort()){
  // A target-adjacent lock has the target filesystem's identity across all workspaces.
  await fs.mkdir(path.dirname(target),{recursive:true});
  const file=target+'.council-proposal.lock';const handle=await fs.open(file,'wx');locks.push({file,handle});
 }
}
async function applyChanges(o,s,receipt,file){
 for(const c of s.review.changes){
  const target=await knowledgeTarget(o,c.target),bytes=await snapshotBytes(s.store,c.after_sha256,'md');await fs.mkdir(path.dirname(target),{recursive:true});
  if(c.operation==='create')await fs.writeFile(target,bytes,{flag:'wx'});
  else{const temp=target+'.'+randomUUID()+'.tmp';await fs.writeFile(temp,bytes,{flag:'wx'});await fs.rename(temp,target);}
  receipt.written.push({target:c.target,sha256:c.after_sha256});await io.atomic(file,receipt);
 }
}
export async function decideProposal(o,input){
 assertAuthorization(o,input);const s=await frozenReview(o,input),directory=await io.safe(s.store,'proposals/decisions');await fs.mkdir(directory,{recursive:true});
 const file=await io.safe(directory,s.review.item_id+'.json');
 const receipt={schema_version:1,run_id:s.review.run_id,item_id:s.review.item_id,summary:s.review.summary,review_id:input.review_id,review_sha256:input.review_sha256,proposal_sha256:s.review.proposal_sha256,decision:input.decision,reason:input.reason,authorization:'explicit-user',actor:o.actor||'codex',chat_sha256:io.owner(o),started_at:io.time(o),status:'failed',failure:'completion-not-recorded',changes:s.review.changes,written:[]};
 if(s.config.propagation?.enabled)receipt.propagation_expected=true;
 await fs.writeFile(file,encode(receipt),{flag:'wx',encoding:'utf8'});const locks=[];
 try{
  const current=await candidate(o,s.review);if(current.proposal_sha256!==s.review.proposal_sha256)throw Error('Proposal version changed after review');
  if(input.decision==='accept'){
   await lockTargets(o,s,s.review.changes,locks);
   const problems=await issues(o,current);if(problems.length){receipt.issues=problems;throw Error('Acceptance validation failed');}
   const expected=await plannedChanges(o,current,s.review.review_id);
   if(encode(expected)!==encode(s.review.changes))throw Error('Reviewed target plan changed');
   await applyChanges(o,s,receipt,file);
   for(const c of s.review.changes)if(io.hash(await fs.readFile(await knowledgeTarget(o,c.target)))!==c.after_sha256)throw Error('Applied target fingerprint mismatch');
   receipt.status='accepted';
  }else receipt.status='rejected';
  delete receipt.failure;
 }catch{receipt.status='failed';receipt.failure='acceptance-not-applied-or-incomplete';}
 finally{for(const lock of locks.reverse()){await lock.handle.close();await fs.unlink(lock.file);}}
 receipt.finished_at=io.time(o);await io.atomic(file,receipt);
 let propagation;if(receipt.status==='accepted'&&receipt.propagation_expected){
  try{propagation=await enqueuePropagation(o,{item_id:receipt.item_id});}catch{propagation={status:'failed',reason:'Propagation scheduling unavailable; accepted knowledge remains accepted; no retry',events:[]};}
 }
 return {...receipt,path:file,...(propagation?{propagation}:{})};
}
async function workFiles(store){try{return (await fs.readdir(await io.safe(store,'work'))).filter(n=>/^[a-f0-9]{64}\.json$/.test(n));}catch(e){if(e.code==='ENOENT')return [];throw e;}}
async function collectProposals(o,s,status){
 const proposals=[],failures=[];
 for(const name of await workFiles(s.store)){
  try{
   const item=await io.json(await io.safe(s.store,'work/'+name));if(!item.finalized||item.status!=='proposed')continue;
   const decision=await optionalJson(await io.safe(s.store,`proposals/decisions/${item.item_id}.json`)),state=decision?.status||'pending';if(status!=='all'&&state!==status)continue;
   if(decision){
    if(!['accepted','rejected','failed'].includes(state)||!Array.isArray(decision.changes)||decision.item_id!==item.item_id)throw Error('Invalid decision receipt');
    proposals.push({run_id:item.run_id,item_id:item.item_id,status:state,summary:decision.summary||'Saved knowledge proposal',targets:decision.changes.map(c=>c.target),changes:decision.changes,decision_at:decision.finished_at||decision.started_at});
   }else{
    const c=await candidate(o,item);proposals.push({run_id:item.run_id,item_id:item.item_id,status:state,summary:c.artifact.proposal.summary,targets:c.artifact.proposal.revisions.map(r=>r.target),decision_at:null});
   }
  }catch{failures.push({item_id:name.slice(0,-5),reason:'Proposal record unavailable or invalid'});}
 }
 return {proposals,failures};
}
export async function listProposals(o,input={}){
 const s=await environment(o),status=input.status||'pending',limit=input.limit??50,offset=input.offset??0;
 if(!['pending','accepted','rejected','failed','all'].includes(status)||!Number.isInteger(limit)||limit<1||limit>200||!Number.isInteger(offset)||offset<0)throw Error('Invalid proposal list selection');
 const result=await collectProposals(o,s,status);return {...result,proposals:result.proposals.slice(offset,offset+limit),total:result.proposals.length,offset};
}
export async function proposalStatus(o,input){
 const target=await knowledgeTarget(o,input?.target),s=await environment(o),list=await collectProposals(o,s,'all'),relevant=[];
 for(const entry of list.proposals)for(const reference of entry.targets)if(pathKey(await knowledgeTarget(o,reference))===pathKey(target)){relevant.push(entry);break;}
 const bytes=await currentBytes(target),current=bytes?io.hash(bytes):null,unresolved=[];
 for(const entry of relevant)if(entry.status==='pending'||entry.status==='failed'){
  const superseded=entry.status==='failed'&&await supersededFailure(o,target,current,entry,relevant);
  if(!superseded)unresolved.push(entry);
 }
 const accepted_version_matches=await acceptedVersionMatches(o,target,current,relevant);
 const parent_review=await propagationStatus(o,input),parentPending=['pending-parent-review','parent-review-failed'].includes(parent_review.status);
 return {target:input.target,status:unresolved.length||list.failures.length||!accepted_version_matches||parentPending?'needs-review':'no-pending-review',proposals:relevant,unresolved:unresolved.map(r=>r.item_id),accepted_version_matches,record_failures:list.failures.length,parent_review};
}
async function acceptedVersionMatches(o,target,current,relevant){
 const accepted=relevant.filter(r=>r.status==='accepted').sort((a,b)=>b.decision_at.localeCompare(a.decision_at));if(!accepted.length)return true;
 const versions=new Set();for(const record of accepted.filter(r=>r.decision_at===accepted[0].decision_at)){
  for(const change of record.changes)if(pathKey(await knowledgeTarget(o,change.target))===pathKey(target))versions.add(change.after_sha256);
 }
 return versions.size===1&&versions.has(current);
}
async function supersededFailure(o,target,current,failed,relevant){
 for(const accepted of relevant.filter(r=>r.status==='accepted'&&r.decision_at>failed.decision_at)){
  for(const change of accepted.changes)if(pathKey(await knowledgeTarget(o,change.target))===pathKey(target)&&change.after_sha256===current)return true;
 }
 return false;
}
