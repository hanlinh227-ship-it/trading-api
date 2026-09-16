import assert from 'node:assert/strict';
import {ACTIVATION_STAGES,advanceActivation,evaluateActivation} from './image-render/activation.js';

// Section 5 flow, in order.
assert.deepEqual([...ACTIVATION_STAGES],[
  'CANDIDATE','RUNTIME_DISCOVERED','HEALTH_VERIFIED','LICENSE_VERIFIED','PRIVACY_VERIFIED','BENCHMARKED','ACTIVE',
]);

const adapter={
  id:'ai_horde',type:'community_volunteer_compute',baseUrl:'https://aihorde.net/api/v2',
  costMode:'FREE_ONLY',monetaryCost:'zero',paidFallback:false,autoPurchase:false,
  privacyClasses:['PUBLIC'],referenceSafe:false,
  supportedTasks:['TEXT_TO_IMAGE'],supportedModels:['sdxl'],
  maxResolution:{width:1536,height:1536},healthEndpoint:'/status/heartbeat',
  queueBehavior:'async_poll',timeout:{submitMs:20000},retryPolicy:{maxAttempts:3},
  rateLimitBehavior:'fail_closed',provenance:'https://github.com/Haidra-Org/AI-Horde',
  licenseEvidence:'per-model licenses tracked in the model vault',
};
const model={
  modelId:'sdxl',family:'stable-diffusion',version:'1.0',license:'CreativeML-Open-RAIL++-M',
  codeLicense:'Apache-2.0',weightsLicense:'CreativeML-Open-RAIL++-M',
  runtimeProviders:['ai_horde'],supportedTasks:['TEXT_TO_IMAGE'],
  referenceSupport:false,editSupport:false,criticSupport:false,
  minResolution:{width:256,height:256},maxResolution:{width:1536,height:1536},
  monetaryCost:'zero',status:'CANDIDATE',lastVerifiedAt:'2026-09-16',
};
const base={model,adapter,taskType:'TEXT_TO_IMAGE'};

// No evidence at all: stays CANDIDATE and says what is missing.
let result=evaluateActivation(base);
assert.equal(result.stage,'CANDIDATE');
assert.ok(result.blockers.includes('runtime_not_discovered'));
assert.equal(result.status,'CANDIDATE');

// Runtime discovered but never probed: cannot claim health.
result=evaluateActivation({...base,evidence:{runtimeDiscovered:{ok:true,at:'2026-09-16',source:'provider model listing'}}});
assert.equal(result.stage,'RUNTIME_DISCOVERED');
assert.ok(result.blockers.includes('runtime_health_not_verified'));

// A failed probe never advances the stage.
result=evaluateActivation({...base,evidence:{
  runtimeDiscovered:{ok:true,at:'2026-09-16',source:'provider model listing'},
  health:{ok:false,at:'2026-09-16',detail:'provider_unreachable'},
}});
assert.equal(result.stage,'RUNTIME_DISCOVERED');
assert.ok(result.blockers.includes('runtime_health_not_verified'));

const healthy={
  runtimeDiscovered:{ok:true,at:'2026-09-16',source:'provider model listing'},
  health:{ok:true,at:'2026-09-16',detail:'workers_available=4'},
};

// Licence is verified from the vault record, not assumed.
result=evaluateActivation({...base,evidence:healthy});
assert.equal(result.stage,'HEALTH_VERIFIED');
assert.ok(result.blockers.includes('license_not_verified'));

const licensed={...healthy,license:{ok:true,at:'2026-09-16',source:'upstream repository LICENSE'}};
result=evaluateActivation({...base,evidence:licensed});
assert.equal(result.stage,'LICENSE_VERIFIED');
assert.ok(result.blockers.includes('privacy_not_verified'));

const priv={...licensed,privacy:{ok:true,at:'2026-09-16',source:'provider privacy documentation'}};
result=evaluateActivation({...base,evidence:priv});
assert.equal(result.stage,'PRIVACY_VERIFIED');
assert.ok(result.blockers.includes('benchmark_not_passed'));

// Benchmark evidence is per task and must actually pass.
result=evaluateActivation({...base,evidence:{...priv,benchmark:{ok:false,at:'2026-09-16',taskType:'TEXT_TO_IMAGE',samples:12,average:41}}});
assert.equal(result.stage,'PRIVACY_VERIFIED');
result=evaluateActivation({...base,evidence:{...priv,benchmark:{ok:true,at:'2026-09-16',taskType:'CHARACTER_CONSISTENCY',samples:12,average:91}}});
assert.equal(result.stage,'PRIVACY_VERIFIED','benchmark for another task must not activate this one');

const full={...priv,benchmark:{ok:true,at:'2026-09-16',taskType:'TEXT_TO_IMAGE',samples:12,average:91}};
result=evaluateActivation({...base,evidence:full});
assert.equal(result.stage,'ACTIVE');
assert.equal(result.status,'ACTIVE');
assert.deepEqual(result.blockers,[]);
assert.equal(result.evidenceTrail.length,5,'every stage keeps its evidence record');

// A broken adapter can never reach ACTIVE, whatever the evidence says.
result=evaluateActivation({...base,adapter:{...adapter,monetaryCost:'unknown'},evidence:full});
assert.equal(result.status,'DISABLED');
assert.ok(result.blockers.some(b=>b.includes('monetaryCost')));

// Cost/licence/privacy failures DISABLE rather than merely hold.
for(const evidence of [
  {...full,license:{ok:false,at:'2026-09-16',detail:'non_commercial'}},
  {...full,privacy:{ok:false,at:'2026-09-16',detail:'retains_user_images'}},
]){
  assert.equal(evaluateActivation({...base,evidence}).status,'DISABLED');
}

// A quality regression demotes an active model to DEGRADED, it does not silently stay ACTIVE.
result=evaluateActivation({...base,evidence:{...full,regression:{degraded:true,at:'2026-09-16',detail:'critic pass rate fell'}}});
assert.equal(result.status,'DEGRADED');

// advanceActivation records the outcome on the vault entry without mutating the input.
const advanced=advanceActivation(base.model,evaluateActivation({...base,evidence:full}));
assert.equal(advanced.status,'ACTIVE');
assert.equal(advanced.activation.taskType,'TEXT_TO_IMAGE');
assert.equal(advanced.activation.evidenceTrail.length,5);
assert.equal(model.status,'CANDIDATE','input entry must not be mutated');

console.log('image render v3 runtime activation contracts: PASS');
