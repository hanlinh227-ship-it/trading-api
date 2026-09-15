import {MODEL_MESH_LIMITS,eligibleModel} from './contracts.js';
import {MODEL_MESH_POLICY} from '../generated/model-mesh-policy.js';

/**
 * Capability fit for a routed domain.
 *
 * Weights come from the canonical domain_capabilities.yaml, compiled into the
 * runtime contract. That file declares weights_are_selection_metadata_only, so
 * it ranks candidates -- it never decides routing and never gates membership.
 *
 * Previously the score read model.quality_scores[domain], which is {} for every
 * model in the active registry, so ranking collapsed to a single reasoning
 * score and the domain was effectively ignored.
 */
function capabilityFit(model,domain){
  const weights=MODEL_MESH_POLICY.domain_capabilities?.[domain]||MODEL_MESH_POLICY.domain_capabilities?.core||{};
  let weighted=0,total=0;
  for(const [dimension,weight] of Object.entries(weights)){
    total+=weight;
    const capability=model?.capabilities?.[dimension];
    // A dimension the registry does not declare scores zero for fit but does
    // not disqualify: registry capability coverage is incomplete, and treating
    // a missing declaration as a veto would empty whole domains.
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

export function selectModelWorkers({profile='STANDARD',domain='core',dataClass='PUBLIC',models=[],contextTokens=0,requiredCapability='text_reasoning'}={}){
  const limit=MODEL_MESH_LIMITS[String(profile).toUpperCase()]??0;
  if(limit<=0)return [];
  const ranked=models.filter(m=>eligibleModel(m,dataClass,{contextTokens,requiredCapability})).sort((a,b)=>score(b,domain)-score(a,domain)||String(a.model_family).localeCompare(String(b.model_family)));
  const out=[];const seen=new Set();
  // One model family is one reasoner, never N -- policy.yaml
  // same_family_counts_as_independent_reasoning is false.
  for(const model of ranked){const family=String(model.model_family||model.model_id||'');if(seen.has(family))continue;seen.add(family);out.push({...model,worker_role:out.length?'critic':'maker'});if(out.length>=limit)break;}
  return out;
}
