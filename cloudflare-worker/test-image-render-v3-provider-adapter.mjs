import assert from 'node:assert/strict';
import {PROVIDER_ADAPTER_REQUIRED_FIELDS,describeProviderAdapter,validateProviderAdapter} from './image-render/provider-adapter.js';

// Section 15 contract: every field is required, and a provider missing any of them is
// inactive rather than quietly half-registered.
assert.deepEqual([...PROVIDER_ADAPTER_REQUIRED_FIELDS].sort(),[
  'autoPurchase','baseUrl','costMode','healthEndpoint','id','licenseEvidence','maxResolution',
  'monetaryCost','paidFallback','privacyClasses','provenance','queueBehavior','rateLimitBehavior',
  'referenceSafe','retryPolicy','supportedModels','supportedTasks','timeout','type',
].sort());

const adapter={
  id:'ai_horde',
  type:'community_volunteer_compute',
  baseUrl:'https://aihorde.net/api/v2',
  costMode:'FREE_ONLY',
  monetaryCost:'zero',
  paidFallback:false,
  autoPurchase:false,
  privacyClasses:['PUBLIC'],
  referenceSafe:false,
  supportedTasks:['TEXT_TO_IMAGE','MULTI_SCENE_BATCH'],
  supportedModels:['stable_diffusion_xl'],
  maxResolution:{width:1536,height:1536},
  healthEndpoint:'/status/heartbeat',
  queueBehavior:'async_poll',
  timeout:{submitMs:20000,pollMs:15000},
  retryPolicy:{maxAttempts:3,backoff:'exponential'},
  rateLimitBehavior:'fail_closed',
  provenance:'https://github.com/Haidra-Org/AI-Horde',
  licenseEvidence:'AGPL-3.0 horde software; per-model licenses tracked in the model vault',
};
assert.equal(validateProviderAdapter(adapter).ok,true,JSON.stringify(validateProviderAdapter(adapter).errors));

// Any missing field makes the adapter inactive.
for(const field of PROVIDER_ADAPTER_REQUIRED_FIELDS){
  const {[field]:_dropped,...partial}=adapter;
  const result=validateProviderAdapter(partial);
  assert.equal(result.ok,false,`missing ${field} must be rejected`);
  assert.ok(result.errors.some(e=>e.includes(field)),`${field}: ${result.errors}`);
  assert.equal(describeProviderAdapter(partial).active,false);
}

// FREE_ONLY is a hard gate, not a label.
for(const override of [
  {monetaryCost:'unknown'},
  {monetaryCost:'0.01'},
  {paidFallback:true},
  {autoPurchase:true},
  {costMode:'PAID'},
  {costMode:'FREE_TRIAL'},
]){
  const result=validateProviderAdapter({...adapter,...override});
  assert.equal(result.ok,false,`${JSON.stringify(override)} must be rejected`);
}

// A synchronous provider has no poll step, so 0 is valid there, but submitMs is required
// and no timeout may be negative.
assert.equal(validateProviderAdapter({...adapter,timeout:{submitMs:30000,pollMs:0,cancelMs:0}}).ok,true);
assert.equal(validateProviderAdapter({...adapter,timeout:{pollMs:1000}}).ok,false);
assert.equal(validateProviderAdapter({...adapter,timeout:{submitMs:30000,pollMs:-1}}).ok,false);

// Privacy classes must be explicit and known; a reference-unsafe provider may never
// advertise a non-public class.
assert.equal(validateProviderAdapter({...adapter,privacyClasses:[]}).ok,false);
assert.equal(validateProviderAdapter({...adapter,privacyClasses:['SECRET']}).ok,false);
assert.equal(validateProviderAdapter({...adapter,privacyClasses:['PUBLIC','CONFIDENTIAL']}).ok,false,
  'a referenceSafe=false provider must not accept non-public data');
assert.equal(validateProviderAdapter({...adapter,referenceSafe:true,privacyClasses:['PUBLIC','CONFIDENTIAL']}).ok,true);

// A reference-unsafe provider may not claim reference/edit tasks.
assert.equal(validateProviderAdapter({...adapter,supportedTasks:['REFERENCE_GENERATION']}).ok,false);
assert.equal(validateProviderAdapter({...adapter,referenceSafe:true,privacyClasses:['PUBLIC','CONFIDENTIAL'],supportedTasks:['REFERENCE_GENERATION']}).ok,true);

// describeProviderAdapter reports why a provider is inactive, for the activation report.
const described=describeProviderAdapter(adapter);
assert.equal(described.active,true);
assert.equal(described.id,'ai_horde');
assert.equal(described.referenceSafe,false);
assert.deepEqual(described.blockers,[]);

console.log('image render v3 provider adapter contracts: PASS');
