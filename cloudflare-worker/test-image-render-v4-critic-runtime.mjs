import assert from 'node:assert/strict';
import {createVisualCriticRuntime,visualCriticAvailability} from './image-render/critic-runtime.js';
import {decideQualityAction} from './image-render/critic.js';

// With no AI binding there is no critic, and the system must say so rather than pretend.
assert.deepEqual(await visualCriticAvailability({}),{available:false,provider:null,model:null,reason:'workers_ai_binding_unavailable'});
const none=createVisualCriticRuntime();
let result=await none.review({},{intent:{taskType:'TEXT_TO_IMAGE',promptCompiled:'a blue square'},image:[1]});
assert.equal(result.ok,false);
assert.equal(result.reason,'visual_critic_unavailable');
// A metadata-only result must never become a verified pass.
assert.equal(decideQualityAction(result).decision,'PASS_UNVERIFIED');
assert.equal(decideQualityAction(result).verified,false);

const availability=await visualCriticAvailability({AI:{run:async()=>({})}});
assert.equal(availability.available,true);
assert.equal(availability.provider,'cloudflare_workers_ai');
assert.match(availability.model,/^@cf\//);

// A real critic response is normalised into dimensions and problems the decision layer uses.
const good={AI:{async run(){return {response:JSON.stringify({
  overallScore:93,confidence:0.9,
  dimensions:{promptAdherence:95,objectCount:100,composition:90,anatomy:92,styleAccuracy:90,textAccuracy:88},
  problems:[],
})};}}};
const critic=createVisualCriticRuntime();
result=await critic.review(good,{intent:{taskType:'TEXT_TO_IMAGE',promptCompiled:'a blue square'},image:[1]});
assert.equal(result.ok,true);
assert.equal(result.overallScore,93);
assert.equal(result.dimensions.promptAdherence,95);
const decision=decideQualityAction(result,{passThreshold:85});
assert.equal(decision.decision,'PASS');
assert.equal(decision.verified,true,'a real critic pass is the only way to be verified');

// A critic that reports a local defect drives a local repair, not a full redraw.
const defectEnv={AI:{async run(){return {response:JSON.stringify({
  overallScore:70,confidence:0.88,dimensions:{anatomy:40,promptAdherence:95},
  problems:[{code:'hand_anatomy',scope:'local',severity:'major',target:'left hand'}],
})};}}};
result=await critic.review(defectEnv,{intent:{taskType:'TEXT_TO_IMAGE',promptCompiled:'a person waving'},image:[1]});
assert.equal(result.ok,true);
assert.equal(decideQualityAction(result,{passThreshold:85}).decision,'REPAIR_LOCAL');

// Unparseable or non-JSON critic output is unverified, never an invented score.
for(const body of [{response:'the image looks nice'},{response:'{"overallScore":'},{},{response:JSON.stringify({overallScore:'high'})}]){
  const flaky={AI:{async run(){return body;}}};
  const out=await createVisualCriticRuntime().review(flaky,{intent:{taskType:'TEXT_TO_IMAGE',promptCompiled:'x'},image:[1]});
  assert.equal(out.ok,false,JSON.stringify(body));
  assert.equal(decideQualityAction(out).verified,false);
}

// A critic error is unverified, and exhausting the free allocation is a wait, not a pass.
const exhausted={AI:{async run(){const e=new Error('neurons');e.status=429;throw e;}}};
result=await createVisualCriticRuntime().review(exhausted,{intent:{taskType:'TEXT_TO_IMAGE',promptCompiled:'x'},image:[1]});
assert.equal(result.ok,false);
assert.equal(result.reason,'free_allocation_exhausted');
assert.equal(result.waitState,'WAITING_FOR_FREE_COMPUTE');
assert.equal(decideQualityAction(result).verified,false);

// The critic is asked about the dimensions of the task at hand, not a generic question.
const captured=[];
const probe={AI:{async run(model,input){captured.push({model,input});return {response:'{}'};}}};
await createVisualCriticRuntime().review(probe,{intent:{taskType:'REFERENCE_GENERATION',promptCompiled:'same character'},image:[1]});
const asked=JSON.stringify(captured[0].input);
for(const dimension of ['identitySimilarity','wardrobeConsistency','subjectCount'])assert.ok(asked.includes(dimension),dimension);

console.log('image render v4 visual critic runtime contracts: PASS');
