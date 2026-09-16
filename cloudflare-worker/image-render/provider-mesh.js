import {AI_HORDE_ADAPTER,listProviderAdapters} from './provider-adapter-registry.js';

const FREE_COST='zero';
const REFERENCE_TASKS=new Set(['REFERENCE_GENERATION','IMAGE_EDIT_GLOBAL','IMAGE_EDIT_LOCAL','INPAINT','OUTPAINT','BACKGROUND_REPLACE','OBJECT_REPLACE','MULTI_IMAGE_COMPOSE','CHARACTER_CONSISTENCY','PRODUCT_CONSISTENCY','TARGETED_REPAIR']);

const asStringArray=value=>Array.isArray(value)?value.map(item=>String(item).trim()).filter(Boolean):[];
const positiveInteger=value=>Number.isInteger(Number(value))&&Number(value)>0;

export function validateProviderModelRegistration(registration={}){
  const errors=[];
  if(!String(registration.providerId||'').trim())errors.push('provider_id_required');
  if(!String(registration.modelId||'').trim())errors.push('model_id_required');
  if(registration.monetaryCost!==FREE_COST)errors.push('non_zero_or_unknown_cost');
  if(registration.paidFallback!==false)errors.push('paid_fallback_forbidden');
  if(registration.autoPurchase!==false)errors.push('auto_purchase_forbidden');
  if(asStringArray(registration.supportedDataClasses).length===0)errors.push('supported_data_classes_required');
  if(asStringArray(registration.supportedTasks).length===0)errors.push('supported_tasks_required');
  if(typeof registration.referenceSafe!=='boolean')errors.push('reference_safe_required');
  if(!registration.maxResolution||!positiveInteger(registration.maxResolution.width)||!positiveInteger(registration.maxResolution.height))errors.push('max_resolution_required');
  return {ok:errors.length===0,errors};
}

function needsReferenceSafe(intent={}){
  return (Array.isArray(intent.referenceAssets)&&intent.referenceAssets.length>0)||REFERENCE_TASKS.has(String(intent.taskType||''));
}

export function filterEligibleProviderModels(intent={},registrations=[]){
  const taskType=String(intent.taskType||'');
  const privacyClass=String(intent.privacyClass||'');
  const targetWidth=Number(intent.target?.width||0);
  const targetHeight=Number(intent.target?.height||0);
  const requireReferenceSafe=needsReferenceSafe(intent);
  return registrations.filter(registration=>{
    if(!validateProviderModelRegistration(registration).ok)return false;
    if(!asStringArray(registration.supportedTasks).includes(taskType))return false;
    if(!asStringArray(registration.supportedDataClasses).includes(privacyClass))return false;
    if(requireReferenceSafe&&registration.referenceSafe!==true)return false;
    if(targetWidth>Number(registration.maxResolution.width)||targetHeight>Number(registration.maxResolution.height))return false;
    if(['down','unhealthy','disabled'].includes(String(registration.health||'').toLowerCase()))return false;
    return true;
  }).map(registration=>({...registration}));
}

// Registrations are derived from the adapter registry: the adapters are the single
// provider authority, so a provider cannot be described differently in two places.
function registrationFromAdapter(adapter){
  return {
    providerId:adapter.id,
    providerClass:adapter.type,
    modelId:adapter.supportedModels[0],
    monetaryCost:adapter.monetaryCost,
    paidFallback:adapter.paidFallback,
    autoPurchase:adapter.autoPurchase,
    supportedDataClasses:[...adapter.privacyClasses],
    referenceSafe:adapter.referenceSafe,
    supportedTasks:[...adapter.supportedTasks],
    health:'dynamic',
    maxResolution:{...adapter.maxResolution},
    privacyNotes:adapter.referenceSafe
      ?'reference-safe runtime; may receive reference and source images'
      :'PUBLIC_ONLY; reference/private assets forbidden',
    retentionNotes:adapter.provenance,
  };
}

// Registering an adapter is not the same as having a runtime. A provider only enters the
// mesh when the runtime it needs is actually present, so nothing is offered that cannot run.
function adapterHasRuntime(adapter,env){
  if(adapter.authentication==='worker_ai_binding')return Boolean(env?.AI&&typeof env.AI.run==='function');
  return true;
}

const AI_HORDE_REGISTRATION=Object.freeze(registrationFromAdapter(AI_HORDE_ADAPTER));

export function createImageProviderMesh({extraRegistrations=[],env={}}={}){
  const available=listProviderAdapters().filter(adapter=>adapterHasRuntime(adapter,env));
  const registrations=[...available.map(registrationFromAdapter),...extraRegistrations].map(item=>({...item}));
  const keys=new Set();
  for(const registration of registrations){
    const validation=validateProviderModelRegistration(registration);
    if(!validation.ok)throw new Error(`invalid_provider_model_registration:${registration.providerId||'unknown'}:${validation.errors.join(',')}`);
    const key=`${registration.providerId}::${registration.modelId}`;
    if(keys.has(key))throw new Error(`duplicate_provider_model_registration:${key}`);
    keys.add(key);
  }
  return {
    listRegistrations(){return registrations.map(item=>({...item}));},
    getRegistration(providerId,modelId){
      const match=registrations.find(item=>item.providerId===providerId&&item.modelId===modelId);
      return match?{...match}:null;
    },
    eligible(intent){return filterEligibleProviderModels(intent,registrations);},
  };
}

export const IMAGE_PROVIDER_MESH_DEFAULTS=Object.freeze([AI_HORDE_REGISTRATION]);
