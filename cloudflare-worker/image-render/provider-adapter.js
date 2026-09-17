// Provider adapter contract. A provider that cannot state all of these facts is inactive:
// an unknown cost, an unknown privacy behaviour or an unknown retry/rate-limit behaviour is
// treated as a blocker, never as a default.
export const PROVIDER_ADAPTER_REQUIRED_FIELDS=Object.freeze([
  'id','type','baseUrl','costMode','monetaryCost','paidFallback','autoPurchase','privacyClasses',
  'referenceSafe','supportedTasks','supportedModels','maxResolution','healthEndpoint',
  'queueBehavior','timeout','retryPolicy','rateLimitBehavior','provenance','licenseEvidence',
]);

const KNOWN_PRIVACY_CLASSES=new Set(['PUBLIC','INTERNAL','CONFIDENTIAL']);
// Tasks that hand the provider a reference or source image.
const REFERENCE_TASKS=new Set(['REFERENCE_GENERATION','CHARACTER_CONSISTENCY','PRODUCT_CONSISTENCY','IMAGE_EDIT_GLOBAL','IMAGE_EDIT_LOCAL','INPAINT','OUTPAINT','BACKGROUND_REPLACE','OBJECT_REPLACE','TEXT_RENDER_EDIT','MULTI_IMAGE_COMPOSE','TARGETED_REPAIR']);

const isNonEmptyString=value=>typeof value==='string'&&value.trim().length>0;
const isStringList=value=>Array.isArray(value)&&value.length>0&&value.every(isNonEmptyString);
const isPositiveInt=value=>Number.isInteger(Number(value))&&Number(value)>0;
const isPlainObject=value=>Boolean(value)&&typeof value==='object'&&!Array.isArray(value);

export function validateProviderAdapter(adapter={}){
  const errors=[];
  for(const field of PROVIDER_ADAPTER_REQUIRED_FIELDS){
    if(adapter[field]===undefined||adapter[field]===null)errors.push(`${field}_required`);
  }

  for(const field of ['id','type','baseUrl','healthEndpoint','queueBehavior','rateLimitBehavior','provenance','licenseEvidence']){
    if(adapter[field]!==undefined&&!isNonEmptyString(adapter[field]))errors.push(`${field}_required`);
  }
  if(isNonEmptyString(adapter.baseUrl)&&!/^https:\/\//i.test(adapter.baseUrl))errors.push('baseUrl_must_be_https');

  // FREE_ONLY hard gate.
  if(adapter.costMode!==undefined&&adapter.costMode!=='FREE_ONLY')errors.push('costMode_must_be_free_only');
  if(adapter.monetaryCost!==undefined&&adapter.monetaryCost!=='zero')errors.push('monetaryCost_must_be_zero');
  if(adapter.paidFallback!==undefined&&adapter.paidFallback!==false)errors.push('paidFallback_must_be_false');
  if(adapter.autoPurchase!==undefined&&adapter.autoPurchase!==false)errors.push('autoPurchase_must_be_false');

  if(adapter.privacyClasses!==undefined){
    if(!isStringList(adapter.privacyClasses))errors.push('privacyClasses_required');
    else if(adapter.privacyClasses.some(cls=>!KNOWN_PRIVACY_CLASSES.has(cls)))errors.push('privacyClasses_unknown_class');
  }
  if(adapter.referenceSafe!==undefined&&typeof adapter.referenceSafe!=='boolean')errors.push('referenceSafe_required');

  if(adapter.supportedTasks!==undefined&&!isStringList(adapter.supportedTasks))errors.push('supportedTasks_required');
  if(adapter.supportedModels!==undefined&&!isStringList(adapter.supportedModels))errors.push('supportedModels_required');

  if(adapter.maxResolution!==undefined&&(!isPlainObject(adapter.maxResolution)||!isPositiveInt(adapter.maxResolution.width)||!isPositiveInt(adapter.maxResolution.height)))errors.push('maxResolution_required');
  // Every timeout must be a non-negative integer and submitMs must be set. A synchronous
  // provider legitimately has no poll or cancel step, so 0 is allowed for those.
  if(adapter.timeout!==undefined&&(
    !isPlainObject(adapter.timeout)
    ||!isPositiveInt(adapter.timeout.submitMs)
    ||!Object.values(adapter.timeout).every(value=>Number.isInteger(Number(value))&&Number(value)>=0)
  ))errors.push('timeout_required');
  if(adapter.retryPolicy!==undefined&&(!isPlainObject(adapter.retryPolicy)||!isPositiveInt(adapter.retryPolicy.maxAttempts)))errors.push('retryPolicy_required');

  // A provider that is not reference-safe must never be handed non-public data or a task
  // that carries a reference/source image.
  if(adapter.referenceSafe===false){
    if(Array.isArray(adapter.privacyClasses)&&adapter.privacyClasses.some(cls=>cls!=='PUBLIC'))errors.push('referenceSafe_false_requires_public_only_privacyClasses');
    if(Array.isArray(adapter.supportedTasks)&&adapter.supportedTasks.some(task=>REFERENCE_TASKS.has(task)))errors.push('referenceSafe_false_cannot_support_reference_tasks');
  }

  return {ok:errors.length===0,errors:[...new Set(errors)]};
}

export function describeProviderAdapter(adapter={}){
  const {ok,errors}=validateProviderAdapter(adapter);
  return {
    id:isNonEmptyString(adapter.id)?adapter.id:null,
    type:isNonEmptyString(adapter.type)?adapter.type:null,
    active:ok,
    blockers:errors,
    costMode:adapter.costMode??null,
    monetaryCost:adapter.monetaryCost??null,
    paidFallback:adapter.paidFallback??null,
    autoPurchase:adapter.autoPurchase??null,
    referenceSafe:adapter.referenceSafe===true,
    privacyClasses:Array.isArray(adapter.privacyClasses)?[...adapter.privacyClasses]:[],
    supportedTasks:Array.isArray(adapter.supportedTasks)?[...adapter.supportedTasks]:[],
    supportedModels:Array.isArray(adapter.supportedModels)?[...adapter.supportedModels]:[],
  };
}
