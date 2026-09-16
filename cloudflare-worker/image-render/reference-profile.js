const list=value=>Array.isArray(value)?[...new Set(value.map(item=>String(item).trim()).filter(Boolean))]:[];

export function createReferenceProfile({references=[],constraints={}}={}){
  if(!Array.isArray(references)||references.length===0)throw new Error('reference_assets_required');
  return {
    profileVersion:'reference_profile_v3',
    referenceCount:references.length,
    referenceIds:references.map(ref=>String(ref?.id||'')).filter(Boolean),
    characterClass:String(constraints.characterClass||'').trim()||null,
    headShape:String(constraints.headShape||'').trim()||null,
    bodyProportions:String(constraints.bodyProportions||'').trim()||null,
    palette:list(constraints.palette),
    eyeStyle:String(constraints.eyeStyle||'').trim()||null,
    clothing:list(constraints.clothing),
    accessories:list(constraints.accessories),
    recurringProps:list(constraints.recurringProps),
    silhouette:String(constraints.silhouette||'').trim()||null,
    forbiddenDeviations:list(constraints.forbiddenDeviations),
    sceneInvariantFeatures:list(constraints.sceneInvariantFeatures),
    biometricIdentityClaim:false,
  };
}

export function validateReferenceRoute({intent={},providerModel}={}){
  if(!providerModel)return {ok:false,state:'WAITING_FOR_SAFE_FREE_RUNTIME',reason:'reference_safe_runtime_unavailable'};
  const errors=[];
  if(providerModel.monetaryCost!=='zero')errors.push('free_only_required');
  if(providerModel.paidFallback!==false)errors.push('paid_fallback_forbidden');
  if(providerModel.autoPurchase!==false)errors.push('auto_purchase_forbidden');
  if(providerModel.referenceSafe!==true)errors.push('reference_safe_required');
  if(!Array.isArray(providerModel.supportedDataClasses)||!providerModel.supportedDataClasses.includes(intent.privacyClass))errors.push('privacy_class_not_supported');
  if(!Array.isArray(providerModel.supportedTasks)||!providerModel.supportedTasks.includes(intent.taskType))errors.push('task_not_supported');
  const width=Number(intent.target?.width||0),height=Number(intent.target?.height||0);
  if(width>Number(providerModel.maxResolution?.width||0)||height>Number(providerModel.maxResolution?.height||0))errors.push('resolution_not_supported');
  if(providerModel.providerId==='ai_horde')errors.push('volunteer_reference_route_forbidden');
  return errors.length?{ok:false,state:'WAITING_FOR_SAFE_FREE_RUNTIME',reason:errors[0],errors}:{ok:true,state:'ELIGIBLE',providerModel};
}
