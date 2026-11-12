import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';

test('Codex evaluation requires a completed turn and actual memory retrieval evidence', async () => {
  const { parseTrace, gradeCase } = await import('../council-eval.mjs');
  const trace = parseTrace('codex', [
    {type:'item.completed',item:{id:'1',type:'command_execution',command:'node council-codex.mjs onboard',exit_code:0}},
    {type:'item.completed',item:{id:'2',type:'agent_message',text:'Current CTX_123; stopped STOP_123.'}},
    {type:'turn.completed'}
  ].map(x=>JSON.stringify(x)).join('\n'));
  assert.equal(gradeCase('startup', trace, {current:'CTX_123',stopped:'STOP_123'}).status, 'pass');
  trace.completed = false;
  assert.equal(gradeCase('startup', trace, {current:'CTX_123',stopped:'STOP_123'}).status, 'blocked');
});
test('final self-report cannot substitute for tool evidence and fixture IDs', async () => {
  const { parseTrace, gradeCase } = await import('../council-eval.mjs');
  const trace = parseTrace('codex', JSON.stringify({type:'item.completed',item:{type:'agent_message',text:'Council loaded; I read memory.'}})+'\n'+JSON.stringify({type:'turn.completed'}));
  assert.equal(gradeCase('startup', trace, {current:'CTX_123',stopped:'STOP_123'}).status, 'fail');
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
  const events=[{type:'tool_use',tool_name:'read_file',parameters:{file_path:'current_state.md'}},
    ...['Current CT','X_123; paused ST','OP_123.'].map(content=>({type:'message',role:'assistant',content,delta:true})),
    {type:'result',status:'success'}];
  assert.equal(gradeCase('startup',parseTrace('gemini',events.map(e=>JSON.stringify(e)).join('\n')),{current:'CTX_123',stopped:'STOP_123'}).status,'pass');
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
