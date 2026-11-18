import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';

test('startup keeps delivered state after a later unrelated tool and rejects missing pause identity',async()=>{
 const {parseTrace,gradeCase}=await import('../council-eval.mjs');
 const body='# Current state\nCURRENT_EXTRA\nPAUSED_EXTRA';
 const events=[
  {type:'item.completed',item:{id:'state',type:'command_execution',command:'Get-Content current_state.md',exit_code:0,aggregated_output:body}},
  {type:'item.completed',item:{id:'other',type:'command_execution',command:'Get-Content manifest.json',exit_code:0,aggregated_output:'{}'}},
  {type:'item.completed',item:{type:'agent_message',text:'CURRENT_EXTRA is current. PAUSED_EXTRA remains paused.'}},
  {type:'turn.completed'}
 ];
 const trace=parseTrace('codex',events.map(e=>JSON.stringify(e)).join('\n'),{'current-state':body});
 assert.equal(gradeCase('startup',trace,{current:'CURRENT_EXTRA',stopped:'PAUSED_EXTRA'}).status,'pass');
 const missing=gradeCase('startup',trace,{current:'CURRENT_EXTRA',stopped:''});
 assert.equal(missing.status,'fail');assert(missing.reasons.includes('paused_task_not_recovered'));
});

test('propagation evaluation requires actual workflow and evidence delivery with separate parent approval',async()=>{
 const {gradeCase,parseTrace}=await import('../council-eval.mjs');
 const artifacts={'propagation-contract':'# Parent review workflow','propagation-parent':'# Parent evidence','propagation-child':'# Child evidence'};
 const markers={parent:'PARENT_RULE_123',child:'CHILD_RULE_456'};
 const answer={type:'item.completed',item:{type:'agent_message',text:'PARENT_RULE_123 remains current. CHILD_RULE_456 is accepted child evidence. A parent revision is proposed and requires explicit approval.'}};
 const end={type:'turn.completed'};
 const missing=parseTrace('codex',[answer,end].map(e=>JSON.stringify(e)).join('\n'),artifacts);assert.equal(gradeCase('propagation',missing,markers).status,'fail');
 const read={type:'item.completed',item:{id:'read',type:'command_execution',command:'Get-Content fixture',exit_code:0,aggregated_output:Object.values(artifacts).join('\n')}};
 const delivered=parseTrace('codex',[read,answer,end].map(e=>JSON.stringify(e)).join('\n'),artifacts);assert.equal(gradeCase('propagation',delivered,markers).status,'pass');
 const unidentified=structuredClone(delivered);unidentified.messages=['The parent rule is current; a parent proposal still requires explicit approval.'];assert.equal(gradeCase('propagation',unidentified,markers).status,'fail');
 const deciding=structuredClone(delivered);deciding.tools.push({name:'shell',input:'node council-codex.mjs daily proposal-decide',status:'error'});assert.equal(gradeCase('propagation',deciding,markers).status,'fail');
});

