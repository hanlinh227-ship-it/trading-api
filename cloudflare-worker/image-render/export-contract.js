const COMPLETE=new Set(['complete','complete_unverified']);
const FAILED=new Set(['failed_quality','failed_provider']);
const safeHttps=value=>{try{const url=new URL(String(value||''));return url.protocol==='https:'&&Boolean(url.hostname)?url:null;}catch{return null;}};
const latestAttempt=scene=>Array.isArray(scene?.attempts)&&scene.attempts.length?scene.attempts[scene.attempts.length-1]:null;
const extensionFor=url=>{const match=String(url?.pathname||'').match(/\.(webp|png|jpe?g)$/i);return match?match[1].toLowerCase().replace('jpeg','jpg'):'webp';};
const sceneName=id=>String(id||'').replace(/[^A-Za-z0-9_-]+/g,'_')||'scene';
const qaFor=attempt=>({level:attempt?.QA_level??attempt?.qa?.qaLevel??null,result:attempt?.QA_result??attempt?.qa?.result??null,confidence:attempt?.QA_confidence??attempt?.qa?.confidence??null,reasons:Array.isArray(attempt?.QA_reasons)?attempt.QA_reasons:(Array.isArray(attempt?.qa?.reasons)?attempt.qa.reasons:[])});

export function buildRenderReport(state={}){
  const scenes=Array.isArray(state.scenes)?state.scenes:[];
  const passed=scenes.filter(scene=>COMPLETE.has(scene.status));
  const failed=scenes.filter(scene=>FAILED.has(scene.status));
  const modelUsage={};const seeds=[];const attempts=[];const qa=[];const failureReasons={};
  for(const scene of scenes){
    for(const attempt of Array.isArray(scene.attempts)?scene.attempts:[]){
      const model=String(attempt?.model||'').trim();if(model)modelUsage[model]=(modelUsage[model]||0)+1;
      if(attempt?.seed!==undefined&&attempt?.seed!==null)seeds.push({sceneId:String(scene.scene_id),seed:String(attempt.seed)});
      attempts.push({sceneId:String(scene.scene_id),attemptNumber:Number(attempt?.attempt_number||attempts.length+1),provider:attempt?.provider??null,model:model||null,seed:attempt?.seed??null,providerJobId:attempt?.provider_job_id??null,qa:qaFor(attempt)});
    }
    const last=latestAttempt(scene);const q=qaFor(last);qa.push({sceneId:String(scene.scene_id),status:String(scene.status||''),...q});
    const reasons=[...q.reasons];if(last?.provider_error)reasons.push(String(last.provider_error));if(reasons.length)failureReasons[String(scene.scene_id)]=[...new Set(reasons)];
  }
  return {batchId:String(state.batch_id||state.batchId||''),status:String(state.status||state.summary?.status||''),totalScenes:scenes.length,passedScenes:passed.length,failedSceneCount:failed.length,failedScenes:failed.map(scene=>String(scene.scene_id)),modelUsage,seeds,attempts,qa,failureReasons,freeOnly:true,paidFallback:false,monetaryImageProviderCost:0};
}

export function buildExportManifest(state={}){
  const scenes=Array.isArray(state.scenes)?state.scenes:[];const assets=[];
  for(const scene of scenes){
    if(!COMPLETE.has(scene.status))continue;
    const attempt=[...(Array.isArray(scene.attempts)?scene.attempts:[])].reverse().find(row=>safeHttps(row?.generation?.imageUrl));
    const url=safeHttps(attempt?.generation?.imageUrl);if(!url)continue;
    const id=sceneName(scene.scene_id);assets.push({sceneId:String(scene.scene_id),fileName:`Scene_${id}.${extensionFor(url)}`,url:url.toString()});
  }
  return {batchId:String(state.batch_id||state.batchId||''),freeOnly:true,paidFallback:false,assets};
}
