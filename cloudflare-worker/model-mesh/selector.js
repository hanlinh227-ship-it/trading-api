import {MODEL_MESH_LIMITS,eligibleModel} from './contracts.js';
import {MODEL_MESH_POLICY} from '../generated/model-mesh-policy.js';

function capabilityFit(model,domain){
  const weights=MODEL_MESH_POLICY.domain_capabilities?.[domain]||MODEL_MESH_POLICY.domain_capabilities?.core||{};
  let weighted=0,total=0;
  for(const [dimension,weight] of Object.entries(weights)){
    total+=weight;
    const capability=model?.capabilities?.[dimension];
    if(capability?.supported===true)weighted+=weight*Number(capability.score??0);
  }
  return total>0?weighted/total:0;
}

function score(model,domain='core'){
  const fitWeight=Number(MODEL_MESH_POLICY.scoring?.capability_fit??0.5);
  const qualityWeight=Number(MODEL_MESH_POLICY.scoring?.measured_quality??0.25);
  const measured=Number(model?.quality_scores?.[domain]??model?.quality_scores?.core??0);
  return capabilityFit(model,domain)*fitWeight+measured*qualityWeight;
}

function passesEvidenceHardGates(model,dataClass,{contextTokens=0,hardCapabilities=[]}={}){
  const capabilities=[...new Set((Array.isArray(hardCapabilities)?hardCapabilities:[]).map(value=>String(value||'').trim()).filter(Boolean))].sort();
  for(const requiredCapability of capabilities){
    if(!eligibleModel(model,dataClass,{contextTokens,requiredCapability,hardCapabilityGate:true}))return false;
  }
  return true;
}

export function selectModelWorkers({profile='STANDARD',domain='core',dataClass='PUBLIC',models=[],contextTokens=0,requiredCapability='text_reasoning',hardCapabilities=[]}={}){
  const limit=MODEL_MESH_LIMITS[String(profile).toUpperCase()]??0;
  if(limit<=0)return [];
  const ranked=models
    .filter(model=>eligibleModel(model,dataClass,{contextTokens,requiredCapability}))
    .filter(model=>passesEvidenceHardGates(model,dataClass,{contextTokens,hardCapabilities}))
    .sort((a,b)=>score(b,domain)-score(a,domain)||String(a.model_family).localeCompare(String(b.model_family)));
  const out=[];const seen=new Set();
  for(const model of ranked){const family=String(model.model_family||model.model_id||'');if(seen.has(family))continue;seen.add(family);out.push({...model,worker_role:out.length?'critic':'maker'});if(out.length>=limit)break;}
  return out;
}
