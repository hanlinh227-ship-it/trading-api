const clamp=(value,min,max)=>Math.min(max,Math.max(min,Number(value)||0));

export function rankImageModels({models=[],preferredModels=[],history={},limit=4}={}){
  const preferred=new Set((Array.isArray(preferredModels)?preferredModels:[]).map(String));
  const ranked=(Array.isArray(models)?models:[]).map(model=>{
    const name=String(model?.name||'');
    const stats=history?.[name]||{};
    let score=0;
    const reasons=[];
    if(preferred.has(name)){
      score+=50;
      reasons.push('preferred_model');
    }
    const workerCount=clamp(model?.workerCount,0,8);
    const performance=clamp(model?.performance,0,200);
    const eta=clamp(model?.eta,0,300);
    const queued=clamp(model?.queued,0,50);
    score+=workerCount*4;
    score+=performance/10;
    score-=eta/10;
    score-=queued;
    const successes=Math.min(5,Math.max(0,Number(stats?.successes)||0));
    const failures=Math.min(5,Math.max(0,Number(stats?.failures)||0));
    if(successes){score+=successes*3;reasons.push('batch_success_history');}
    if(failures){score-=failures*12;reasons.push('batch_failure_history');}
    if(workerCount<=0){score-=1000;reasons.push('no_active_workers');}
    return {...model,name,score,reasons};
  });
  return ranked.sort((a,b)=>b.score-a.score||a.name.localeCompare(b.name)).slice(0,Math.max(1,Math.min(8,Number(limit)||4)));
}
