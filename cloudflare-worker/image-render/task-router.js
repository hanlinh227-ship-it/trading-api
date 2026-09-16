import {requiresReferenceSafeRuntime} from './provider-mesh.js';

const isHealthy=candidate=>!['down','unhealthy','disabled'].includes(String(candidate.health||'').toLowerCase());
const numberOr=(value,fallback=0)=>Number.isFinite(Number(value))?Number(value):fallback;

function taskHistory(history,candidate,taskType){
  const record=history?.[`${candidate.providerId}::${candidate.modelId}`]||{};
  const taskRecord=record.byTask?.[taskType]||{};
  return {
    qualityScore:numberOr(taskRecord.qualityScore,candidate.taskScores?.[taskType]??50),
    criticPassRate:numberOr(taskRecord.criticPassRate,candidate.criticPassRate??0.5),
    retryCount:numberOr(record.retryCount,0),
  };
}

export function rankImageModels({intent={},candidates=[],history={}}={}){
  const taskType=String(intent.taskType||'');
  const needsReference=requiresReferenceSafeRuntime(intent);
  const width=numberOr(intent.target?.width,0);
  const height=numberOr(intent.target?.height,0);

  return candidates
    .filter(candidate=>Array.isArray(candidate.supportedTasks)&&candidate.supportedTasks.includes(taskType))
    .filter(isHealthy)
    .filter(candidate=>!needsReference||candidate.referenceSafe===true)
    .filter(candidate=>width<=numberOr(candidate.maxResolution?.width,0)&&height<=numberOr(candidate.maxResolution?.height,0))
    .map(candidate=>{
      const historical=taskHistory(history,candidate,taskType);
      let score=historical.qualityScore*0.55+historical.criticPassRate*20;
      score-=Math.min(15,numberOr(candidate.queueEstimate,0)*0.15);
      score-=Math.min(10,numberOr(candidate.latencyMs,0)/2000);
      score-=Math.min(15,historical.retryCount*4);
      if(taskType==='TEXT_RENDER_EDIT')score+=numberOr(candidate.textRenderScore,0)*0.2;
      return {...candidate,routingScore:Number(score.toFixed(4))};
    })
    .sort((a,b)=>b.routingScore-a.routingScore||String(a.providerId).localeCompare(String(b.providerId))||String(a.modelId).localeCompare(String(b.modelId)));
}
