const COMPLETE_STATES=new Set(['complete','complete_unverified']);
const FAILED_STATES=new Set(['failed_quality','failed_provider','cancelled']);
const clone=value=>structuredClone(value);
const latestAttempt=scene=>Array.isArray(scene?.attempts)&&scene.attempts.length?scene.attempts[scene.attempts.length-1]:null;

function validHttpsUrl(value){
  try{const url=new URL(String(value||''));return url.protocol==='https:'?url:null;}catch{return null;}
}

function extensionFor(url){
  const match=String(url?.pathname||'').match(/\.([a-zA-Z0-9]{2,5})$/);
  const ext=String(match?.[1]||'webp').toLowerCase();
  return ['webp','png','jpg','jpeg'].includes(ext)?ext:'webp';
}

function safeSceneId(value){
  const raw=String(value||'scene').trim()||'scene';
  return raw.replace(/[^a-zA-Z0-9_-]+/g,'_');
}

function attemptQa(attempt){
  if(attempt?.qa&&typeof attempt.qa==='object')return clone(attempt.qa);
  return {
    qaLevel:attempt?.qa_level??null,
    result:attempt?.qa_result??null,
    reasons:Array.isArray(attempt?.qa_reasons)?clone(attempt.qa_reasons):[],
    confidence:attempt?.qa_confidence??null,
  };
}

export function buildRenderReport(state={}){
  const scenes=Array.isArray(state?.scenes)?state.scenes:[];
  const modelUsage={};
  const seeds=[];
  const sceneReports=scenes.map(scene=>{
    const attempts=(scene.attempts||[]).map((attempt,index)=>{
      const model=String(attempt?.model||'').trim();
      if(model)modelUsage[model]=(modelUsage[model]||0)+1;
      if(attempt?.seed!==undefined&&attempt?.seed!==null)seeds.push(String(attempt.seed));
      const qa=attemptQa(attempt);
      return {
        attempt:Number(attempt?.attempt||index+1),
        provider:attempt?.provider||null,
        providerJobId:attempt?.provider_job_id||null,
        model:model||null,
        seed:attempt?.seed??null,
        submittedAt:attempt?.submitted_at||null,
        completedAt:attempt?.completed_at||null,
        generationState:attempt?.generation_state||attempt?.generation?.state||null,
        imageUrl:validHttpsUrl(attempt?.generation?.imageUrl)?.toString()||null,
        qa,
      };
    });
    const reasons=[];
    for(const attempt of attempts){for(const reason of attempt?.qa?.reasons||[])if(reason&&!reasons.includes(reason))reasons.push(reason);}
    if(Array.isArray(scene?.quality?.reasons))for(const reason of scene.quality.reasons)if(reason&&!reasons.includes(reason))reasons.push(reason);
    return {sceneId:String(scene.scene_id),status:String(scene.status||'unknown'),attemptCount:attempts.length,attempts,failureReasons:reasons};
  });
  const failedScenes=scenes.filter(scene=>FAILED_STATES.has(scene.status)).map(scene=>String(scene.scene_id));
  const completedScenes=scenes.filter(scene=>COMPLETE_STATES.has(scene.status)).length;
  return {
    version:2,
    batchId:state.batch_id||null,
    status:state.status||null,
    totalScenes:scenes.length,
    completedScenes,
    verifiedScenes:scenes.filter(scene=>scene.status==='complete').length,
    unverifiedScenes:scenes.filter(scene=>scene.status==='complete_unverified').length,
    failedSceneCount:failedScenes.length,
    failedScenes,
    modelUsage,
    seeds:[...new Set(seeds)],
    scenes:sceneReports,
    freeOnly:true,
    paidFallback:false,
    monetaryImageProviderCost:0,
  };
}

export function buildExportManifest(state={}){
  const assets=[];
  for(const scene of Array.isArray(state?.scenes)?state.scenes:[]){
    if(!COMPLETE_STATES.has(scene.status))continue;
    const attempt=latestAttempt(scene);
    const url=validHttpsUrl(attempt?.generation?.imageUrl);
    if(!url)continue;
    const sceneId=String(scene.scene_id);
    assets.push({sceneId,fileName:`Scene_${safeSceneId(sceneId)}.${extensionFor(url)}`,url:url.toString()});
  }
  return {
    version:2,
    batchId:state.batch_id||null,
    format:'zip_handoff_metadata',
    freeOnly:true,
    paidFallback:false,
    monetaryImageProviderCost:0,
    assetCount:assets.length,
    assets,
  };
}
