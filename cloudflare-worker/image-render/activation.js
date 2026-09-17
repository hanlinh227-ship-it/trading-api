import {validateProviderAdapter} from './provider-adapter.js';
import {benchmarkEvidenceMeetsPromotion,evaluatePromotionGate} from './benchmark-registry.js';

export const ACTIVATION_STAGES=Object.freeze([
  'CANDIDATE','RUNTIME_DISCOVERED','HEALTH_VERIFIED','LICENSE_VERIFIED','PRIVACY_VERIFIED','BENCHMARKED','ACTIVE',
]);

const passed=record=>Boolean(record)&&record.ok===true;
const failed=record=>Boolean(record)&&record.ok===false;
const stamp=(stage,record)=>({stage,at:record?.at??null,source:record?.source??record?.detail??null});

const GATES=[
  {stage:'RUNTIME_DISCOVERED',key:'runtimeDiscovered',blocker:'runtime_not_discovered',disabling:false},
  {stage:'HEALTH_VERIFIED',key:'health',blocker:'runtime_health_not_verified',disabling:false},
  {stage:'LICENSE_VERIFIED',key:'license',blocker:'license_not_verified',disabling:true},
  {stage:'PRIVACY_VERIFIED',key:'privacy',blocker:'privacy_not_verified',disabling:true},
  {stage:'BENCHMARKED',key:'benchmark',blocker:'benchmark_not_passed',disabling:false},
];

export function evaluateActivation({model={},adapter={},taskType,evidence={}}={}){
  const blockers=[];
  const evidenceTrail=[];

  const adapterCheck=validateProviderAdapter(adapter);
  if(!adapterCheck.ok){
    return {stage:'CANDIDATE',status:'DISABLED',taskType:taskType??null,blockers:adapterCheck.errors.map(e=>`adapter:${e}`),evidenceTrail};
  }

  if(taskType&&Array.isArray(model.supportedTasks)&&!model.supportedTasks.includes(taskType))blockers.push('task_not_supported_by_model');
  if(taskType&&Array.isArray(adapter.supportedTasks)&&!adapter.supportedTasks.includes(taskType))blockers.push('task_not_supported_by_provider');
  if(model.monetaryCost!==undefined&&model.monetaryCost!=='zero')blockers.push('model_cost_not_zero');

  let stage='CANDIDATE';
  for(const gate of GATES){
    const record=evidence[gate.key];
    let gatePassed=passed(record);
    if(gate.key==='benchmark')gatePassed=benchmarkEvidenceMeetsPromotion(record,taskType);
    if(gatePassed){
      stage=gate.stage;
      evidenceTrail.push(stamp(gate.stage,record));
      continue;
    }
    if(gate.disabling&&failed(record)){
      return {stage,status:'DISABLED',taskType:taskType??null,blockers:[...blockers,`${gate.key}_failed`],evidenceTrail};
    }
    blockers.push(gate.blocker);
    break;
  }

  if(blockers.length)return {stage,status:stage==='CANDIDATE'?'CANDIDATE':stage,taskType:taskType??null,blockers:[...new Set(blockers)],evidenceTrail};

  if(evidence.regression?.degraded===true){
    return {stage:'BENCHMARKED',status:'DEGRADED',taskType:taskType??null,blockers:['benchmark_regression'],evidenceTrail};
  }

  const registration={
    providerId:adapter.id,
    modelId:model.modelId,
    monetaryCost:adapter.monetaryCost,
    paidFallback:adapter.paidFallback,
    autoPurchase:adapter.autoPurchase,
    supportedDataClasses:[...adapter.privacyClasses],
    supportedTasks:[...adapter.supportedTasks],
    referenceSafe:adapter.referenceSafe,
    maxResolution:{...adapter.maxResolution},
    baseUrl:adapter.baseUrl,
    healthEndpoint:adapter.healthEndpoint,
    queueBehavior:adapter.queueBehavior,
    timeoutMs:Number(adapter.timeout?.submitMs||0),
    retryPolicy:{...adapter.retryPolicy},
    rateLimitBehavior:adapter.rateLimitBehavior,
    provenance:adapter.provenance,
    licenseEvidence:adapter.licenseEvidence,
  };
  const gate=evaluatePromotionGate({
    vaultEntry:model,
    providerRegistration:registration,
    runtimeConfigured:model.runtimeConfigured===true||undefined,
    runtimeHealthy:evidence.health?.ok===true,
    taskType,
  });
  if(!gate.ok)return {stage:'BENCHMARKED',status:'BENCHMARKED',taskType:taskType??null,blockers:gate.blockers,evidenceTrail,gate};
  return {stage:'ACTIVE',status:'ACTIVE',taskType:taskType??null,blockers:[],evidenceTrail,gate};
}

export function advanceActivation(model={},evaluation={}){
  return {
    ...structuredClone(model),
    status:evaluation.status??'CANDIDATE',
    activation:{
      stage:evaluation.stage??'CANDIDATE',
      taskType:evaluation.taskType??null,
      blockers:[...(evaluation.blockers||[])],
      evidenceTrail:[...(evaluation.evidenceTrail||[])],
    },
  };
}
