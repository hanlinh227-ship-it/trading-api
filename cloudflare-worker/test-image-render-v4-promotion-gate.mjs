import assert from 'node:assert/strict';
import {evaluateModelPromotion,evaluatePromotionGate,proposeModelPromotion,recordBenchmarkResult} from './image-render/benchmark-registry.js';
import {MODEL_VAULT_STATUSES,validateModelVaultEntry} from './image-render/model-vault.js';

// The vault state machine must name every stage of the promotion pipeline.
assert.deepEqual([...MODEL_VAULT_STATUSES],['CANDIDATE','BENCHMARKED','ACTIVE','DEGRADED','DISABLED']);

const entry={
  modelId:'demo',
  canonicalRepo:'org/repo',
  sourceRevision:'0123456789abcdef0123456789abcdef01234567',
  codeLicense:'Apache-2.0',
  weightsLicense:'Apache-2.0',
  commercialUseEligible:true,
  redistributionEligible:true,
  runtimeConfigured:true,
  approvalStatus:'BENCHMARKED',
  supportedTasks:['TEXT_TO_IMAGE'],
  monetaryCost:'zero',
};
const providerRegistration={
  providerId:'safe_free',
  modelId:'demo',
  monetaryCost:'zero',
  paidFallback:false,
  autoPurchase:false,
  supportedDataClasses:['PUBLIC'],
  referenceSafe:false,
  supportedTasks:['TEXT_TO_IMAGE'],
  health:'healthy',
  maxResolution:{width:2048,height:2048},
  baseUrl:'https://example.invalid',
  healthEndpoint:'/health',
  queueBehavior:'provider_managed',
  timeoutMs:120000,
  retryPolicy:{maxAttempts:3,backoff:'bounded_exponential'},
  rateLimitBehavior:'provider_declared',
  provenance:'verified test fixture',
  licenseEvidence:'verified test fixture',
};
assert.equal(validateModelVaultEntry(entry).ok,true,'BENCHMARKED must be a valid vault status');

let state={models:{}};
for(let i=0;i<10;i+=1)state=recordBenchmarkResult(state,{modelKey:'p::m',taskType:'TEXT_TO_IMAGE',score:92,verified:true});
const options={modelKey:'p::m',taskType:'TEXT_TO_IMAGE',minSamples:8,minAverage:85,minVerifiedRate:0.8};

// Benchmark evidence alone never makes a model ACTIVE.
let result=evaluateModelPromotion(state,options);
assert.equal(result.status,'BENCHMARKED');
assert.equal(result.gate.ok,false);

// A model whose runtime is not configured stays BENCHMARKED, however good the scores.
result=evaluateModelPromotion(state,{...options,gate:{vaultEntry:{...entry,runtimeConfigured:false},runtimeConfigured:false,runtimeHealthy:true,providerRegistration}});
assert.equal(result.status,'BENCHMARKED');
assert.ok(result.gate.blockers.includes('runtime_not_configured'));

// Nor does a configured runtime that has not been verified healthy.
result=evaluateModelPromotion(state,{...options,gate:{vaultEntry:entry,runtimeConfigured:true,runtimeHealthy:false,providerRegistration}});
assert.equal(result.status,'BENCHMARKED');
assert.ok(result.gate.blockers.includes('runtime_not_verified_healthy'));

// A configured/healthy boolean pair without a validated provider registration is not enough.
result=evaluateModelPromotion(state,{...options,gate:{vaultEntry:entry,runtimeConfigured:true,runtimeHealthy:true}});
assert.equal(result.status,'BENCHMARKED');
assert.ok(result.gate.blockers.includes('provider_registration_required'));

// Invalid or paid provider registration blocks promotion even if runtime health says true.
result=evaluateModelPromotion(state,{...options,gate:{vaultEntry:entry,runtimeConfigured:true,runtimeHealthy:true,providerRegistration:{...providerRegistration,monetaryCost:'paid'}}});
assert.equal(result.status,'BENCHMARKED');
assert.ok(result.gate.blockers.includes('non_zero_or_unknown_cost'));

// Reference/edit tasks require an explicitly reference-safe runtime; task support alone is insufficient.
const referenceEntry={...entry,supportedTasks:['REFERENCE_GENERATION']};
const unsafeReferenceProvider={...providerRegistration,supportedTasks:['REFERENCE_GENERATION'],referenceSafe:false};
let referenceGate=evaluatePromotionGate({vaultEntry:referenceEntry,runtimeConfigured:true,runtimeHealthy:true,providerRegistration:unsafeReferenceProvider,taskType:'REFERENCE_GENERATION'});
assert.equal(referenceGate.ok,false);
assert.ok(referenceGate.blockers.includes('reference_safe_runtime_required'));
referenceGate=evaluatePromotionGate({vaultEntry:referenceEntry,runtimeConfigured:true,runtimeHealthy:true,providerRegistration:{...unsafeReferenceProvider,referenceSafe:true},taskType:'REFERENCE_GENERATION'});
assert.equal(referenceGate.ok,true);

// Nor a non-free or non-commercial model license, whatever the runtime says.
result=evaluateModelPromotion(state,{...options,gate:{vaultEntry:{...entry,weightsLicense:'NON_COMMERCIAL'},runtimeConfigured:true,runtimeHealthy:true,providerRegistration}});
assert.equal(result.status,'BENCHMARKED');
result=evaluateModelPromotion(state,{...options,gate:{vaultEntry:{...entry,monetaryCost:'unknown'},runtimeConfigured:true,runtimeHealthy:true,providerRegistration}});
assert.equal(result.status,'BENCHMARKED');

// A DISABLED model can never be promoted back by benchmark evidence alone.
result=evaluateModelPromotion(state,{...options,gate:{vaultEntry:{...entry,approvalStatus:'DISABLED'},runtimeConfigured:true,runtimeHealthy:true,providerRegistration}});
assert.equal(result.status,'BENCHMARKED');
assert.ok(result.gate.blockers.includes('model_disabled'));

// Promotion is task-specific: a model may not go ACTIVE for a task it does not support.
result=evaluateModelPromotion(state,{...options,gate:{vaultEntry:entry,runtimeConfigured:true,runtimeHealthy:true,providerRegistration},taskType:'TEXT_TO_IMAGE'});
assert.equal(result.status,'ACTIVE');
const otherTaskGate=evaluatePromotionGate({vaultEntry:entry,runtimeConfigured:true,runtimeHealthy:true,providerRegistration,taskType:'CHARACTER_CONSISTENCY'});
assert.equal(otherTaskGate.ok,false);
assert.ok(otherTaskGate.blockers.includes('task_not_supported_by_model'));

// Insufficient evidence still holds the model at CANDIDATE even with a clean gate.
result=evaluateModelPromotion({models:{}},{...options,gate:{vaultEntry:entry,runtimeConfigured:true,runtimeHealthy:true,providerRegistration}});
assert.equal(result.status,'CANDIDATE');
assert.equal(result.reason,'insufficient_benchmark_evidence');

// A proposal is evidence for a human/CI gate, never a self-applied mutation.
const proposal=proposeModelPromotion(state,{...options,currentStatus:'CANDIDATE',gate:{vaultEntry:entry,runtimeConfigured:true,runtimeHealthy:true,providerRegistration}});
assert.equal(proposal.currentStatus,'CANDIDATE');
assert.equal(proposal.proposedStatus,'ACTIVE');
assert.equal(proposal.applied,false);
assert.equal(proposal.requiresApproval,true);
assert.ok(proposal.evidence.samples>=8);

console.log('image render v4 promotion gate contracts: PASS');
