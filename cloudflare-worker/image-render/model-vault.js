import vault from './model-vault.json' with {type:'json'};

// Licences we may redistribute or self-host under.
export const PERMISSIVE_LICENSES=Object.freeze(new Set(['Apache-2.0','MIT']));
// Licences that permit commercial use of the model and its outputs but are not free
// redistribution licences. A model under one of these may only be reached through a
// hosted provider that already licensed it; we never mirror or ship its weights.
export const HOSTED_INFERENCE_LICENSES=Object.freeze(new Set([
  'CreativeML-Open-RAIL-M',
  'CreativeML-Open-RAIL++-M',
  'Llama-2-Community-License',
  'Llama-3.2-Community-License',
]));
const ALLOWED_LICENSES=new Set([...PERMISSIVE_LICENSES,...HOSTED_INFERENCE_LICENSES]);
// Promotion pipeline: candidate -> benchmark -> compare -> promotion proposal -> gate -> active.
// BENCHMARKED means the benchmark evidence passed but the policy/runtime gate has not.
export const MODEL_VAULT_STATUSES=Object.freeze(['CANDIDATE','BENCHMARKED','ACTIVE','DEGRADED','DISABLED']);
const ALLOWED_STATUS=new Set(MODEL_VAULT_STATUSES);
const SHA40=/^[0-9a-f]{40}$/i;

export function validateModelVaultEntry(entry={}){
  const errors=[];
  if(!String(entry.modelId||'').trim())errors.push('model_id_required');
  if(!String(entry.canonicalRepo||'').includes('/'))errors.push('canonical_repo_required');
  if(!SHA40.test(String(entry.sourceRevision||'')))errors.push('exact_source_revision_required');
  if(!ALLOWED_LICENSES.has(entry.codeLicense))errors.push('code_license_not_approved');
  if(!ALLOWED_LICENSES.has(entry.weightsLicense))errors.push('weights_license_not_approved');
  if(entry.commercialUseEligible!==true)errors.push('commercial_use_must_be_explicitly_allowed');
  if(typeof entry.redistributionEligible!=='boolean')errors.push('redistribution_eligibility_required');
  // Only a permissive licence may claim redistribution eligibility.
  if(entry.redistributionEligible===true&&!(PERMISSIVE_LICENSES.has(entry.codeLicense)&&PERMISSIVE_LICENSES.has(entry.weightsLicense)))errors.push('redistribution_requires_permissive_license');
  if(typeof entry.runtimeConfigured!=='boolean')errors.push('runtime_configured_required');
  if(!ALLOWED_STATUS.has(entry.approvalStatus))errors.push('approval_status_invalid');
  if(!Array.isArray(entry.supportedTasks)||entry.supportedTasks.length===0)errors.push('supported_tasks_required');
  if(entry.monetaryCost!=='zero')errors.push('free_only_required');
  return {ok:errors.length===0,errors};
}

export function loadApprovedModelVault(){
  const entries=Array.isArray(vault.entries)?vault.entries:[];
  for(const entry of entries){
    const result=validateModelVaultEntry(entry);
    if(!result.ok)throw new Error(`invalid_model_vault_entry:${entry.modelId||'unknown'}:${result.errors.join(',')}`);
  }
  return entries.map(entry=>({...entry,supportedTasks:[...entry.supportedTasks]}));
}

export function getModelVaultEntry(modelId){
  return loadApprovedModelVault().find(entry=>entry.modelId===modelId)||null;
}

// Section 16 record schema. The older validateModelVaultEntry above remains the FREE_ONLY
// license gate; this is the full record contract a vault entry must also satisfy.
export const MODEL_VAULT_RECORD_FIELDS=Object.freeze([
  'modelId','family','version','license','codeLicense','weightsLicense','runtimeProviders',
  'supportedTasks','referenceSupport','editSupport','criticSupport','minResolution',
  'maxResolution','qualityBenchmarks','status','lastVerifiedAt','notes',
]);

const isString=value=>typeof value==='string';
const isNonEmptyString=value=>isString(value)&&value.trim().length>0;
const isResolution=value=>Boolean(value)&&typeof value==='object'&&!Array.isArray(value)
  &&Number.isInteger(Number(value.width))&&Number(value.width)>0
  &&Number.isInteger(Number(value.height))&&Number(value.height)>0;
const isPlainObject=value=>Boolean(value)&&typeof value==='object'&&!Array.isArray(value);

export function validateModelVaultRecord(record={}){
  const errors=[];
  for(const field of MODEL_VAULT_RECORD_FIELDS){
    if(record[field]===undefined||record[field]===null)errors.push(`${field}_required`);
  }
  for(const field of ['modelId','family','version','license','codeLicense','weightsLicense','lastVerifiedAt']){
    if(record[field]!==undefined&&!isNonEmptyString(record[field]))errors.push(`${field}_required`);
  }
  if(record.notes!==undefined&&!isString(record.notes))errors.push('notes_required');
  if(record.runtimeProviders!==undefined&&!Array.isArray(record.runtimeProviders))errors.push('runtimeProviders_required');
  if(record.supportedTasks!==undefined&&(!Array.isArray(record.supportedTasks)||record.supportedTasks.length===0))errors.push('supportedTasks_required');
  for(const field of ['referenceSupport','editSupport','criticSupport']){
    if(record[field]!==undefined&&typeof record[field]!=='boolean')errors.push(`${field}_required`);
  }
  if(record.minResolution!==undefined&&!isResolution(record.minResolution))errors.push('minResolution_required');
  if(record.maxResolution!==undefined&&!isResolution(record.maxResolution))errors.push('maxResolution_required');
  if(isResolution(record.minResolution)&&isResolution(record.maxResolution)
    &&(Number(record.minResolution.width)>Number(record.maxResolution.width)||Number(record.minResolution.height)>Number(record.maxResolution.height))){
    errors.push('minResolution_exceeds_maxResolution');
  }
  if(record.qualityBenchmarks!==undefined&&!isPlainObject(record.qualityBenchmarks))errors.push('qualityBenchmarks_required');
  if(record.status!==undefined&&!ALLOWED_STATUS.has(record.status))errors.push('status_invalid');

  // ACTIVE is a runtime claim: it needs a runtime to run on and benchmark evidence for a
  // task the model supports. A model is never ACTIVE just because its record exists.
  if(record.status==='ACTIVE'){
    if(!Array.isArray(record.runtimeProviders)||record.runtimeProviders.length===0)errors.push('active_requires_runtime_provider');
    const benchmarks=isPlainObject(record.qualityBenchmarks)?record.qualityBenchmarks:{};
    const supported=Array.isArray(record.supportedTasks)?record.supportedTasks:[];
    if(!supported.some(task=>isPlainObject(benchmarks[task])))errors.push('active_requires_benchmark_evidence');
  }
  return {ok:errors.length===0,errors:[...new Set(errors)]};
}
