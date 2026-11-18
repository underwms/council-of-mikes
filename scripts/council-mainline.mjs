/** Daily network observations of integrated code. Never checks out, merges or resets a working tree. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {randomUUID} from 'node:crypto';
import {maintenanceIO as io} from './council-daily.mjs';
const execute=promisify(execFile),encode=v=>JSON.stringify(v,null,2)+'\n';
const sha=s=>typeof s==='string'&&/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(s);
async function git(repo,args){
 try{return (await execute('git',['-c','gc.auto=0','-c','maintenance.auto=false','-C',repo,...args],{encoding:'buffer',timeout:30000,maxBuffer:2*1024*1024,windowsHide:true,env:{...process.env,GIT_TERMINAL_PROMPT:'0',GCM_INTERACTIVE:'Never'}})).stdout;}
 catch(e){const error=Error(e.killed?'Git operation timed out':'Git operation failed');error.code=e.killed?'git-timeout':'git-failed';throw error;}
}
const decode=b=>new TextDecoder('utf-8',{fatal:true}).decode(b);
async function environment(o){
 const s=await io.settings(o);if(!s?.config.mainline?.enabled)throw Error('Daily mainline refresh disabled');
 const repositories=s.config.mainline.repositories;
 if(!Array.isArray(repositories)||!repositories.length||repositories.length>3000)throw Error('Invalid mainline repository registry');
 const names=new Set(),documents=new Set(),paths=new Set();
 for(const r of repositories){
  validateRepository(r,names,paths);await io.safe(o.workspaceRoot,r.path);
  for(const document of r.documents){if(typeof document!=='string'||!document.startsWith('docs/')||!document.endsWith('.md')||!s.config.documents.includes(document)||documents.has(document.toLowerCase()))throw Error('Invalid mainline document target');documents.add(document.toLowerCase());await io.safe(o.workspaceRoot,document);}
 }
 return {...s,repositories};
}
function validateRepository(r,names,paths){
 if(!r||typeof r.name!=='string'||!/^[-\w.]+$/.test(r.name)||typeof r.path!=='string')throw Error('Invalid mainline repository identity');
 const normalized=r.path.replaceAll('\\','/').toLowerCase();
 if(names.has(r.name.toLowerCase())||paths.has(normalized))throw Error('Duplicate mainline repository');
 if(!['main','master',null].includes(r.branch)||!sha(r.baseline_commit))throw Error('Invalid mainline branch or baseline');
 if(!Array.isArray(r.documents)||!r.documents.length)throw Error('Invalid mainline document registry');
 names.add(r.name.toLowerCase());paths.add(normalized);
}
async function runContext(o,input){
 const s=await environment(o);
 if(!input||!/^\d{4}-\d{2}-\d{2}$/.test(input.run_id))throw Error('Invalid mainline run identity');
 const runFile=await io.safe(s.store,`runs/${input.run_id}.json`),run=await io.json(runFile);
 if(run.owner!==io.owner(o)||input.run_id!==io.day(o,s.config.time_zone))throw Error('Only same-day owner may perform mainline work');
 if(!run.mainline_enabled||run.scan_complete)throw Error('Mainline run closed or unavailable');
 return {...s,run,runFile};
}
async function checkpoint(s){
 let cp;try{cp=await io.json(await io.safe(s.store,'mainline-checkpoints.json'));}catch(e){if(e.code!=='ENOENT')throw e;cp={schema_version:1,repositories:{}};}
 if(cp.schema_version!==1||!cp.repositories||typeof cp.repositories!=='object'||Array.isArray(cp.repositories))throw Error('Invalid mainline checkpoints');
 for(const state of Object.values(cp.repositories))if(!state||!sha(state.attempted)||!sha(state.documented)||!['current','failed'].includes(state.status)||!state.documents||typeof state.documents!=='object'||Array.isArray(state.documents))throw Error('Invalid mainline checkpoint entry');
 return cp;
}
function baseline(r){return {attempted:r.baseline_commit,documented:r.baseline_commit,status:'current',documents:r.baseline_documents||{},checked_at:r.baseline_checked_on||null,baseline_day:r.baseline_checked_on||null};}
async function documentHashes(o,documents){
 const result={};for(const document of documents){const bytes=await fs.readFile(await io.safe(o.workspaceRoot,document));if(bytes.length>256*1024)throw Error('Architecture document too large');decode(bytes);result[document]=io.hash(bytes);}return result;
}
async function fetchMainline(o,r){
 const repo=await io.safe(o.workspaceRoot,r.path),top=decode(await git(repo,['rev-parse','--show-toplevel'])).trim();
 if(path.resolve(top).toLowerCase()!==repo.toLowerCase())throw Error('Repository root mismatch');
 const advertised=decode(await git(repo,['ls-remote','--heads','origin','refs/heads/main','refs/heads/master']));
 const branches=[...advertised.matchAll(/^[a-f0-9]{40,64}\s+refs\/heads\/(main|master)\r?$/gm)].map(m=>m[1]);
 if(!branches.length)throw Error('Origin has no main/master');
 await git(repo,['fetch','--no-tags','--no-recurse-submodules','--no-write-fetch-head','origin',...branches.map(b=>`+refs/heads/${b}:refs/memoryforge/mainline/${b}`)]);
 if(!r.branch||!branches.includes(r.branch))throw Error('Configured mainline branch unavailable');
 const commit=decode(await git(repo,['rev-parse',`refs/memoryforge/mainline/${r.branch}`])).trim();if(!sha(commit))throw Error('Invalid fetched revision');
 return {commit,branches};
}
async function assignRefresh(o,s,cp,r,commit){
 const previous=cp.repositories[r.name]||baseline(r),refresh_id=io.hash(JSON.stringify([s.run.run_id,r.name,commit]));
 const item={schema_version:1,run_id:s.run.run_id,refresh_id,repo:r.name,repository_path:r.path,branch:r.branch,commit,before:previous.documented,documents:[],status:'failed',reason:'completion-not-recorded',finalized:false};
 await fs.writeFile(await io.safe(s.store,`refresh/${refresh_id}.json`),encode(item),{flag:'wx',encoding:'utf8'});
 s.run.refresh_items.push(refresh_id);await io.atomic(s.runFile,s.run);
 cp.repositories[r.name]={...previous,attempted:commit,status:'failed',reason:'completion-not-recorded'};await io.atomic(await io.safe(s.store,'mainline-checkpoints.json'),cp);
 const hashes=await documentHashes(o,r.documents);item.documents=r.documents.map(p=>({path:p,sha256:hashes[p]}));
 await io.atomic(await io.safe(s.store,`refresh/${refresh_id}.json`),item);
 return refresh_id;
}
export async function scanMainline(o,input){
 const s=await runContext(o,input);await fs.writeFile(await io.safe(s.store,`runs/${input.run_id}.mainline`),'attempted\n',{flag:'wx'});
 await fs.mkdir(await io.safe(s.store,'refresh'),{recursive:true});const cp=await checkpoint(s);
 for(const r of s.repositories){
  s.run.mainline_observations[r.name]={status:'failed',reason:'completion-not-recorded',checked_at:io.time(o)};await io.atomic(s.runFile,s.run);
  try{
   const fetched=await fetchMainline(o,r),previous=cp.repositories[r.name]||baseline(r);
   if(input.run_id!==io.day(o,s.config.time_zone))throw Error('Daily mainline run expired');
   s.run.mainline_observations[r.name]={status:'fetched',...fetched,branch:r.branch,checked_at:io.time(o)};await io.atomic(s.runFile,s.run);
   if(fetched.commit!==previous.attempted)await assignRefresh(o,s,cp,r,fetched.commit);
   else {cp.repositories[r.name]=previous;await io.atomic(await io.safe(s.store,'mainline-checkpoints.json'),cp);}
  }catch(e){s.run.mainline_observations[r.name]={...s.run.mainline_observations[r.name],status:'failed',reason:e.code||'mainline-observation-failed'};s.run.failures.push({repo:r.name,reason:e.code||'mainline-observation-failed'});await io.atomic(s.runFile,s.run);}
  if(input.run_id!==io.day(o,s.config.time_zone))break;
 }
 s.run.mainline_complete=true;await io.atomic(s.runFile,s.run);
 return {run_id:input.run_id,refresh_items:s.run.refresh_items,observations:s.run.mainline_observations};
}
async function itemContext(o,input){
 const s=await runContext(o,input);
 if(!/^[a-f0-9]{64}$/.test(input.refresh_id)||!s.run.refresh_items.includes(input.refresh_id))throw Error('Unknown refresh identity');
 const file=await io.safe(s.store,`refresh/${input.refresh_id}.json`),item=await io.json(file);
 if(item.finalized)throw Error('Refresh already finalized; no retries');
 const repo=s.repositories.find(r=>r.name===item.repo);
 if(!repo||item.run_id!==input.run_id||item.branch!==repo.branch||item.repository_path!==repo.path||!sha(item.commit)||item.commit!==s.run.mainline_observations[item.repo]?.commit||input.refresh_id!==io.hash(JSON.stringify([input.run_id,item.repo,item.commit])))throw Error('Refresh identity mismatch');
 return {...s,item,file,repo};
}
export async function mainlinePacket(o,input){
 const s=await itemContext(o,input),repo=await io.safe(o.workspaceRoot,s.repo.path);
 if(s.item.documents.length!==s.repo.documents.length)throw Error('Refresh document inputs unavailable');
 const bytes=await git(repo,['diff','--name-only','-z',s.item.before,s.item.commit,'--']);
 const changed_paths=decode(bytes).split('\0').filter(Boolean);if(changed_paths.length>20000)throw Error('Change set too large');
 return {...s.item,changed_paths,contract:'instructions/memoryforge/stages/00-mainline-refresh/CONTEXT.md',skill:'skills/repo-documentation/SKILL.md',source_command:'daily mainline-source with run_id, refresh_id, path and optional side before; reads only pinned integrated revisions. Never substitute working-tree files.'};
}
async function readSource(o,s,input){
 if(input.side!==undefined&&!['before','after'].includes(input.side))throw Error('Invalid source side');
 await io.safe(o.workspaceRoot,input.path);
 if(input.path.split(/[\\/]/).some(p=>p==='.git'||p==='.env'||/\.(?:pfx|pem|key)$/i.test(p)))throw Error('Sensitive source path excluded');
 const revision=input.side==='before'?s.item.before:s.item.commit;
 const bytes=await git(await io.safe(o.workspaceRoot,s.repo.path),['cat-file','blob',revision+':'+input.path.replaceAll('\\','/')]);
 if(bytes.length>256*1024)throw Error('Source file too large');
 return {path:input.path,revision,sha256:io.hash(bytes),text:decode(bytes)};
}
export async function mainlineSource(o,input){return readSource(o,await itemContext(o,input),input);}
async function validateEvidence(o,s,input){
 if(!Array.isArray(input.evidence)||!input.evidence.length||input.evidence.length>100)throw Error('Inspected mainline evidence required');
 for(const evidence of input.evidence){
  const side=evidence.revision===s.item.commit?'after':evidence.revision===s.item.before?'before':null;if(!side)throw Error('Evidence must be a pinned mainline revision');
  if((await readSource(o,s,{path:evidence.path,side})).sha256!==evidence.sha256)throw Error('Mainline evidence fingerprint mismatch');
 }
}
async function stagedDocuments(o,s,input){
 const current=await documentHashes(o,s.repo.documents);
 for(const d of s.item.documents)if(current[d.path]!==d.sha256)throw Error('Architecture target fingerprint mismatch');
 if(input.decision==='no-doc-change'){if(input.documents?.length)throw Error('No-doc-change cannot publish documents');return [];}
 if(!Array.isArray(input.documents)||!input.documents.length||input.documents.length>s.repo.documents.length)throw Error('Staged document changes required');
 const edits=[],seen=new Set(),output=await io.safe(s.store,'stages/00-mainline-refresh/output');
 for(const d of input.documents)edits.push(await stagedEdit(o,s,d,current,seen,output));
 return edits;
}
async function stagedEdit(o,s,d,current,seen,output){
  if(!s.repo.documents.includes(d.path)||seen.has(d.path)||d.before_sha256!==current[d.path])throw Error('Invalid or stale architecture target');seen.add(d.path);
  const file=await io.safe(o.workspaceRoot,d.staged_path);await io.safe(output,path.relative(output,file));
  const bytes=await fs.readFile(file);if(bytes.length>256*1024||!decode(bytes).trim())throw Error('Invalid staged document');
  if(io.hash(bytes)===current[d.path])throw Error('Updated document is unchanged');return {path:d.path,bytes};
}
async function publish(o,edits){
 for(const edit of edits){const file=await io.safe(o.workspaceRoot,edit.path),temp=file+'.'+randomUUID()+'.tmp';await fs.writeFile(temp,edit.bytes,{flag:'wx'});await fs.rename(temp,file);}
}
export async function finishMainline(o,input){
 if(!input||!['updated','no-doc-change','failed'].includes(input.decision)||typeof input.reason!=='string'||!input.reason.trim()||input.reason.length>4000)throw Error('Invalid refresh disposition');
 const s=await itemContext(o,input);let edits=[];
 if(input.decision!=='failed'){if(s.item.documents.length!==s.repo.documents.length)throw Error('Refresh document inputs unavailable');await validateEvidence(o,s,input);edits=await stagedDocuments(o,s,input);}
 const lockFile=await io.safe(s.store,`runs/${input.run_id}.publication`),lock=await fs.open(lockFile,'wx');
 try{
  s.run=await io.json(s.runFile);
  if(input.run_id!==io.day(o,s.config.time_zone))throw Error('Daily mainline run expired');
  if(s.run.scan_complete)throw Error('Mainline run closed; document scan already complete');
  return await finalizeRefresh(o,input,s,edits);
 }finally{await lock.close();await fs.unlink(lockFile);}
}
async function finalizeRefresh(o,input,s,edits){
 await fs.writeFile(await io.safe(s.store,`refresh/${input.refresh_id}.final`),'attempted\n',{flag:'wx'});
 await publish(o,edits);
 const hashes=input.decision==='failed'?undefined:await documentHashes(o,s.repo.documents);
 const evidence=input.decision==='failed'?undefined:input.evidence.map(({path,revision,sha256})=>({path,revision,sha256}));
 const record={...s.item,status:input.decision,reason:input.reason,evidence,document_fingerprints:hashes,finalized:true,finished_at:io.time(o)};
 const output=await io.safe(s.store,`stages/00-mainline-refresh/output/${input.refresh_id}.json`);await fs.mkdir(path.dirname(output),{recursive:true});await fs.writeFile(output,encode(record),{flag:'wx',encoding:'utf8'});
 await io.atomic(s.file,record);
 const cp=await checkpoint(s),previous=cp.repositories[s.repo.name]||baseline(s.repo);
 if(input.decision==='failed'){cp.repositories[s.repo.name]={...previous,status:'failed',reason:input.reason};s.run.failures.push({repo:s.repo.name,reason:'documentation-refresh-failed'});}
 else{
  cp.repositories[s.repo.name]={...previous,documented:s.item.commit,status:'current',reason:input.reason,documents:hashes,checked_at:io.time(o)};
  s.run.mainline_scan_documents=[...new Set([...s.run.mainline_scan_documents,...s.repo.documents])];
 }
 await io.atomic(await io.safe(s.store,'mainline-checkpoints.json'),cp);await io.atomic(s.runFile,s.run);
 return {refresh_id:input.refresh_id,status:input.decision,path:output};
}
export async function mainlineStatus(o,input){
 const s=await environment(o),repo=s.repositories.find(r=>r.name===input?.repo);if(!repo)throw Error('Unknown mainline repository');
 if(!repo.branch)return {repo:repo.name,status:'unavailable',reason:'No configured main/master'};
 const cp=await checkpoint(s),state=cp.repositories[repo.name]||baseline(repo),today=io.day(o,s.config.time_zone);
 let observation;try{observation=(await io.json(await io.safe(s.store,`runs/${today}.json`))).mainline_observations?.[repo.name];}catch(e){if(e.code!=='ENOENT')throw e;}
 if(observation?.status==='failed')return {repo:repo.name,status:'unavailable',reason:observation.reason};
 if(!observation&&state.baseline_day!==today)return {repo:repo.name,status:'unavailable',reason:'Mainline not checked today'};
 if(state.status!=='current'||observation&&state.documented!==observation.commit)return {repo:repo.name,status:'needs-review',revision:observation?.commit||state.attempted,documented_revision:state.documented};
 let actual;try{actual=await documentHashes(o,repo.documents);}catch{return {repo:repo.name,status:'unavailable',reason:'Maintained documents unavailable',revision:state.documented};}
 if(repo.documents.some(p=>actual[p]!==state.documents[p]))return {repo:repo.name,status:'needs-review',reason:'Architecture document fingerprint changed',revision:state.documented};
 return {repo:repo.name,status:'current',branch:repo.branch,revision:state.documented,checked_at:observation?.checked_at||state.checked_at,basis:observation?'daily-network-observation':'approved-mainline-baseline',scope:'Fetched integrated mainline and maintained documents; feature working tree is not a freshness input'};
}
