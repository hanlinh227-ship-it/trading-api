import {MODEL_MESH_LIMITS,eligibleModel} from './contracts.js';

function score(model,domain='core'){
  const quality=Number(model?.quality_scores?.[domain]??model?.quality_scores?.core??0);
  const reasoning=Number(model?.capabilities?.text_reasoning?.score??0);
  return quality*0.7+reasoning*0.3;
}

export function selectModelWorkers({profile='STANDARD',domain='core',dataClass='PUBLIC',models=[]}={}){
  const limit=MODEL_MESH_LIMITS[String(profile).toUpperCase()]??0;
  if(limit<=0)return [];
  const ranked=models.filter(m=>eligibleModel(m,dataClass)).sort((a,b)=>score(b,domain)-score(a,domain)||String(a.model_family).localeCompare(String(b.model_family)));
  const out=[];const seen=new Set();
  for(const model of ranked){const family=String(model.model_family||model.model_id||'');if(seen.has(family))continue;seen.add(family);out.push({...model,worker_role:out.length?'critic':'maker'});if(out.length>=limit)break;}
  return out;
}
