const LOCAL_REPAIR=new Set(['hand_anatomy','anatomy_error','wardrobe_mismatch','prop_mismatch','object_mismatch','text_error','small_artifact']);
const MODEL_SWITCH=new Set(['identity_mismatch','model_mismatch','severe_deformation']);
const PROMPT_RETRY=new Set(['background_mismatch','camera_mismatch','composition_mismatch','wrong_subject_count','missing_required_object']);

function preserveBlocks(intent,target){
  const normalized=String(target||'').toLowerCase();
  return (intent?.preserveRegions||[]).some(region=>normalized.includes(String(region).toLowerCase())||String(region).toLowerCase().includes(normalized));
}

export function planRepair({intent={},criticResult={},capabilities={},attempts={}}={}){
  const total=Number(attempts.total||0),totalLimit=Number(attempts.totalLimit||5);
  const repair=Number(attempts.repair||0),repairLimit=Number(attempts.repairLimit||2);
  if(total>=totalLimit)return {action:'FAIL_TERMINAL',reason:'total_attempt_limit_reached'};
  const problems=Array.isArray(criticResult?.problems)?criticResult.problems:[];
  if(problems.length===0)return {action:'NONE',reason:'no_repairable_problem'};
  const problem=problems[0];
  const code=String(problem?.code||'');
  const target=String(problem?.target||code||'unknown');
  if(MODEL_SWITCH.has(code))return {action:'RETRY_MODEL',reason:code,target};
  if(PROMPT_RETRY.has(code)&&preserveBlocks(intent,target))return {action:'RETRY_PROMPT',reason:'preserve_region_protected',target};
  if(problem?.scope==='local'||LOCAL_REPAIR.has(code)){
    if(repair>=repairLimit)return {action:'RETRY_MODEL',reason:'repair_attempt_limit_reached',target};
    if(capabilities.segment===true&&capabilities.localEdit===true&&!preserveBlocks(intent,target))return {action:'LOCAL_MASKED_EDIT',reason:code,target,requiresSegmentation:true,preserveRegions:[...(intent.preserveRegions||[])]};
    return {action:'RETRY_SEED',reason:'local_repair_runtime_unavailable',target};
  }
  if(problem?.scope==='global'&&capabilities.globalEdit===true&&intent.destructiveRedrawAllowed===true)return {action:'GLOBAL_EDIT',reason:code,target,requiresSegmentation:false};
  if(PROMPT_RETRY.has(code))return {action:'RETRY_PROMPT',reason:code,target};
  return {action:'RETRY_SEED',reason:code||'unclassified_quality_problem',target};
}
