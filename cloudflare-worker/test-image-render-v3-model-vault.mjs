import assert from 'node:assert/strict';
import {loadApprovedModelVault,validateModelVaultEntry} from './image-render/model-vault.js';

const valid={modelId:'demo',canonicalRepo:'org/repo',sourceRevision:'0123456789abcdef0123456789abcdef01234567',codeLicense:'Apache-2.0',weightsLicense:'Apache-2.0',commercialUseEligible:true,redistributionEligible:true,runtimeConfigured:false,approvalStatus:'CANDIDATE',supportedTasks:['TEXT_TO_IMAGE'],monetaryCost:'zero'};
assert.equal(validateModelVaultEntry(valid).ok,true);
assert.equal(validateModelVaultEntry({...valid,weightsLicense:''}).ok,false);
assert.equal(validateModelVaultEntry({...valid,commercialUseEligible:null}).ok,false);
assert.equal(validateModelVaultEntry({...valid,sourceRevision:''}).ok,false);
assert.equal(validateModelVaultEntry({...valid,monetaryCost:'unknown'}).ok,false);
assert.equal(validateModelVaultEntry({...valid,weightsLicense:'NON_COMMERCIAL'}).ok,false);

const vault=loadApprovedModelVault();
assert.ok(vault.length>=4);
for(const entry of vault){
  assert.equal(validateModelVaultEntry(entry).ok,true,entry.modelId);
  assert.equal(entry.approvalStatus,'CANDIDATE');
  assert.equal(entry.monetaryCost,'zero');
}
// runtimeConfigured is no longer false for every model: the Workers AI models are reached
// through a runtime that exists. The invariant that matters is that a configured runtime
// still does not make a model ACTIVE — health and benchmark evidence do, and those are
// collected in production.
assert.ok(vault.some(entry=>entry.runtimeConfigured===true),'a configured runtime must be representable');
assert.ok(vault.every(entry=>entry.approvalStatus!=='ACTIVE'),'no model is ACTIVE without verified evidence');
for(const entry of vault){
  if(entry.runtimeConfigured===true)assert.ok((entry.runtimeProviders||[]).length>0,`${entry.modelId} claims a runtime with no provider`);
  if((entry.runtimeProviders||[]).length===0)assert.equal(entry.runtimeConfigured,false,entry.modelId);
}
assert.ok(vault.some(entry=>entry.modelId==='flux2-klein-4b'));
assert.ok(!vault.some(entry=>/9b|dev/i.test(entry.modelId)&&entry.canonicalRepo==='black-forest-labs/flux2'));

console.log('image render v3 model vault contracts: PASS');
