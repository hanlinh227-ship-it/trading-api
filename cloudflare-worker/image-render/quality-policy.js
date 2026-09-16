const ALLOWED_VISUAL_DECISIONS=new Set(['PASS','RETRY_PROMPT','RETRY_MODEL','RETRY_SEED','FAIL_TERMINAL']);
const normalizeReasons=value=>Array.isArray(value)?value.map(String).filter(Boolean):[];

export async function evaluateImageQuality({scene,generation,qualityMode='STRICT',visualCritic=null}={}){
  const reasons=[];
  if(!generation?.imageUrl){
    return {decision:'RETRY_SEED',sceneStatus:'retry_pending',qaLevel:'STRUCTURAL',qaConfidence:1,reasons:['missing_image_url']};
  }
  if(generation?.censored===true){
    return {decision:'RETRY_MODEL',sceneStatus:'retry_pending',qaLevel:'STRUCTURAL',qaConfidence:1,reasons:['censored_generation']};
  }
  if(generation?.state&&String(generation.state).toLowerCase()!=='ok'){
    return {decision:'RETRY_SEED',sceneStatus:'retry_pending',qaLevel:'STRUCTURAL',qaConfidence:1,reasons:['generation_state_not_ok']};
  }

  const mode=String(qualityMode||'STRICT').toUpperCase();
  if(mode==='STRUCTURAL'){
    return {decision:'PASS',sceneStatus:'complete',qaLevel:'STRUCTURAL',qaConfidence:1,reasons};
  }

  if(typeof visualCritic!=='function'){
    return {decision:'PASS_UNVERIFIED',sceneStatus:'complete_unverified',qaLevel:'STRUCTURAL',qaConfidence:0,reasons:['visual_critic_unavailable']};
  }

  let result;
  try{result=await visualCritic({scene,generation});}
  catch{return {decision:'PASS_UNVERIFIED',sceneStatus:'complete_unverified',qaLevel:'STRUCTURAL',qaConfidence:0,reasons:['visual_critic_error']};}
  const decision=ALLOWED_VISUAL_DECISIONS.has(String(result?.decision||''))?String(result.decision):'PASS_UNVERIFIED';
  const visualReasons=normalizeReasons(result?.reasons);
  const confidence=Math.max(0,Math.min(1,Number(result?.confidence)||0));
  if(result?.ok!==true||decision==='PASS_UNVERIFIED'){
    return {decision:'PASS_UNVERIFIED',sceneStatus:'complete_unverified',qaLevel:'STRUCTURAL',qaConfidence:confidence,reasons:visualReasons.length?visualReasons:['visual_critic_unverified']};
  }
  if(decision==='PASS')return {decision,sceneStatus:'complete',qaLevel:'VISUAL',qaConfidence:confidence,reasons:visualReasons};
  if(decision==='FAIL_TERMINAL')return {decision,sceneStatus:'failed_quality',qaLevel:'VISUAL',qaConfidence:confidence,reasons:visualReasons};
  return {decision,sceneStatus:'retry_pending',qaLevel:'VISUAL',qaConfidence:confidence,reasons:visualReasons};
}