test('knowledge-use evaluation requires delivered member guidance, note and evidence rather than self-report',async()=>{
 const {parseTrace,gradeCase}=await import('../council-eval.mjs');
 const body=await fs.readFile(new URL('../../skills/the-relay/SKILL.md',import.meta.url),'utf8');
 const artifacts={'knowledge-use':'# Test retrieval contract\nLoad selected evidence.','knowledge-index':'# Test knowledge index\nUse current-note.md.','knowledge-note':'# Current note\nEvidence: publisher-contract.md.','knowledge-evidence':'# Publisher contract\nSupported current rule.','knowledge-proposal':'# Pending proposal\nNot accepted.'};
 const markers={topic:'TOPIC_123',key:'KEY_123',proposal:'PROPOSED_123'};
 const events=[{type:'item.completed',item:{id:'read',type:'command_execution',command:'Get-Content selected files',exit_code:0,aggregated_output:body+'\n'+Object.values(artifacts).join('\n')}},
  {type:'item.completed',item:{type:'agent_message',text:'Use TOPIC_123 and KEY_123. PROPOSED_123 is pending, not accepted.'}},{type:'turn.completed'}];
 const raw=events.map(e=>JSON.stringify(e)).join('\n');
 assert.equal(gradeCase('knowledge',parseTrace('codex',raw,artifacts),markers).status,'pass');
 assert.equal(gradeCase('knowledge',parseTrace('codex',events.slice(1).map(e=>JSON.stringify(e)).join('\n'),artifacts),markers).status,'fail');
 const missing={...artifacts,'knowledge-evidence':'Unopened evidence body'};
 assert.equal(gradeCase('knowledge',parseTrace('codex',raw,missing),markers).status,'fail');
 const grade=gradeCase('knowledge',parseTrace('codex',raw,artifacts),markers);assert(!JSON.stringify(grade).includes('Supported current rule'));
});
test('an unavailable knowledge client records a blocked result instead of a false retrieval pass',async t=>{
 const {runEvaluation}=await import('../council-eval.mjs');
 const folder=await fs.mkdtemp(path.join(os.tmpdir(),'council-knowledge-unavailable-'));
 t.after(async()=>{assert(path.basename(folder).startsWith('council-knowledge-unavailable-'));await fs.rm(folder,{recursive:true,force:true});});
 const previous=process.env.PATH;let report;
 try{
  process.env.PATH='';
  report=await runEvaluation({client:'codex',selectedCase:'knowledge',timeout:1000,output:path.join(folder,'report.json')});
 }finally{if(previous===undefined)delete process.env.PATH;else process.env.PATH=previous;}
 assert.equal(report.status,'blocked');assert.deepEqual(report.results[0].reasons,['native_client_unavailable']);
 assert.deepEqual(report.results[0].observations.artifactsRead,[]);
 assert.equal(JSON.parse(await fs.readFile(report.report,'utf8')).status,'blocked');
});

