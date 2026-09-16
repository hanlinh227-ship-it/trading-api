import assert from 'node:assert/strict';
import {MODEL_VAULT_RECORD_FIELDS,loadApprovedModelVault,validateModelVaultRecord} from './image-render/model-vault.js';

// Section 16: a vault record must state its own facts; model-name inference is not evidence.
assert.deepEqual([...MODEL_VAULT_RECORD_FIELDS].sort(),[
  'codeLicense','criticSupport','editSupport','family','license','maxResolution','minResolution',
  'modelId','qualityBenchmarks','referenceSupport','runtimeProviders','status','supportedTasks',
  'lastVerifiedAt','version','weightsLicense','notes',
].sort());

const record={
  modelId:'demo',family:'demo-family',version:'1.0',
  license:'Apache-2.0',codeLicense:'Apache-2.0',weightsLicense:'Apache-2.0',
  runtimeProviders:[],supportedTasks:['TEXT_TO_IMAGE'],
  referenceSupport:false,editSupport:false,criticSupport:false,
  minResolution:{width:256,height:256},maxResolution:{width:1536,height:1536},
  qualityBenchmarks:{},status:'CANDIDATE',lastVerifiedAt:'2026-09-16',notes:'',
};
assert.equal(validateModelVaultRecord(record).ok,true,JSON.stringify(validateModelVaultRecord(record).errors));

// Every field is required.
for(const field of MODEL_VAULT_RECORD_FIELDS){
  const {[field]:_dropped,...partial}=record;
  assert.equal(validateModelVaultRecord(partial).ok,false,`missing ${field} must be rejected`);
}

// A model with no runtime provider can never be ACTIVE — that is the whole point.
assert.equal(validateModelVaultRecord({...record,status:'ACTIVE'}).ok,false);
assert.ok(validateModelVaultRecord({...record,status:'ACTIVE'}).errors.includes('active_requires_runtime_provider'));
assert.equal(validateModelVaultRecord({...record,status:'ACTIVE',runtimeProviders:['ai_horde'],qualityBenchmarks:{TEXT_TO_IMAGE:{score:91,samples:12,at:'2026-09-16'}}}).ok,true);

// ACTIVE also requires benchmark evidence for a supported task.
assert.ok(validateModelVaultRecord({...record,status:'ACTIVE',runtimeProviders:['ai_horde']}).errors.includes('active_requires_benchmark_evidence'));

// Status must be a known vault status.
assert.equal(validateModelVaultRecord({...record,status:'PROMOTED'}).ok,false);
// Resolution ordering must make sense.
assert.equal(validateModelVaultRecord({...record,minResolution:{width:4096,height:4096}}).ok,false);

// The shipped vault still validates and stays honest.
const vault=loadApprovedModelVault();
assert.ok(vault.length>=4);
for(const entry of vault){
  assert.equal(validateModelVaultRecord(entry).ok,true,`${entry.modelId}: ${validateModelVaultRecord(entry).errors}`);
  if(entry.status==='ACTIVE')assert.ok(entry.runtimeProviders.length>0,`${entry.modelId} ACTIVE without a runtime provider`);
}

console.log('image render v3 model vault record contracts: PASS');
