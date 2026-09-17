import assert from 'node:assert/strict';
import {loadApprovedModelVault,validateModelVaultEntry} from './image-render/model-vault.js';

const selfHosted={
  modelId:'demo',canonicalRepo:'org/repo',sourceRevision:'0123456789abcdef0123456789abcdef01234567',
  codeLicense:'Apache-2.0',weightsLicense:'Apache-2.0',commercialUseEligible:true,
  redistributionEligible:true,runtimeConfigured:false,approvalStatus:'CANDIDATE',
  supportedTasks:['TEXT_TO_IMAGE'],monetaryCost:'zero',
};
// A model we could self-host must pin an exact revision.
assert.equal(validateModelVaultEntry(selfHosted).ok,true);
assert.equal(validateModelVaultEntry({...selfHosted,sourceRevision:''}).ok,false);

// A hosted-inference model has no revision we control: the provider serves its own build,
// so it is identified by the provider's model id instead. Inventing a git SHA would be a
// fabricated fact, so one is not required here.
const hosted={
  modelId:'flux-1-schnell',canonicalRepo:'black-forest-labs/FLUX.1-schnell',
  providerModelId:'@cf/black-forest-labs/flux-1-schnell',
  codeLicense:'Apache-2.0',weightsLicense:'Apache-2.0',commercialUseEligible:true,
  redistributionEligible:false,runtimeConfigured:true,approvalStatus:'CANDIDATE',
  supportedTasks:['TEXT_TO_IMAGE'],monetaryCost:'zero',
};
assert.equal(validateModelVaultEntry(hosted).ok,true,JSON.stringify(validateModelVaultEntry(hosted).errors));

// But it must identify itself somehow: neither a revision nor a provider model id is invalid.
const anonymous={...hosted};
delete anonymous.providerModelId;
assert.equal(validateModelVaultEntry(anonymous).ok,false);
assert.ok(validateModelVaultEntry(anonymous).errors.includes('exact_source_revision_or_provider_model_id_required'));

// A provider model id must look like a real provider-qualified id, not a bare name.
assert.equal(validateModelVaultEntry({...hosted,providerModelId:'flux'}).ok,false);

// The shipped vault registers the Workers AI models against a runtime provider.
const vault=loadApprovedModelVault();
const cf=vault.filter(e=>(e.runtimeProviders||[]).includes('cloudflare_workers_ai'));
assert.ok(cf.length>=4,'Workers AI models must be registered in the vault');
for(const entry of cf){
  assert.equal(validateModelVaultEntry(entry).ok,true,`${entry.modelId}: ${validateModelVaultEntry(entry).errors}`);
  assert.match(entry.providerModelId,/^@cf\//,entry.modelId);
  assert.equal(entry.monetaryCost,'zero');
  // Hosted models are never claimed as redistributable by this repository.
  assert.equal(entry.redistributionEligible,false,entry.modelId);
}
// A critic-capable model must be present, and a reference-capable edit model.
assert.ok(cf.some(e=>e.criticSupport===true));
assert.ok(cf.some(e=>e.editSupport===true&&e.supportedTasks.includes('INPAINT')));
// Nothing is ACTIVE yet: health and benchmark evidence still come from production.
assert.ok(vault.every(e=>e.status!=='ACTIVE'));

console.log('image render v3 hosted model identity contracts: PASS');
