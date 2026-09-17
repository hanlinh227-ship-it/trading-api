const PROMPT_REPAIR_REASONS=new Set([
  'duplicate_subject','wrong_subject_count','wardrobe_mismatch','identity_mismatch',
  'background_mismatch','camera_mismatch','text_or_watermark',
]);
const MODEL_RETRY_REASONS=new Set([
  'severe_anatomy','deformation','provider_censored','model_mismatch',
]);

import {decideQualityAction} from './critic.js';

const asReasons=value=>Array.isArray(value)?[...new Set(value.map(x=>String(x||'').trim()).filter(Boolean))]:[];
const finiteConfidence=value=>Number.isFinite(Number(value))?Math.min(1,Math.max(0,Number(value))):null;

function validHttpsUrl(value){
  try{return new URL(String(value||'')).protocol==='https:';}catch{return false;}
}

// An image either lives at a provider URL or in our own asset store. A synchronous
// runtime hands back bytes and no URL, so requiring a URL here would have failed every
// real Workers AI render as malformed.
const hasAsset=generation=>validHttpsUrl(generation?.imageUrl)||Boolean(String(generation?.assetRef||'').trim());

function structuralFailure(generation){
  if(!generation||typeof generation!=='object')return {decision:'FAIL_TERMINAL',reason:'invalid_generation_record'};
  if(!hasAsset(generation))return {decision:'FAIL_TERMINAL',reason:'invalid_image_url'};
  if(generation.censored===true)return {decision:'RETRY_MODEL',reason:'provider_censored'};
  if(!String(generation.model||'').trim())return {decision:'RETRY_MODEL',reason:'missing_generation_model'};
  if(!String(generation.state||'').trim())return {decision:'RETRY_MODEL',reason:'missing_generation_state'};
  const state=String(generation.state).toLowerCase();
  if(['faulted','failed','error','cancelled'].includes(state))return {decision:'RETRY_MODEL',reason:'provider_generation_failed'};
  return null;
}

function retryFromReasons(reasons){
  if(reasons.some(reason=>MODEL_RETRY_REASONS.has(reason)))return 'RETRY_MODEL';
  if(reasons.some(reason=>PROMPT_REPAIR_REASONS.has(reason)))return 'RETRY_PROMPT';
  return 'RETRY_SEED';
}

function result({decision,reasons=[],verified=false,qaLevel='STRUCTURAL',confidence=null,critic=null,repairAction=null}){
  const sceneStatus=decision==='PASS'?'complete':decision==='PASS_UNVERIFIED'?'complete_unverified':decision==='FAIL_TERMINAL'?'failed_quality':'retry_pending';
  return {decision,sceneStatus,verified,qaLevel,confidence,reasons:asReasons(reasons),...(critic?{critic}:{}),...(repairAction?{repairAction}:{})};
}

export async function evaluateImageQuality({scene,generation,qualityMode='STRICT',visualCritic=null}={}){
  if(!scene||typeof scene!=='object')return result({decision:'FAIL_TERMINAL',reasons:['invalid_scene']});
  const structural=structuralFailure(generation);
  if(structural)return result({decision:structural.decision,reasons:[structural.reason]});

  const mode=String(qualityMode||'STRICT').toUpperCase();
  if(mode==='STRUCTURAL')return result({decision:'PASS',verified:true,qaLevel:'STRUCTURAL',confidence:1});
  if(typeof visualCritic!=='function')return result({decision:'PASS_UNVERIFIED',verified:false,qaLevel:'STRUCTURAL',reasons:['visual_critic_unavailable']});

  let review;
  try{review=await visualCritic({scene,generation});}
  catch{return result({decision:'PASS_UNVERIFIED',verified:false,qaLevel:'STRUCTURAL',reasons:['visual_critic_unavailable']});}
  if(!review||review.ok!==true)return result({decision:'PASS_UNVERIFIED',verified:false,qaLevel:'STRUCTURAL',reasons:['visual_critic_unavailable']});

  // A critic that scored the image is judged on its scores and problems; the older
  // pass/reasons shape is still honoured so an existing critic keeps working.
  if(Number.isFinite(Number(review.overallScore))){
    const action=decideQualityAction(review,{strictVisual:mode!=='STRUCTURAL'});
    const decision=action.decision==='REPAIR_LOCAL'||action.decision==='REPAIR_GLOBAL'?'RETRY_PROMPT':action.decision;
    return result({
      decision,
      verified:action.verified===true,
      qaLevel:'VISUAL',
      confidence:finiteConfidence(review.confidence),
      reasons:action.reasons,
      critic:action.critic,
      repairAction:action.decision,
    });
  }

  const reasons=asReasons(review.reasons);
  const confidence=finiteConfidence(review.confidence);
  if(review.pass===true)return result({decision:'PASS',verified:true,qaLevel:'VISUAL',confidence,reasons});
  return result({decision:retryFromReasons(reasons),verified:false,qaLevel:'VISUAL',confidence,reasons:reasons.length?reasons:['visual_quality_failed']});
}

export {PROMPT_REPAIR_REASONS,MODEL_RETRY_REASONS};
