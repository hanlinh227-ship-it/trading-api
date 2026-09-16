const clone=value=>structuredClone(value);
const taskRecord=(state,modelKey,taskType)=>state?.models?.[modelKey]?.tasks?.[taskType]||{results:[]};

export function recordBenchmarkResult(state={models:{}},{modelKey,taskType,score,verified}={}){
  const next=clone(state||{models:{}});next.models||={};
  next.models[modelKey]||={tasks:{}};next.models[modelKey].tasks||={};
  next.models[modelKey].tasks[taskType]||={results:[]};
  next.models[modelKey].tasks[taskType].results.push({score:Math.max(0,Math.min(100,Number(score)||0)),verified:verified===true});
  return next;
}

function stats(results=[]){
  if(!results.length)return {samples:0,average:0,verifiedRate:0};
  return {samples:results.length,average:results.reduce((sum,item)=>sum+Number(item.score||0),0)/results.length,verifiedRate:results.filter(item=>item.verified===true).length/results.length};
}

export function evaluateModelPromotion(state,{modelKey,taskType,minSamples=10,minAverage=85,minVerifiedRate=0.8}={}){
  const current=stats(taskRecord(state,modelKey,taskType).results);
  if(current.samples<minSamples)return {status:'CANDIDATE',reason:'insufficient_benchmark_evidence',stats:current};
  if(current.average>=minAverage&&current.verifiedRate>=minVerifiedRate)return {status:'ACTIVE',reason:'benchmark_threshold_passed',stats:current};
  return {status:'CANDIDATE',reason:'benchmark_threshold_not_met',stats:current};
}

export function evaluateModelRegression(state,{modelKey,taskType,window=10,minAverage=70,minVerifiedRate=0.6}={}){
  const all=taskRecord(state,modelKey,taskType).results;
  const current=stats(all.slice(-Math.max(1,Number(window)||10)));
  if(!current.samples)return {status:'CANDIDATE',reason:'insufficient_benchmark_evidence',stats:current};
  if(current.average<minAverage||current.verifiedRate<minVerifiedRate)return {status:'DEGRADED',reason:'benchmark_regression',stats:current};
  return {status:'ACTIVE',reason:'benchmark_stable',stats:current};
}
