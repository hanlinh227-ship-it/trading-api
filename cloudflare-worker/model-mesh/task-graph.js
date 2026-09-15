export function buildTaskGraph({text='',route,workers=[]}={}){
  const inputHash=String(text).length+':'+String(route?.primarySkill||'');
  return {inputHash,nodes:workers.map((worker,index)=>({id:`worker-${index+1}`,family:worker.model_family,provider:worker.provider_id,dependsOn:[]})),independent:true};
}