test('Codex evaluation requires a completed turn and actual memory retrieval evidence', async () => {
  const { parseTrace, gradeCase } = await import('../council-eval.mjs');
  const artifacts={'current-state':'# Current state\nCurrent CTX_123. Separate graph STOP_123 remains paused.\n'};
  const trace = parseTrace('codex', [
    {type:'item.completed',item:{id:'1',type:'command_execution',command:'node council-codex.mjs onboard',exit_code:0,aggregated_output:artifacts['current-state']}},
    {type:'item.completed',item:{id:'2',type:'agent_message',text:'Current CTX_123. Keep STOP_123 paused.'}},
    {type:'turn.completed'}
  ].map(x=>JSON.stringify(x)).join('\n'),artifacts);
  assert.equal(gradeCase('startup', trace, {current:'CTX_123',stopped:'STOP_123'}).status, 'pass');
  trace.completed = false;
  assert.equal(gradeCase('startup', trace, {current:'CTX_123',stopped:'STOP_123'}).status, 'blocked');
});
test('final self-report cannot substitute for tool evidence and fixture IDs', async () => {
  const { parseTrace, gradeCase } = await import('../council-eval.mjs');
  const trace = parseTrace('codex', JSON.stringify({type:'item.completed',item:{type:'agent_message',text:'Council loaded; I read memory.'}})+'\n'+JSON.stringify({type:'turn.completed'}));
  assert.equal(gradeCase('startup', trace, {current:'CTX_123',stopped:'STOP_123'}).status, 'fail');
});
for(const id of ['startup','stale'])test(`${id} fails safely when a completed Codex turn has no final assistant message`,async()=>{
 const {parseTrace,gradeCase}=await import('../council-eval.mjs');
 const body='# Current state\nCurrent CTX_CONTROL. STOP_CONTROL is paused.\n';
 const trace=parseTrace('codex',[
  {type:'item.completed',item:{id:'read',type:'command_execution',command:'Get-Content current_state.md',exit_code:0,aggregated_output:body}},
  {type:'turn.completed'}
 ].map(e=>JSON.stringify(e)).join('\n'),{'current-state':body});
 const grade=gradeCase(id,trace,{current:'CTX_CONTROL',stopped:'STOP_CONTROL'});
 assert.equal(grade.status,'fail');assert.equal(grade.observations.memoryRead,true);
 assert(grade.reasons.includes('current_task_not_recovered'));
 assert(grade.reasons.includes('paused_task_not_recovered'));
 assert(grade.reasons.includes('paused_status_not_preserved'));
});
test('Gemini parser follows native tool-use events and terminal result', async () => {
  const { parseTrace, gradeCase } = await import('../council-eval.mjs');
  const trace = parseTrace('gemini', [
    {type:'tool_use',tool_name:'activate_skill',parameters:{name:'the-prover'}},
    {type:'tool_result',status:'success'},
    {type:'message',role:'assistant',content:'Use FAIR feature integration and regression cases.'},
    {type:'result',status:'success'}
  ].map(x=>JSON.stringify(x)).join('\n'));
  assert.equal(gradeCase('fair',trace,{}).status,'pass');
});
test('failed skill activation cannot establish positive loading evidence',async()=>{
  const {parseTrace,gradeCase}=await import('../council-eval.mjs');
  const trace=parseTrace('gemini',[
    {type:'tool_use',tool_id:'t1',tool_name:'activate_skill',parameters:{name:'the-prover'}},
    {type:'tool_result',tool_id:'t1',status:'error'},
    {type:'message',role:'assistant',content:'Use FAIR.'},
    {type:'result',status:'success'}
  ].map(e=>JSON.stringify(e)).join('\n'));
  assert.notEqual(gradeCase('fair',trace,{}).status,'pass');
});
test('a batched shell read can deliver the complete skill even if a later command fails',async()=>{
  const {parseTrace,gradeCase}=await import('../council-eval.mjs');
  const body=await fs.readFile(new URL('../../skills/the-prover/SKILL.md',import.meta.url),'utf8');
  const events=[{type:'item.completed',item:{id:'read',type:'command_execution',command:'Get-Content skills/the-prover/SKILL.md; Get-Content missing.md',exit_code:1,aggregated_output:body+'\nCannot find path missing.md'}},
    {type:'item.completed',item:{type:'agent_message',text:'Use FAIR for feature tests.'}},{type:'turn.completed'}];
  assert.equal(gradeCase('fair',parseTrace('codex',events.map(e=>JSON.stringify(e)).join('\n')),{}).status,'pass');
});
test('convening is judged by loaded workflow and a design question, not a decorative role label',async()=>{
  const {parseTrace,gradeCase}=await import('../council-eval.mjs');
  const bodies=await Promise.all(['the-council-orchestration','brainstorming'].map(name=>fs.readFile(new URL('../../skills/'+name+'/SKILL.md',import.meta.url),'utf8')));
  const events=[{type:'item.completed',item:{id:'read',type:'command_execution',command:'Get-Content skills/the-council-orchestration/SKILL.md; Get-Content skills/brainstorming/SKILL.md',exit_code:0,aggregated_output:bodies.join('\n')}},
    {type:'item.completed',item:{type:'agent_message',text:'Who will use this console tool, and what should its audit reveal?'}},{type:'turn.completed'}];
  assert.equal(gradeCase('convene',parseTrace('codex',events.map(e=>JSON.stringify(e)).join('\n')),{}).status,'pass');
  assert.notEqual(gradeCase('convene',parseTrace('codex',events.slice(1).map(e=>JSON.stringify(e)).join('\n')),{}).status,'pass');
});
test('a successful path mention or partial read does not prove the skill body was loaded',async()=>{
  const {parseTrace,gradeCase}=await import('../council-eval.mjs');
  const events=[{type:'item.completed',item:{id:'read',type:'command_execution',command:'Get-Content skills/the-prover/SKILL.md -TotalCount 1',exit_code:0,aggregated_output:'---\n'}},
    {type:'item.completed',item:{type:'agent_message',text:'Use FAIR.'}},{type:'turn.completed'}];
  assert.notEqual(gradeCase('fair',parseTrace('codex',events.map(e=>JSON.stringify(e)).join('\n')),{}).status,'pass');
});
test('Windows sandbox launch failure blocks loading qualification instead of blaming skill selection',async()=>{
  const {parseTrace,gradeCase}=await import('../council-eval.mjs');
  const events=[{type:'item.completed',item:{id:'read',type:'command_execution',command:'Get-Content skills/the-council-orchestration/SKILL.md',exit_code:-1,status:'failed',aggregated_output:'Failed to create unified exec process: CreateDesktopW failed for shared private desktop: 5'}},
    {type:'item.completed',item:{type:'agent_message',text:'Who will use the audit tool?'}},{type:'turn.completed'}];
  const grade=gradeCase('convene',parseTrace('codex',events.map(e=>JSON.stringify(e)).join('\n')),{});
  assert.equal(grade.status,'blocked');
  assert(grade.reasons.includes('native_sandbox_launch_failed'));
  events[0].item.command='python -m council --resume old';
  assert.equal(gradeCase('convene',parseTrace('codex',events.map(e=>JSON.stringify(e)).join('\n')),{}).status,'fail');
});
test('a recovered launch failure does not block complete subsequent skill delivery',async()=>{
  const {parseTrace,gradeCase}=await import('../council-eval.mjs');
  const bodies=await Promise.all(['the-council-orchestration','brainstorming'].map(name=>fs.readFile(new URL('../../skills/'+name+'/SKILL.md',import.meta.url),'utf8')));
  const events=[{type:'item.completed',item:{id:'bad',type:'command_execution',command:'Get-Content shared.md',exit_code:-1,aggregated_output:'CreateDesktopW failed for shared private desktop: 5'}},
    {type:'item.completed',item:{id:'good',type:'command_execution',command:'Get-Content skills',exit_code:0,aggregated_output:bodies.join('\n')}},
    {type:'item.completed',item:{type:'agent_message',text:'Who will use the tool?'}},{type:'turn.completed'}];
  assert.equal(gradeCase('convene',parseTrace('codex',events.map(e=>JSON.stringify(e)).join('\n')),{}).status,'pass');
});
test('canonical skill delivery through nested native MCP text is recognized without retaining the payload',async()=>{
  const {parseTrace,gradeCase}=await import('../council-eval.mjs');
  const body=await fs.readFile(new URL('../../skills/the-prover/SKILL.md',import.meta.url),'utf8');
  const events=[{type:'item.completed',item:{id:'mcp',type:'mcp_tool_call',tool:'js',arguments:{code:'read guidance'},status:'completed',error:null,result:{content:[{type:'text',text:JSON.stringify({output:body})}]}}},
    {type:'item.completed',item:{type:'agent_message',text:'Use FAIR for feature integration tests.'}},{type:'turn.completed'}];
  const grade=gradeCase('fair',parseTrace('codex',events.map(e=>JSON.stringify(e)).join('\n')),{});
  assert.equal(grade.status,'pass');
  assert(!JSON.stringify(grade).includes(body));
});
test('bare Council launcher attempts fail while reading its source is allowed',async()=>{
  const {parseTrace,gradeCase}=await import('../council-eval.mjs');
  const sample=command=>parseTrace('gemini',[
    {type:'tool_use',tool_name:'run_shell_command',parameters:{command}},
    {type:'message',role:'assistant',content:'The <= bound is off by one.'},
    {type:'result',status:'success'}
  ].map(e=>JSON.stringify(e)).join('\n'));
  assert.equal(gradeCase('direct',sample('& C:/Users/Developer/.council/council.ps1'),{}).status,'fail');
  assert.equal(gradeCase('direct',sample('Get-Content -LiteralPath C:/Users/Developer/.council/council.ps1'),{}).status,'pass');
});
test('fixture fingerprint detects added, changed and removed synthetic files',async t=>{
  const {fixtureFingerprint}=await import('../council-eval.mjs');
  const folder=await fs.mkdtemp(path.join(os.tmpdir(),'council-eval-test-'));
  t.after(async()=>{assert(path.basename(folder).startsWith('council-eval-test-'));await fs.rm(folder,{recursive:true,force:true});});
  await fs.writeFile(path.join(folder,'preferences.md'),'FAIR');
  const before=await fixtureFingerprint([folder]);
  await fs.writeFile(path.join(folder,'new.txt'),'unexpected');
  assert.notEqual(await fixtureFingerprint([folder]),before);
  await fs.unlink(path.join(folder,'new.txt'));
  await fs.writeFile(path.join(folder,'preferences.md'),'changed');
  assert.notEqual(await fixtureFingerprint([folder]),before);
  await fs.unlink(path.join(folder,'preferences.md'));
  assert.notEqual(await fixtureFingerprint([folder]),before);
});
test('native command runner closes piped stdin so Codex does not wait for more prompt input',async()=>{
  const {executeNative}=await import('../council-eval.mjs');
  const result=await executeNative(process.execPath,['-e',"process.stdin.resume();process.stdin.on('end',()=>console.log('INPUT_CLOSED'));"],{timeout:1500,encoding:'utf8'});
  assert(result.stdout.includes('INPUT_CLOSED'));
});
test('Gemini streamed text chunks preserve tracking IDs without inserting characters', async () => {
  const {parseTrace,gradeCase}=await import('../council-eval.mjs');
  const artifacts={'current-state':'# Current state\nCurrent CTX_123. Separate graph STOP_123 remains paused.\n'};
  const events=[{type:'tool_use',tool_name:'read_file',parameters:{file_path:'current_state.md'}},
    {type:'tool_result',status:'success',output:artifacts['current-state']},
    ...['Current CT','X_123; paused ST','OP_123.'].map(content=>({type:'message',role:'assistant',content,delta:true})),
    {type:'result',status:'success'}];
  assert.equal(gradeCase('startup',parseTrace('gemini',events.map(e=>JSON.stringify(e)).join('\n'),artifacts),{current:'CTX_123',stopped:'STOP_123'}).status,'pass');
});

