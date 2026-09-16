const array=value=>Array.isArray(value)?value:[];
const httpsUrl=value=>{
  try{const url=new URL(String(value||''));return url.protocol==='https:'?url.toString():null;}catch{return null;}
};
const last=arrayValue=>array(arrayValue).at(-1)||null;
const safeSceneId=value=>String(value??'').replace(/[^A-Za-z0-9_-]/g,'_')||'unknown';

export function buildRenderReport(state={}){
  const scenes=array(state.scenes);
  const modelUsage={};
  const seeds=[];
  let providerRequests=0;
  const rows=scenes.map(scene=>{
    const attempts=array(scene.attempts);
    for(const attempt of attempts){
      providerRequests+=1;
      const model=String(attempt?.model||attempt?.generation?.model||'').trim();
      if(model)modelUsage[model]=(modelUsage[model]||0)+1;
      if(attempt?.seed!==undefined&&attempt?.seed!==null&&String(attempt.seed).length)seeds.push(String(attempt.seed));
    }
    const attempt=last(attempts)||{};
    const failureReasons=[...array(attempt?.qa_reasons).map(String)];
    if(attempt?.provider_error)failureReasons.push(String(attempt.provider_error));
    return {
      sceneId:String(scene?.scene_id||''),
      status:String(scene?.status||''),
      attemptCount:attempts.length,
      model:String(attempt?.model||attempt?.generation?.model||''),
      seed:attempt?.seed??attempt?.generation?.seed??null,
      imageUrl:httpsUrl(attempt?.generation?.imageUrl),
      qa:{
        level:attempt?.qa_level||attempt?.qa?.level||null,
        result:attempt?.qa_result||attempt?.qa?.result||null,
        confidence:attempt?.qa_confidence??attempt?.qa?.confidence??null,
        reasons:array(attempt?.qa_reasons||attempt?.qa?.reasons).map(String),
      },
      failureReasons:[...new Set(failureReasons)],
    };
  });
  return {
    batchId:state.batch_id||null,
    batchStatus:state.status||null,
    totalScenes:scenes.length,
    passedScenes:rows.filter(row=>row.status==='complete').map(row=>row.sceneId),
    unverifiedScenes:rows.filter(row=>row.status==='complete_unverified').map(row=>row.sceneId),
    failedScenes:rows.filter(row=>row.status==='failed_quality'||row.status==='failed_provider').map(row=>row.sceneId),
    cancelledScenes:rows.filter(row=>row.status==='cancelled').map(row=>row.sceneId),
    providerRequests,
    modelUsage,
    seeds,
    scenes:rows,
    freeOnly:true,
    paidFallback:false,
    autoPurchase:false,
    monetaryImageProviderCost:0,
  };
}

export function buildExportManifest(state={}){
  const report=buildRenderReport(state);
  const assets=report.scenes.flatMap(scene=>scene.imageUrl?[{
    sceneId:scene.sceneId,
    fileName:`Scene_${safeSceneId(scene.sceneId)}.webp`,
    url:scene.imageUrl,
  }]:[]);
  return {
    batchId:report.batchId,
    directoryName:`render_batch_${safeSceneId(report.batchId||'unknown')}`,
    assets,
    reportFileName:'render_report.json',
    manifestFileName:'manifest.json',
    freeOnly:true,
    paidFallback:false,
    autoPurchase:false,
    monetaryImageProviderCost:0,
    storageRequired:false,
    packageMode:'CALLER_STREAM_OR_ZIP',
  };
}
