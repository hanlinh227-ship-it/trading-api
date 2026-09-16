const PROMPT_REPAIR_REASONS=new Set(['duplicate_subject','wrong_subject_count','wardrobe_mismatch','identity_mismatch','background_mismatch','camera_mismatch','text_or_watermark']);
const MODEL_RETRY_REASONS=new Set(['severe_anatomy','deformation','provider_censored','model_mismatch']);

const result=(decision,reasons=[],extra={})=>({decision,reasons:[...new Set(reasons.map(String))],...extra});
const validHttps=value=>{
  try{return new URL(String(value||'')).protocol==='https:';}catch{return false;}
};

export async function evaluateImageQuality({scene={},generation,qualityMode='STRICT',visualCritic=null}={}){
  if(!generation||typeof generation!=='object')return result('RETRY_MODEL',['malformed_generation'],{qaLevel:'STRUCTURAL'});
  if(!validHttps(generation.imageUrl))return result('RETRY_MODEL',['invalid_image_url'],{qaLevel:'STRUCTURAL'});
  if(generation.censored===true)return result('RETRY_MODEL',['provider_censored'],{qaLevel:'STRUCTURAL'});
  if(!String(generation.model||'').trim()||!String(generation.state||'').trim())return result('RETRY_MODEL',['malformed_generation'],{qaLevel:'STRUCTURAL'});
  if(!['ok','completed','complete'].includes(String(generation.state).toLowerCase()))return result('RETRY_MODEL',['provider_generation_state'],{qaLevel:'STRUCTURAL'});

  if(String(qualityMode||'STRICT').toUpperCase()==='STRUCTURAL')return result('PASS',[],{qaLevel:'STRUCTURAL',sceneState:'complete',qaConfidence:1});
  if(typeof visualCritic!=='function')return result('PASS_UNVERIFIED',['visual_critic_unavailable'],{qaLevel:'STRUCTURAL',sceneState:'complete_unverified',qaConfidence:0});

  let review;
  try{review=await visualCritic({scene,generation});}
  catch{return result('PASS_UNVERIFIED',['visual_critic_failed'],{qaLevel:'STRUCTURAL',sceneState:'complete_unverified',qaConfidence:0});}
  if(!review||review.ok!==true)return result('PASS_UNVERIFIED',['visual_critic_unavailable'],{qaLevel:'STRUCTURAL',sceneState:'complete_unverified',qaConfidence:Number(review?.confidence)||0});

  const reasons=Array.isArray(review.reasons)?review.reasons.map(String):[];
  const confidence=Math.max(0,Math.min(1,Number(review.confidence)||0));
  if(review.pass===true){
    if(confidence<0.8)return result('PASS_UNVERIFIED',['visual_confidence_below_threshold'],{qaLevel:'VISUAL',sceneState:'complete_unverified',qaConfidence:confidence});
    return result('PASS',reasons,{qaLevel:'VISUAL',sceneState:'complete',qaConfidence:confidence});
  }
  if(reasons.some(reason=>MODEL_RETRY_REASONS.has(reason)))return result('RETRY_MODEL',reasons,{qaLevel:'VISUAL',qaConfidence:confidence});
  if(reasons.some(reason=>PROMPT_REPAIR_REASONS.has(reason)))return result('RETRY_PROMPT',reasons,{qaLevel:'VISUAL',qaConfidence:confidence});
  return result('RETRY_SEED',reasons.length?reasons:['visual_quality_failed'],{qaLevel:'VISUAL',qaConfidence:confidence});
}

export {PROMPT_REPAIR_REASONS,MODEL_RETRY_REASONS};
