import test from 'node:test';
import assert from 'node:assert/strict';
import {cases,gradeCase,parseTrace} from '../council-eval.mjs';
const artifacts={'reply-rules':'# Current reply rules\nReview meaning before delivery.'};
function grade(id,text,delivered=true){
 const events=[];
 if(delivered)events.push({type:'item.completed',item:{type:'command_execution',command:'Get-Content shared.md',exit_code:0,aggregated_output:artifacts['reply-rules']}});
 events.push({type:'item.completed',item:{type:'agent_message',text}},{type:'turn.completed'});
 return gradeCase(id,parseTrace('codex',events.map(e=>JSON.stringify(e)).join('\n'),artifacts),{});
}
test('reply cases are discoverable and missing review guidance cannot pass',()=>{
 for(const id of ['reply-clarity','reply-procedure','reply-evidence'])assert.equal(typeof cases[id],'string');
 assert.equal(grade('reply-clarity','I reviewed my answer.').status,'fail');
 assert.equal(grade('reply-clarity','shipping-service paused at 14:05 UTC. The cause is unknown. Inspect timeout logs.',false).status,'fail');
});
test('clarity preserves facts and uncertainty while rejecting dense source language',()=>{
 const good='shipping-service paused at 14:05 UTC. The cause is unknown. Inspect timeout logs next.';
 assert.equal(grade('reply-clarity',good).status,'pass');
 for(const bad of [good.replace('14:05','14:50'),good.replace('unknown','database failure'),good+' Operational cessation necessitates epistemic determination.'])assert.equal(grade('reply-clarity',bad).status,'fail');
});
test('procedure checks backup before migration and preserves the failure stop condition',()=>{
 const good='1. Create a backup.\n2. Run ApplySchemaV2.\n3. If ApplySchemaV2 fails, stop. Keep the worker stopped.\n4. If ApplySchemaV2 succeeds, start the worker.';
 assert.equal(grade('reply-procedure',good).status,'pass');
 for(const bad of [good.replace('Create a backup.','Prepare files.'),good.replaceAll('ApplySchemaV2','ApplySchemaV3'),'Run ApplySchemaV2. Create a backup. Stop on failure. Start the worker on success.'])assert.equal(grade('reply-procedure',bad).status,'fail');
});
test('evidence rejects deployment certainty and preserves the narrow test result',()=>{
 const good='12 unit tests passed. Database integration tests did not run. Production safety is unverified. Run the database integration tests next.';
 assert.equal(grade('reply-evidence',good).status,'pass');
 for(const bad of [good.replace('12','21'),'12 unit tests passed. Database integration tests did not run. Production is safe.', 'I reviewed the reply. Everything passed.'])assert.equal(grade('reply-evidence',bad).status,'fail');
 assert(!JSON.stringify(grade('reply-evidence',good+' PRIVATE_SAMPLE_TEXT')).includes('PRIVATE_SAMPLE_TEXT'));
});

test('guards reject a long update and an unconditional worker start',()=>{
 const long='shipping-service paused at 14:05 UTC and the cause is unknown and we must inspect timeout logs and the team must determine the exact cause before it can make any claim about why the service stopped.';
 assert.equal(grade('reply-clarity',long).status,'fail');
 const unsafe='1. Create a backup.\n2. Run ApplySchemaV2.\n3. Start the worker now.\n4. If ApplySchemaV2 fails, stop and keep the worker stopped.\n5. If ApplySchemaV2 succeeds, start the worker.';
 assert.equal(grade('reply-procedure',unsafe).status,'fail');
});

test('answer quality and observed rule delivery remain separate',()=>{
 const result=grade('reply-clarity','shipping-service paused at 14:05 UTC. The cause is unknown. Inspect timeout logs.',false);
 assert.equal(result.status,'fail');
 assert.equal(result.observations.replyOutputChecksPassed,true);
 assert.equal(result.observations.replyReviewGuidanceObserved,false);
});

test('answer order puts deployment status and next action before evidence',()=>{
 assert.equal(typeof cases['reply-order'],'string');
 const opening='Deployment is not authorized. Run the database integration tests before requesting deployment approval.';
 const evidence='12 unit tests passed. Database integration tests did not run. Production safety is unverified.';
 assert.equal(grade('reply-order',opening+'\n\n'+evidence).status,'pass');
 assert.equal(grade('reply-order','# Release status\n\n'+opening+'\n\n'+evidence).status,'pass');
 assert.equal(grade('reply-order','- Deployment is not authorized.\n- Run the database integration tests before requesting deployment approval.\n\n'+evidence).status,'pass');
 for(const bad of [evidence+'\n\n'+opening,'Deployment is not authorized.\n\n'+evidence+'\n\nRun the database integration tests before requesting deployment approval.',opening.replace('not authorized','authorized')+'\n\n'+evidence,opening+'\n\n'+evidence.replace('12','21'),opening+'\n\n'+evidence.replace('unverified','verified')])assert.equal(grade('reply-order',bad).status,'fail');
 const unseen=grade('reply-order',opening+'\n\n'+evidence,false);
 assert.equal(unseen.observations.replyOutputChecksPassed,true);
 assert.equal(unseen.observations.replyReviewGuidanceObserved,false);
});
test('unknown authorization stays unknown and explanation scope stays separate',()=>{
 const good='Deployment authorization status is unknown. Ask the release owner to confirm deployment authorization.\n\nNo authorization record was supplied.';
 assert.equal(grade('reply-order-unknown',good).status,'pass');
 for(const bad of [good.replace('unknown','approved'),good.replace('unknown','not authorized'),'Deployment is not authorized. Ask the release owner to confirm deployment authorization. No authorization record was supplied.',good.replace('Ask the release owner to confirm deployment authorization.','Run the deployment.')])assert.equal(grade('reply-order-unknown',bad).status,'fail');
 assert.equal(grade('direct','The <= condition is an off-by-one error.').status,'pass');
});

test('answer order cannot hide an approval-sequence reversal',()=>{
 const evidence='12 unit tests passed. Database integration tests did not run. Production safety is unverified.';
 const reversed='Deployment is not authorized. Run the database integration tests after requesting deployment approval.';
 assert.equal(grade('reply-order',reversed+'\n\n'+evidence).status,'fail');
});

test('Codex answer-order grading uses the delivered final answer, not progress notes',()=>{
 const final='Deployment is not authorized. Run the database integration tests before requesting deployment approval.\n\n12 unit tests passed. Database integration tests did not run. Production safety is unverified.';
 const events=[{type:'item.completed',item:{type:'command_execution',command:'Get-Content shared.md',exit_code:0,aggregated_output:artifacts['reply-rules']}},{type:'item.completed',item:{type:'agent_message',text:'12 unit tests passed. I will read the instructions.'}},{type:'item.completed',item:{type:'agent_message',text:final}},{type:'turn.completed'}];
 assert.equal(gradeCase('reply-order',parseTrace('codex',events.map(e=>JSON.stringify(e)).join('\n'),artifacts),{}).status,'pass');
 events[1].item.text=final;events[2].item.text='12 unit tests passed. Database integration tests did not run. Production safety is unverified.\n\nDeployment is not authorized. Run the database integration tests before requesting deployment approval.';
 assert.equal(gradeCase('reply-order',parseTrace('codex',events.map(e=>JSON.stringify(e)).join('\n'),artifacts),{}).status,'fail');
});
