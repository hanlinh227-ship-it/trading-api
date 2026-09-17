import {validateModelVaultEntry} from './model-vault.js';
import {requiresReferenceSafeRuntime,validateProviderModelRegistration} from './provider-mesh.js';

const clone=value=>structuredClone(value);
const taskRecord=(state,modelKey,taskType)=>state?.models?.[modelKey]?.tasks?.[taskType]||{results:[]};

export const DEFAULT_BENCHMARK_PROMOTION=Object.freeze({
  minSamples:10,
  minAverage:85,
  minVerifiedRate:0.8,
});

export function recordBenchmarkResult(state={models:{}},{modelKey,taskType,score,verified}={}){
  const next=clone(state||{models:{}});next.models||={};
  next.models[modelKey]||={tasks:{}};next.models[modelKey].tasks||={};
  next.models[modelKey].tasks[taskType]||={results:[]};
  next.models[modelKey].tasks[taskType].results.push({score:Math.max(0,Math.min(100,Number(score)||0)),verified:verified===true});
  return next;
}

function stats(results=[]){
  if(!results.length)return {samples:0,average:0,verifiedRate:0};
  return {samples:results.length,average:results.reduce((sum,item)=>sum+Number(item.score||0),0)/results.length,verifiedRate:results.filter(item=>item.verified===true).length/results.length};
}

export function benchmarkEvidenceMeetsPromotion(record={},taskType){
  if(record?.ok!==true)return false;
  if(taskType&&record?.taskType!==taskType)return false;
  const samples=Number(record?.samples||0);
  const average=Number(record?.average||0);
  const verifiedRate=Number(record?.verifiedRate||0);
  return samples>=DEFAULT_BENCHMARK_PROMOTION.minSamples
    &&average>=DEFAULT_BENCHMARK_PROMOTION.minAverage
    &&verifiedRate>=DEFAULT_BENCHMARK_PROMOTION.minVerifiedRate;
}

export function evaluatePromotionGate({vaultEntry,runtimeConfigured,runtimeHealthy,providerRegistration,taskType}={}){
  const blockers=[];
  if(!vaultEntry)blockers.push('model_vault_entry_required');
  else{
    const validation=validateModelVaultEntry(vaultEntry);
    if(!validation.ok)blockers.push(...validation.errors);
    if(vaultEntry.approvalStatus==='DISABLED')blockers.push('model_disabled');
    if(taskType&&!(Array.isArray(vaultEntry.supportedTasks)&&vaultEntry.supportedTasks.includes(taskType)))blockers.push('task_not_supported_by_model');
    if(vaultEntry.runtimeConfigured!==true&&runtimeConfigured===undefined)blockers.push('runtime_not_configured');
  }
  if(runtimeConfigured!==undefined&&runtimeConfigured!==true)blockers.push('runtime_not_configured');
  if(runtimeHealthy!==true)blockers.push('runtime_not_verified_healthy');
  if(!providerRegistration)blockers.push('provider_registration_required');
  else{
    const providerValidation=validateProviderModelRegistration(providerRegistration);
    if(!providerValidation.ok)blockers.push(...providerValidation.errors);
    if(vaultEntry&&String(providerRegistration.modelId||'')!==String(vaultEntry.modelId||''))blockers.push('provider_model_mismatch');
    if(taskType&&!(Array.isArray(providerRegistration.supportedTasks)&&providerRegistration.supportedTasks.includes(taskType)))blockers.push('task_not_supported_by_provider');
    if(requiresReferenceSafeRuntime({taskType})&&providerRegistration.referenceSafe!==true)blockers.push('reference_safe_runtime_required');
  }
  return {ok:blockers.length===0,blockers:[...new Set(blockers)],reason:blockers.length?blockers[0]:'promotion_gate_passed'};
}

export function evaluateModelPromotion(state,{modelKey,taskType,minSamples=DEFAULT_BENCHMARK_PROMOTION.minSamples,minAverage=DEFAULT_BENCHMARK_PROMOTION.minAverage,minVerifiedRate=DEFAULT_BENCHMARK_PROMOTION.minVerifiedRate,gate}={}){
  const current=stats(taskRecord(state,modelKey,taskType).results);
  if(current.samples<minSamples)return {status:'CANDIDATE',reason:'insufficient_benchmark_evidence',stats:current};
  if(!(current.average>=minAverage&&current.verifiedRate>=minVerifiedRate))return {status:'CANDIDATE',reason:'benchmark_threshold_not_met',stats:current};
  const gateResult=evaluatePromotionGate({...(gate||{}),taskType:gate?.taskType??taskType});
  if(!gateResult.ok)return {status:'BENCHMARKED',reason:gateResult.reason,stats:current,gate:gateResult};
  return {status:'ACTIVE',reason:'benchmark_and_policy_gate_passed',stats:current,gate:gateResult};
}

export function proposeModelPromotion(state,{currentStatus='CANDIDATE',...options}={}){
  const evaluation=evaluateModelPromotion(state,options);
  return {
    modelKey:options.modelKey,
    taskType:options.taskType,
    currentStatus,
    proposedStatus:evaluation.status,
    reason:evaluation.reason,
    evidence:evaluation.stats,
    gate:evaluation.gate||null,
    applied:false,
    requiresApproval:evaluation.status!==currentStatus,
  };
}

export function evaluateModelRegression(state,{modelKey,taskType,window=10,minAverage=70,minVerifiedRate=0.6}={}){
  const all=taskRecord(state,modelKey,taskType).results;
  const current=stats(all.slice(-Math.max(1,Number(window)||10)));
  if(!current.samples)return {status:'CANDIDATE',reason:'insufficient_benchmark_evidence',stats:current};
  if(current.average<minAverage||current.verifiedRate<minVerifiedRate)return {status:'DEGRADED',reason:'benchmark_regression',stats:current};
  return {status:'ACTIVE',reason:'benchmark_stable',stats:current};
}
