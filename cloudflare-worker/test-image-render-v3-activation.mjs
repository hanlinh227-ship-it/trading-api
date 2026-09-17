import assert from 'node:assert/strict';
import {ACTIVATION_STAGES,advanceActivation,evaluateActivation} from './image-render/activation.js';
import {buildStaticActivationEvidence} from './image-render/activation-evidence.js';
import {getProviderAdapter} from './image-render/provider-adapter-registry.js';
import {getModelVaultEntry} from './image-render/model-vault.js';

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
  modelId:'sdxl',family:'stable-diffusion',version:'1.0',
  canonicalRepo:'stabilityai/stable-diffusion',providerModelId:'@cf/stabilityai/sdxl',
  license:'CreativeML-Open-RAIL++-M',codeLicense:'CreativeML-Open-RAIL++-M',weightsLicense:'CreativeML-Open-RAIL++-M',
  commercialUseEligible:true,redistributionEligible:false,
  runtimeProviders:['ai_horde'],runtimeConfigured:true,supportedTasks:['TEXT_TO_IMAGE'],
  referenceSupport:false,editSupport:false,criticSupport:false,
  minResolution:{width:256,height:256},maxResolution:{width:1536,height:1536},
  qualityBenchmarks:{},approvalStatus:'CANDIDATE',
  monetaryCost:'zero',status:'CANDIDATE',lastVerifiedAt:'2026-09-16',notes:'',
};
const base={model,adapter,taskType:'TEXT_TO_IMAGE'};

let result=evaluateActivation(base);
assert.equal(result.stage,'CANDIDATE');
assert.ok(result.blockers.includes('runtime_not_discovered'));
assert.equal(result.status,'CANDIDATE');

result=evaluateActivation({...base,evidence:{runtimeDiscovered:{ok:true,at:'2026-09-16',source:'provider model listing'}}});
assert.equal(result.stage,'RUNTIME_DISCOVERED');
assert.ok(result.blockers.includes('runtime_health_not_verified'));

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

result=evaluateActivation({...base,evidence:{...priv,benchmark:{ok:false,at:'2026-09-16',taskType:'TEXT_TO_IMAGE',samples:12,average:41,verifiedRate:1}}});
assert.equal(result.stage,'PRIVACY_VERIFIED');
result=evaluateActivation({...base,evidence:{...priv,benchmark:{ok:true,at:'2026-09-16',taskType:'CHARACTER_CONSISTENCY',samples:12,average:91,verifiedRate:1}}});
assert.equal(result.stage,'PRIVACY_VERIFIED','benchmark for another task must not activate this one');
result=evaluateActivation({...base,evidence:{...priv,benchmark:{ok:true,at:'2026-09-16',taskType:'TEXT_TO_IMAGE',samples:12,average:91,verifiedRate:0.5}}});
assert.equal(result.stage,'PRIVACY_VERIFIED','low verified rate must not pass benchmark gate');
result=evaluateActivation({...base,evidence:{...priv,benchmark:{ok:true,at:'2026-09-16',taskType:'TEXT_TO_IMAGE',samples:2,average:99,verifiedRate:1}}});
assert.equal(result.stage,'PRIVACY_VERIFIED','too few samples must not pass benchmark gate');

const full={...priv,benchmark:{ok:true,at:'2026-09-16',taskType:'TEXT_TO_IMAGE',samples:12,average:91,verifiedRate:0.92}};
result=evaluateActivation({...base,evidence:full});
assert.equal(result.stage,'ACTIVE');
assert.equal(result.status,'ACTIVE');
assert.deepEqual(result.blockers,[]);
assert.equal(result.evidenceTrail.length,5,'every stage keeps its evidence record');

result=evaluateActivation({...base,adapter:{...adapter,monetaryCost:'unknown'},evidence:full});
assert.equal(result.status,'DISABLED');
assert.ok(result.blockers.some(b=>b.includes('monetaryCost')));

for(const evidence of [
  {...full,license:{ok:false,at:'2026-09-16',detail:'non_commercial'}},
  {...full,privacy:{ok:false,at:'2026-09-16',detail:'retains_user_images'}},
])assert.equal(evaluateActivation({...base,evidence}).status,'DISABLED');

result=evaluateActivation({...base,evidence:{...full,regression:{degraded:true,at:'2026-09-16',detail:'critic pass rate fell'}}});
assert.equal(result.status,'DEGRADED');

const advanced=advanceActivation(base.model,evaluateActivation({...base,evidence:full}));
assert.equal(advanced.status,'ACTIVE');
assert.equal(advanced.activation.taskType,'TEXT_TO_IMAGE');
assert.equal(advanced.activation.evidenceTrail.length,5);
assert.equal(model.status,'CANDIDATE','input entry must not be mutated');

{
  const cf=getProviderAdapter('cloudflare_workers_ai');
  const flux=getModelVaultEntry('flux-1-schnell');
  const staticEvidence=buildStaticActivationEvidence({model:flux,adapter:cf,taskType:'TEXT_TO_IMAGE',at:'2026-09-17T00:00:00Z'});
  assert.equal(staticEvidence.license.ok,true);
  assert.equal(staticEvidence.privacy.ok,true);
  assert.match(staticEvidence.license.source,/^https:\/\//);
  assert.match(staticEvidence.privacy.source,/^https:\/\//);
  const ref=getModelVaultEntry('stable-diffusion-v1-5-img2img');
  const refEvidence=buildStaticActivationEvidence({model:ref,adapter:cf,taskType:'REFERENCE_GENERATION'});
  assert.equal(refEvidence.privacy.ok,true);
  const horde=getProviderAdapter('ai_horde');
  assert.equal(buildStaticActivationEvidence({model:ref,adapter:horde,taskType:'REFERENCE_GENERATION'}).privacy.ok,false);
}

console.log('image render v3 runtime activation contracts: PASS');

{
  const refModel={...model,supportedTasks:['REFERENCE_GENERATION'],referenceSupport:true};
  const unsafeAdapter={...adapter,supportedTasks:['REFERENCE_GENERATION'],referenceSafe:false,privacyClasses:['PUBLIC']};
  const evidence={
    runtimeDiscovered:{ok:true,at:'2026-09-16',source:'x'},
    health:{ok:true,at:'2026-09-16',detail:'x'},
    license:{ok:true,at:'2026-09-16',source:'x'},
    privacy:{ok:true,at:'2026-09-16',source:'x'},
    benchmark:{ok:true,at:'2026-09-16',taskType:'REFERENCE_GENERATION',samples:12,average:95,verifiedRate:1},
  };
  const unsafe=evaluateActivation({model:refModel,adapter:unsafeAdapter,taskType:'REFERENCE_GENERATION',evidence});
  assert.notEqual(unsafe.status,'ACTIVE');
  const safeAdapter={...adapter,supportedTasks:['REFERENCE_GENERATION'],referenceSafe:true,privacyClasses:['PUBLIC','CONFIDENTIAL']};
  const safe=evaluateActivation({model:refModel,adapter:safeAdapter,taskType:'REFERENCE_GENERATION',evidence});
  assert.equal(safe.status,'ACTIVE',JSON.stringify(safe.blockers));
}

console.log('image render v3 activation gate delegation contracts: PASS');
