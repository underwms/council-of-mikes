/** Private task context. No transcript ingestion, native trust changes, or engine execution. */
import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash, randomUUID} from 'node:crypto';
import {setTimeout as delay} from 'node:timers/promises';

const statuses = new Set(['open','paused','blocked','completed']);
const maxCatalogue = 2 * 1024 * 1024;
const timestamp = () => new Date().toISOString();
const root = o => path.join(o.homeDir,'.council','memory');
const cataloguePath = o => path.join(root(o),'task-context.json');
const digest = s => createHash('sha256').update(s).digest('hex');
const idPattern = /^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$/;
function taskId(id) {if(typeof id!=='string'||!idPattern.test(id))throw Error('Invalid task identity');return id;}
function actor(o) {const a=o.actor||'codex';if(!['codex','gemini'].includes(a))throw Error('Unsupported task client');return a;}
function chatKey(o,required=true) {
  if(typeof o.chat!=='string'||!o.chat.trim()||o.chat.length>256||/[\x00-\x1f]/.test(o.chat)) {
    if(required)throw Error('A valid chat identity is required');return null;
  }
  return actor(o)+':'+digest(o.chat);
}
function text(value,name,limit,empty=false) {
  if(typeof value!=='string'||(!empty&&!value.trim())||Buffer.byteLength(value,'utf8')>limit||value.includes('\0'))throw Error('Invalid task '+name);
  return value;
}
function project(value) {
  if(value==null)return null;
  return text(value,'project',256);
}
function projectRoot(value) {
  if(value==null)return null;
  if(typeof value!=='string'||!path.isAbsolute(value)||value.includes('\0'))throw Error('Invalid task project root');
  return path.resolve(value);
}
function validate(data) {
  if(!data||data.schema_version!==1||!data.tasks||!data.bindings||typeof data.tasks!=='object'||Array.isArray(data.tasks)||typeof data.bindings!=='object'||Array.isArray(data.bindings))throw Error('Invalid task catalogue');
  for(const [id,t] of Object.entries(data.tasks)) {
    if(!t||taskId(id)!==t.id||!statuses.has(t.status))throw Error('Invalid task catalogue status/identity');
    text(t.title,'title',200);text(t.summary,'summary',600,true);text(t.state,'state',5000,true);
    project(t.project_id);projectRoot(t.project_root);
    if(!Number.isFinite(Date.parse(t.updated_at))||!Array.isArray(t.history))throw Error('Invalid task catalogue metadata');
  }
  for(const [key,b] of Object.entries(data.bindings)) {
    if(!/^(codex|gemini):[a-f0-9]{64}$/.test(key)||!b||!['task','fresh'].includes(b.mode)||!Number.isFinite(Date.parse(b.updated_at)))throw Error('Invalid task catalogue binding');
    if(b.mode==='task'&&(!Object.hasOwn(data.tasks,b.task_id)||taskId(b.task_id)!==b.task_id))throw Error('Invalid task catalogue binding target');
    if(b.mode==='fresh'&&b.task_id!==null)throw Error('Invalid task catalogue fresh binding');
  }
  return data;
}
export async function readCatalogue(o) {
  try {
    const p=cataloguePath(o),stat=await fs.lstat(p);
    if(!stat.isFile()||stat.isSymbolicLink()||stat.size>maxCatalogue)throw Error('Unsupported task catalogue');
    return validate(JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(await fs.readFile(p))));
  }catch(e){if(e.code==='ENOENT')return {schema_version:1,tasks:{},bindings:{}};throw Error('Task catalogue unavailable; preserve it for review',{cause:e});}
}
async function update(o,change) {
  const dir=root(o);await fs.mkdir(dir,{recursive:true});
  const lock=path.join(dir,'task-context.lock');let handle;
  for(let i=0;i<60;i++) {try{handle=await fs.open(lock,'wx');break;}catch(e){if(e.code!=='EEXIST')throw e;await delay(20);}}
  if(!handle)throw Error('Task catalogue is busy; review stale lock after exiting clients');
  try {
    const data=await readCatalogue(o),result=change(data);validate(data);
    const bytes=Buffer.from(JSON.stringify(data,null,2)+'\n','utf8');if(bytes.length>maxCatalogue)throw Error('Task catalogue is full; archive reviewed tasks before adding more');
    const temp=path.join(dir,'task-context-'+randomUUID()+'.tmp');
    try{await fs.writeFile(temp,bytes,{flag:'wx'});await fs.rename(temp,cataloguePath(o));}
    finally{await fs.unlink(temp).catch(e=>{if(e.code!=='ENOENT')throw e;});}
    return result;
  }finally{await handle.close();await fs.unlink(lock);}
}
export async function saveTask(o,input) {
  if(!input||typeof input!=='object'||Array.isArray(input))throw Error('Invalid task record');
  const allowed=new Set(['id','title','summary','state','project_id','project_root']);
  if(Object.keys(input).some(k=>!allowed.has(k)))throw Error('Task status/metadata must use explicit operations');
  const row={id:taskId(input.id),title:text(input.title,'title',200),summary:text(input.summary??'','summary',600,true),state:text(input.state??'','state',5000,true),project_id:project(input.project_id),project_root:projectRoot(input.project_root)};
  return update(o,data=>{
    const old=Object.hasOwn(data.tasks,row.id)?data.tasks[row.id]:null;
    const saved={...row,status:old?.status||'open',updated_at:timestamp(),history:old?.history||[]};
    Object.defineProperty(data.tasks,row.id,{value:saved,enumerable:true,writable:true,configurable:true});
    return {id:saved.id,status:saved.status,updated_at:saved.updated_at};
  });
}
export async function selectTask(o,id) {
  const key=chatKey(o);taskId(id);
  return update(o,data=>{if(!Object.hasOwn(data.tasks,id))throw Error('Unknown task');const b={mode:'task',task_id:id,updated_at:timestamp()};data.bindings[key]=b;return {...b,status:data.tasks[id].status};});
}
export async function startFresh(o) {
  const key=chatKey(o);return update(o,data=>{const b={mode:'fresh',task_id:null,updated_at:timestamp()};data.bindings[key]=b;return b;});
}
export async function setTaskStatus(o,id,status,{reason='',resume=false}={}) {
  taskId(id);if(!statuses.has(status))throw Error('Invalid task status');text(reason,'status reason',400,true);
  return update(o,data=>{
    if(!Object.hasOwn(data.tasks,id))throw Error('Unknown task');const task=data.tasks[id];
    if(['paused','completed'].includes(task.status)&&status==='open'&&!resume)throw Error('Explicit resume is required');
    if(['paused','blocked'].includes(status)&&!reason.trim())throw Error('Task status requires a reason');
    const at=timestamp();task.history=[...task.history,{from:task.status,to:status,reason,at}].slice(-20);task.status=status;task.updated_at=at;
    return {id,status,updated_at:at};
  });
}
export async function getBinding(o) {
  const key=chatKey(o,false);if(!key)return null;return (await readCatalogue(o)).bindings[key]||null;
}
export async function getSelectedTask(o) {
  const key=chatKey(o,false);if(!key)return null;
  const data=await readCatalogue(o),b=data.bindings[key];return b?.mode==='task'?data.tasks[b.task_id]:null;
}
function normalized(p) {const s=path.resolve(p);return process.platform==='win32'?s.toLowerCase():s;}
function contains(parent,child) {const rel=path.relative(normalized(parent),normalized(child));return rel===''||!rel.startsWith('..'+path.sep)&&rel!=='..'&&!path.isAbsolute(rel);}
export async function suggestTasks(o) {
  const data=await readCatalogue(o);let candidates=Object.values(data.tasks).filter(t=>t.status!=='completed'),scope='recent (no saved project match)';
  if(o.project) {candidates=candidates.filter(t=>t.project_id===o.project);scope='project';}
  else if(o.cwd&&path.isAbsolute(o.cwd)) {
    const matches=candidates.filter(t=>t.project_root&&contains(t.project_root,o.cwd)).sort((a,b)=>b.project_root.length-a.project_root.length);
    if(matches.length){const selected=normalized(matches[0].project_root);candidates=candidates.filter(t=>t.project_root&&normalized(t.project_root)===selected);scope='project';}
  }
  const limit=o.limit??3;if(!Number.isInteger(limit)||limit<1||limit>10)throw Error('Task suggestion limit must be 1-10');
  return {scope,tasks:candidates.sort((a,b)=>b.updated_at.localeCompare(a.updated_at)||a.id.localeCompare(b.id)).slice(0,limit).map(({id,title,summary,status,updated_at,project_id,project_root})=>({id,title,summary,status,updated_at,project_id,project_root})),start_fresh:true};
}
export function taskMemoryRoot(o,id) {return path.join(root(o),'tasks',taskId(id));}
export async function receiptPath(o) {return path.join(root(o),'runtime','startup-'+actor(o)+'-'+(chatKey(o,false)?.split(':')[1]||'unknown')+'.json');}
export async function recordStartupReceipt(o,source,mode) {
  const p=await receiptPath(o);await fs.mkdir(path.dirname(p),{recursive:true});
  const allowed=new Set(['startup','resume','clear','compact','fork']);
  const receipt={schema_version:1,event:'SessionStart',actor:actor(o),source:allowed.has(source)?source:'unknown',observed_at:timestamp(),chat_identity_sha256:chatKey(o,false)?.split(':')[1]||null,context_mode:mode,scope:'user-startup',origin:'hook-handler invocation; caller surface not attested'};
  const temp=p+'.'+randomUUID()+'.tmp';
  try{await fs.writeFile(temp,JSON.stringify(receipt,null,2)+'\n',{flag:'wx'});await fs.rename(temp,p);}
  finally{await fs.unlink(temp).catch(e=>{if(e.code!=='ENOENT')throw e;});}
}
