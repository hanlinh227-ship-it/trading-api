const AI_HORDE_BASE='https://aihorde.net/api/v2';
const ANONYMOUS_KEY='0000000000';
const CLIENT_AGENT='github-brain-free-image-render:1:hanlinh227-ship-it/trading-api';

const clampInt=(value,min,max,fallback)=>{
  const parsed=Number(value);
  if(!Number.isFinite(parsed))return fallback;
  return Math.min(max,Math.max(min,Math.round(parsed)));
};
const snap64=value=>Math.max(64,Math.round(value/64)*64);
const validJobId=id=>/^[0-9a-f-]{16,64}$/i.test(String(id||''));

async function readJson(response){
  let body=null;
  try{body=await response.json();}catch{body=null;}
  return body;
}

function headers(apiKey,{json=false}={}){
  const out={'accept':'application/json','Client-Agent':CLIENT_AGENT,'apikey':String(apiKey||ANONYMOUS_KEY)};
  if(json)out['content-type']='application/json';
  return out;
}

export function resolveAiHordeKey(env={}){
  const configured=String(env?.AI_HORDE_API_KEY||'').trim();
  return configured||ANONYMOUS_KEY;
}

export async function submitAiHordeImage({prompt,negativePrompt='',width=512,height=512,steps=20,n=1,seed=null,models=[],apiKey=ANONYMOUS_KEY,fetchImpl=fetch}={}){
  const positive=String(prompt||'').trim();
  if(!positive)return {ok:false,status:400,error:'invalid_prompt'};
  const negative=String(negativePrompt||'').trim();
  const safeWidth=snap64(clampInt(width,256,1536,512));
  const safeHeight=snap64(clampInt(height,256,1536,512));
  const safeSteps=clampInt(steps,4,40,20);
  const safeN=clampInt(n,1,4,1);
  const payload={
    prompt:negative?`${positive} ### ${negative}`:positive,
    params:{
      cfg_scale:7,
      sampler_name:'k_euler_a',
      height:safeHeight,
      width:safeWidth,
      steps:safeSteps,
      n:safeN,
      karras:true,
      hires_fix:false,
      post_processing:[],
      ...(seed!==null&&seed!==undefined&&String(seed).trim()!==''?{seed:String(seed)}:{}),
    },
    allow_downgrade:true,
    nsfw:false,
    censor_nsfw:true,
    trusted_workers:false,
    r2:true,
    replacement_filter:true,
    shared:false,
    slow_workers:true,
    dry_run:false,
  };
  const requestedModels=Array.isArray(models)?models.map(value=>String(value).trim()).filter(Boolean).slice(0,4):[];
  if(requestedModels.length)payload.models=requestedModels;
  let response;
  try{
    response=await fetchImpl(`${AI_HORDE_BASE}/generate/async`,{method:'POST',headers:headers(apiKey,{json:true}),body:JSON.stringify(payload)});
  }catch{return {ok:false,status:0,error:'provider_unreachable'};}
  const body=await readJson(response);
  if(!response.ok||!body?.id)return {ok:false,status:Number(response.status||0),error:String(body?.rc||body?.message||'provider_rejected')};
  return {ok:true,status:Number(response.status||200),provider:'ai_horde',jobId:String(body.id),kudos:Number(body.kudos||0),anonymous:String(apiKey)===ANONYMOUS_KEY,request:{width:safeWidth,height:safeHeight,steps:safeSteps,n:safeN,models:requestedModels}};
}

export async function checkAiHordeImage({jobId,apiKey=ANONYMOUS_KEY,fetchImpl=fetch}={}){
  if(!validJobId(jobId))return {ok:false,status:400,error:'invalid_job_id'};
  let response;
  try{response=await fetchImpl(`${AI_HORDE_BASE}/generate/check/${encodeURIComponent(jobId)}`,{headers:headers(apiKey)});}catch{return {ok:false,status:0,error:'provider_unreachable'};}
  const body=await readJson(response);
  if(!response.ok)return {ok:false,status:Number(response.status||0),error:String(body?.rc||body?.message||'provider_rejected')};
  return {ok:true,status:Number(response.status||200),provider:'ai_horde',jobId:String(jobId),done:Boolean(body?.done),faulted:Boolean(body?.faulted),waitTime:Number(body?.wait_time||0),queuePosition:Number(body?.queue_position||0),finished:Number(body?.finished||0),processing:Number(body?.processing||0),waiting:Number(body?.waiting||0),isPossible:body?.is_possible!==false};
}

export async function statusAiHordeImage({jobId,apiKey=ANONYMOUS_KEY,fetchImpl=fetch}={}){
  if(!validJobId(jobId))return {ok:false,status:400,error:'invalid_job_id'};
  let response;
  try{response=await fetchImpl(`${AI_HORDE_BASE}/generate/status/${encodeURIComponent(jobId)}`,{headers:headers(apiKey)});}catch{return {ok:false,status:0,error:'provider_unreachable'};}
  const body=await readJson(response);
  if(!response.ok)return {ok:false,status:Number(response.status||0),error:String(body?.rc||body?.message||'provider_rejected')};
  const generations=Array.isArray(body?.generations)?body.generations.map(item=>({imageUrl:typeof item?.img==='string'?item.img:null,seed:item?.seed??null,model:item?.model??null,state:item?.state??null,censored:Boolean(item?.censored)})).filter(item=>item.imageUrl):[];
  return {ok:true,status:Number(response.status||200),provider:'ai_horde',jobId:String(jobId),done:Boolean(body?.done),faulted:Boolean(body?.faulted),waitTime:Number(body?.wait_time||0),queuePosition:Number(body?.queue_position||0),generations};
}

export async function cancelAiHordeImage({jobId,apiKey=ANONYMOUS_KEY,fetchImpl=fetch}={}){
  if(!validJobId(jobId))return {ok:false,status:400,error:'invalid_job_id'};
  let response;
  try{response=await fetchImpl(`${AI_HORDE_BASE}/generate/status/${encodeURIComponent(jobId)}`,{method:'DELETE',headers:headers(apiKey)});}catch{return {ok:false,status:0,error:'provider_unreachable'};}
  const body=await readJson(response);
  if(!response.ok)return {ok:false,status:Number(response.status||0),error:String(body?.rc||body?.message||'provider_rejected')};
  return {ok:true,status:Number(response.status||200),provider:'ai_horde',jobId:String(jobId),cancelled:true};
}

export async function aiHordeHealth({fetchImpl=fetch}={}){
  let response;
  try{response=await fetchImpl(`${AI_HORDE_BASE}/status/heartbeat`,{headers:{'accept':'application/json','Client-Agent':CLIENT_AGENT}});}catch{return {ok:false,status:0};}
  return {ok:Boolean(response.ok),status:Number(response.status||0)};
}