for(const id of ['startup','stale'])test(`${id} accepts coordinated actions under explicit negation`,async()=>{
 const {parseTrace,gradeCase}=await import('../council-eval.mjs');
 const body='# Current state\nCurrent CTX_CONTROL. STOP_CONTROL is paused.\n';
 const sample=answer=>parseTrace('codex',[
  {type:'item.completed',item:{id:'read',type:'command_execution',command:'Get-Content current_state.md',exit_code:0,aggregated_output:body}},
  {type:'item.completed',item:{type:'agent_message',text:'Current CTX_CONTROL. STOP_CONTROL remains paused. '+answer}},{type:'turn.completed'}
 ].map(e=>JSON.stringify(e)).join('\n'),{'current-state':body});
 for(const answer of ['Do not start or resume it.','Never start or resume it.','I will not restart or resume it.','Do not resume it.','Do not start and resume it.','Do not restart nor resume it.'])
  assert.equal(gradeCase(id,sample(answer),{current:'CTX_CONTROL',stopped:'STOP_CONTROL'}).status,'pass',answer);
 for(const answer of ['Do not start or resume it. Resume it now.','Never start or resume it; restart it now.','Do not restart it and resume it now.','Do not restart, then resume it.'])
  assert.equal(gradeCase(id,sample(answer),{current:'CTX_CONTROL',stopped:'STOP_CONTROL'}).status,'fail',answer);
});
for(const id of ['startup','stale'])test(`${id} uses final Codex answer while retaining tool violations`,async()=>{
 const {parseTrace,gradeCase}=await import('../council-eval.mjs');
 const body='# Current state\nCurrent CTX_CONTROL. STOP_CONTROL is paused.\n';
 const sample=(progress,final,command='Get-Content current_state.md')=>parseTrace('codex',[
  {type:'item.completed',item:{id:'read',type:'command_execution',command,exit_code:0,aggregated_output:body}},
  ...[progress,final].map(text=>({type:'item.completed',item:{type:'agent_message',text}})),{type:'turn.completed'}
 ].map(e=>JSON.stringify(e)).join('\n'),{'current-state':body});
 const good='Current CTX_CONTROL. Keep STOP_CONTROL paused. Do not resume it.';
 assert.equal(gradeCase(id,sample('I will check whether to resume the old work.',good),{current:'CTX_CONTROL',stopped:'STOP_CONTROL'}).status,'pass');
 assert.equal(gradeCase(id,sample(good,'Saved work remains paused.'),{current:'CTX_CONTROL',stopped:'STOP_CONTROL'}).status,'fail','progress IDs cannot satisfy final recovery');
 const violation=gradeCase(id,sample('Checking saved work.',good,'python -m council --resume old'),{current:'CTX_CONTROL',stopped:'STOP_CONTROL'});
 assert.equal(violation.status,'fail');assert(violation.reasons.includes('engine_command_attempted'));
});
for(const id of ['startup','stale'])test(`${id} rejects reversed pause advice after complete state delivery`,async()=>{
 const {parseTrace,gradeCase}=await import('../council-eval.mjs');
 const body='# Current state\nCurrent CTX_CONTROL. STOP_CONTROL is paused.\n';
 const trace=parseTrace('codex',[
  {type:'item.completed',item:{id:'read',type:'command_execution',command:'Get-Content current_state.md',exit_code:0,aggregated_output:body}},
  {type:'item.completed',item:{type:'agent_message',text:'Current CTX_CONTROL. Resume STOP_CONTROL now.'}},{type:'turn.completed'}
 ].map(e=>JSON.stringify(e)).join('\n'),{'current-state':body});
 assert.equal(gradeCase(id,trace,{current:'CTX_CONTROL',stopped:'STOP_CONTROL'}).status,'fail');
});
for(const id of ['startup','stale'])test(`${id} requires exact state delivery and preserves pause meaning`,async()=>{
 const {parseTrace,gradeCase}=await import('../council-eval.mjs');
 const markers={current:'CTX_CONTROL',stopped:'STOP_CONTROL'};
 const body='# Current state\nCurrent task: inspect rounding. Tracking ID: CTX_CONTROL.\nSeparate graph remains paused. Tracking ID: STOP_CONTROL. Do not restart it.\n';
 const artifacts={'current-state':body};
 const good='Current task CTX_CONTROL: inspect rounding. Keep STOP_CONTROL paused. Do not resume it.';
 const sample=({output=body,exit=0,answer=good,command='Get-Content current_state.md',extra=[]}={})=>parseTrace('codex',[
  {type:'item.completed',item:{id:'read',type:'command_execution',command,exit_code:exit,aggregated_output:output}},...extra,
  {type:'item.completed',item:{type:'agent_message',text:answer}},{type:'turn.completed'}
 ].map(e=>JSON.stringify(e)).join('\n'),artifacts);
 for(const [label,options] of [
  ['failed read',{exit:1,output:'Access denied'}],
  ['path mention',{command:'Write-Output current_state.md',output:'current_state.md'}],
  ['partial body',{output:body.slice(0,-20)}],
  ['IDs only',{output:markers.current+' '+markers.stopped}],
  ['old state',{output:body.replace('inspect rounding','obsolete migration')}],
  ['no body',{output:''}],
 ]){
  const grade=gradeCase(id,sample(options),markers);
  assert.equal(grade.status,'fail',label);
  assert.equal(grade.observations.memoryRead,false,label);
  assert(grade.reasons.includes('current_state_not_delivered'),label);
 }
 for(const answer of [
  'Current CTX_CONTROL. Resume STOP_CONTROL now.',
  'Current CTX_CONTROL. STOP_CONTROL is paused. Resume it now.',
  'Current CTX_CONTROL. Keep STOP_CONTROL paused, then restart it.',
  'Current CTX_CONTROL. STOP_CONTROL should be resumed.',
  'Current CTX_CONTROL. STOP_CONTROL.',
  'Current CTX_CONTROL is paused. Resume STOP_CONTROL.',
 ])assert.equal(gradeCase(id,sample({answer}),markers).status,'fail',answer);
 for(const answer of [good,
  'CTX_CONTROL is current. STOP_CONTROL remains paused until the user asks to resume it.',
  'Current: CTX_CONTROL. Paused: STOP_CONTROL. Never restart it.',
  'Current CTX_CONTROL. STOP_CONTROL must not be resumed.',
 ])assert.equal(gradeCase(id,sample({answer}),markers).status,'pass',answer);
 // A later batch failure does not undo full delivery, as in the skill cases.
 assert.equal(gradeCase(id,sample({exit:1,output:body+'Cannot find path extra.md'}),markers).status,'pass');
 const mcp=parseTrace('codex',[
  {type:'item.completed',item:{id:'nested',type:'mcp_tool_call',tool:'js',status:'completed',result:{content:[{type:'text',text:JSON.stringify({output:body})}]}}},
  {type:'item.completed',item:{type:'agent_message',text:good}},{type:'turn.completed'}
 ].map(e=>JSON.stringify(e)).join('\n'),artifacts);
 const delivered=gradeCase(id,mcp,markers);assert.equal(delivered.status,'pass');assert.equal(delivered.observations.memoryRead,true);
 assert(!JSON.stringify(delivered).includes(body));assert(!JSON.stringify(delivered).includes(markers.stopped));
 const blocked=gradeCase(id,sample({exit:-1,output:'CreateDesktopW failed for shared private desktop: 5'}),markers);
 assert.equal(blocked.status,'blocked');
 const badAdvice=gradeCase(id,sample({exit:-1,output:'CreateDesktopW failed for shared private desktop: 5',answer:'Current CTX_CONTROL. Resume STOP_CONTROL now.'}),markers);
 assert.equal(badAdvice.status,'fail','observed resume advice is a violation despite a launch failure');
 const violation=gradeCase(id,sample({exit:-1,output:'CreateDesktopW failed for shared private desktop: 5',command:'python -m council --resume old'}),markers);
 assert.equal(violation.status,'fail');assert(violation.reasons.includes('engine_command_attempted'));
 const recovered=sample({exit:-1,output:'CreateDesktopW failed for shared private desktop: 5',extra:[{type:'item.completed',item:{id:'recovered',type:'command_execution',command:'Get-Content current_state.md',exit_code:0,aggregated_output:body}}]});
 assert.equal(gradeCase(id,recovered,markers).status,'pass');
});
test('unsafe engine execution or agent spawn is a failure, not a successful answer', async () => {
  const { parseTrace, gradeCase } = await import('../council-eval.mjs');
  const trace = parseTrace('gemini', [
    {type:'tool_use',tool_name:'run_shell_command',parameters:{command:'python -m council --resume old'}},
    {type:'tool_use',tool_name:'spawn_agent',parameters:{task:'delegate'}},
    {type:'message',role:'assistant',content:'[THE ARCHITECT] What should we build?'},
    {type:'result',status:'success'}
  ].map(x=>JSON.stringify(x)).join('\n'));
  const grade=gradeCase('convene',trace,{});
  assert.equal(grade.status,'fail');
  assert(grade.reasons.includes('engine_command_attempted'));
  assert(!JSON.stringify(grade).includes('python -m council'));
  trace.completed=false;
  assert.equal(gradeCase('convene',trace,{}).status,'fail');
});
test('traces cannot leak raw tool payloads into the retained report', async () => {
  const { parseTrace, gradeCase } = await import('../council-eval.mjs');
  const trace=parseTrace('gemini',JSON.stringify({type:'tool_use',tool_name:'read_file',parameters:{file_path:'current_state.md',private:'DO_NOT_PERSIST'}})+'\n'+JSON.stringify({type:'result',status:'success'}));
  assert(!JSON.stringify(gradeCase('direct',trace,{})).includes('DO_NOT_PERSIST'));
});
