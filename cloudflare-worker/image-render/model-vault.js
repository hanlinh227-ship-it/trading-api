import vault from './model-vault.json' with {type:'json'};

const ALLOWED_LICENSES=new Set(['Apache-2.0','MIT']);
const ALLOWED_STATUS=new Set(['CANDIDATE','ACTIVE','DEGRADED','DISABLED']);
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
