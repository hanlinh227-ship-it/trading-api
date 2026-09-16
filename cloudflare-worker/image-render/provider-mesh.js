const FREE_COST='zero';
const REFERENCE_TASKS=new Set(['REFERENCE_GENERATION','IMAGE_EDIT_GLOBAL','IMAGE_EDIT_LOCAL','INPAINT','OUTPAINT','BACKGROUND_REPLACE','OBJECT_REPLACE','MULTI_IMAGE_COMPOSE','CHARACTER_CONSISTENCY','PRODUCT_CONSISTENCY','TARGETED_REPAIR']);

const asStringArray=value=>Array.isArray(value)?value.map(item=>String(item).trim()).filter(Boolean):[];
const positiveInteger=value=>Number.isInteger(Number(value))&&Number(value)>0;
const nonEmpty=value=>typeof value==='string'&&value.trim().length>0;
const validHttpsUrl=value=>{
  if(!nonEmpty(value))return false;
  try{return new URL(value).protocol==='https:';}catch{return false;}
};

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
  if(!validHttpsUrl(registration.baseUrl))errors.push('base_url_required');
  if(!nonEmpty(registration.healthEndpoint))errors.push('health_endpoint_required');
  if(!nonEmpty(registration.queueBehavior))errors.push('queue_behavior_required');
  if(!positiveInteger(registration.timeoutMs))errors.push('timeout_required');
  if(!registration.retryPolicy||typeof registration.retryPolicy!=='object'||Array.isArray(registration.retryPolicy))errors.push('retry_policy_required');
  if(!nonEmpty(registration.rateLimitBehavior))errors.push('rate_limit_behavior_required');
  if(!nonEmpty(registration.provenance))errors.push('provenance_required');
  if(!nonEmpty(registration.licenseEvidence))errors.push('license_evidence_required');
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

const AI_HORDE_REGISTRATION=Object.freeze({
  providerId:'ai_horde',
  providerClass:'community_nonprofit_volunteer_compute',
  modelId:'sdxl',
  monetaryCost:'zero',
  paidFallback:false,
  autoPurchase:false,
  supportedDataClasses:['PUBLIC'],
  referenceSafe:false,
  supportedTasks:['TEXT_TO_IMAGE','MULTI_SCENE_BATCH'],
  health:'dynamic',
  maxResolution:{width:1536,height:1536},
  baseUrl:'https://aihorde.net/api/v2',
  healthEndpoint:'/status/heartbeat',
  queueBehavior:'provider_managed_volunteer_queue',
  timeoutMs:120000,
  retryPolicy:{maxAttempts:3,backoff:'bounded_exponential'},
  rateLimitBehavior:'provider_managed_kudos_and_queue_capacity',
  provenance:'repo_adapter:cloudflare-worker/image-render/ai-horde.js',
  licenseEvidence:'provider runtime registration; generated model license remains model-specific and is not inferred from provider availability',
  privacyNotes:'PUBLIC_ONLY volunteer infrastructure; reference/private assets forbidden',
  retentionNotes:'provider-controlled volunteer processing; do not send non-public assets',
});

export function createImageProviderMesh({extraRegistrations=[]}={}){
  const registrations=[AI_HORDE_REGISTRATION,...extraRegistrations].map(item=>({...item}));
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
