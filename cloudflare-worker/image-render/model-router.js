const clamp=(value,min,max)=>Math.min(max,Math.max(min,Number(value)||0));
const finite=value=>Number.isFinite(Number(value))?Number(value):0;

export function rankImageModels({models=[],preferredModels=[],history={},limit=4}={}){
  const preferred=new Set((Array.isArray(preferredModels)?preferredModels:[]).map(value=>String(value)));
  const safeLimit=Math.max(1,Math.min(8,Math.round(finite(limit)||4)));
  const rows=(Array.isArray(models)?models:[]).filter(model=>model&&String(model.name||'').trim()).map(model=>{
    const name=String(model.name).trim();
    const evidence=history&&typeof history==='object'&&history[name]&&typeof history[name]==='object'?history[name]:{};
    const workerCount=clamp(model.workerCount,0,8);
    const performance=clamp(model.performance,0,200);
    const eta=clamp(model.eta,0,300);
    const queued=clamp(model.queued,0,50);
    const successes=clamp(evidence.successes,0,5);
    const failures=clamp(evidence.failures,0,5);
    let score=0;const reasons=[];

    if(preferred.has(name)){score+=50;reasons.push('preferred_model');}
    if(workerCount>0){score+=workerCount*4;reasons.push('active_workers');}
    else{score-=1000;reasons.push('no_active_workers');}
    if(performance>0){score+=performance/10;reasons.push('provider_performance');}
    if(eta>0){score-=eta/10;reasons.push('queue_eta_penalty');}
    if(queued>0){score-=queued;reasons.push('queued_work_penalty');}
    if(successes>0){score+=successes*3;reasons.push('batch_success_history');}
    if(failures>0){score-=failures*12;reasons.push('batch_failure_penalty');}

    return {...model,name,score:Number(score.toFixed(4)),reasons};
  });
  rows.sort((left,right)=>right.score-left.score||left.name.localeCompare(right.name));
  return rows.slice(0,safeLimit);
}
