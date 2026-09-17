import {WORKERS_AI_MODELS,sanitizeWorkersAiError} from './workers-ai.js';
import {benchmarkSuiteFor} from './benchmark-suite.js';

// The visual critic runs on the Worker's own AI binding. There is no fallback that fakes
// a verdict: without a real critic the caller gets ok:false and the quality layer reports
// PASS_UNVERIFIED rather than claiming the output was looked at.
const CRITIC_MODEL=WORKERS_AI_MODELS.visionLarge;
// A second vision model behind the first. The large model carries an explicit Meta licence
// acceptance on Cloudflare's side, so an account that has not accepted it still gets a
// real critic rather than none.
const CRITIC_CHAIN=[WORKERS_AI_MODELS.visionLarge,WORKERS_AI_MODELS.vision];

// Workers AI vision models take the image as an array of 8-bit values. A data URL or bare
// base64 string is a schema violation, so it is decoded here instead of being forwarded and
// read back as "the critic runtime is unavailable".
export function normalizeCriticImage(image){
  if(!image)return null;
  if(Array.isArray(image))return image.length?image:null;
  if(image instanceof Uint8Array)return image.length?Array.from(image):null;
  if(typeof image!=='string')return null;
  const b64=image.startsWith('data:')?image.slice(image.indexOf(',')+1):image;
  if(!b64.trim())return null;
  try{const bytes=Array.from(atob(b64),char=>char.charCodeAt(0));return bytes.length?bytes:null;}catch{return null;}
}

const binding=env=>{
  const ai=env?.AI;
  return ai&&typeof ai.run==='function'?ai:null;
};

const isAllocationExhausted=error=>{
  const status=Number(error?.status||error?.code||0);
  const message=String(error?.message||'').toLowerCase();
  return status===429||message.includes('neuron')||message.includes('quota')||message.includes('rate limit');
};

export async function visualCriticAvailability(env={}){
  if(!binding(env))return {available:false,provider:null,model:null,reason:'workers_ai_binding_unavailable'};
  return {available:true,provider:'cloudflare_workers_ai',model:CRITIC_MODEL,reason:null};
}

function criticPrompt(intent={}){
  const suite=benchmarkSuiteFor(intent.taskType)||benchmarkSuiteFor('TEXT_TO_IMAGE');
  const dimensions=suite.dimensions.map(dimension=>dimension.id);
  const locks=[
    intent.subjectCount?`exactly ${intent.subjectCount} subject(s)`:null,
    ...(intent.wardrobeConstraints||[]),
    ...(intent.propConstraints||[]),
    ...(intent.backgroundConstraints||[]),
    ...(intent.cameraConstraints||[]),
  ].filter(Boolean);
  return [
    'You are judging a generated image against the request that produced it.',
    `Requested: ${String(intent.promptCompiled||intent.promptOriginal||'').trim()}`,
    locks.length?`Constraints that must hold: ${locks.join('; ')}`:null,
    `Score each of these 0-100: ${dimensions.join(', ')}.`,
    'Reply with JSON only: {"overallScore":0-100,"confidence":0-1,',
    `"dimensions":{${dimensions.map(d=>`"${d}":0-100`).join(',')}},`,
    '"problems":[{"code":"...","scope":"local|global","severity":"minor|major|critical|terminal","target":"..."}]}',
    'Report a problem only if you can see it. Do not invent scores you cannot judge.',
  ].filter(Boolean).join('\n');
}

function parseCriticResponse(output){
  const raw=typeof output==='string'?output:String(output?.response??output?.result??'');
  if(!raw.trim())return null;
  const start=raw.indexOf('{');
  const end=raw.lastIndexOf('}');
  if(start===-1||end<=start)return null;
  let parsed;
  try{parsed=JSON.parse(raw.slice(start,end+1));}catch{return null;}
  if(!parsed||typeof parsed!=='object')return null;
  if(!Number.isFinite(Number(parsed.overallScore)))return null;
  return parsed;
}

export function createVisualCriticRuntime({model=CRITIC_MODEL}={}){
  return {
    async review(env={},{intent={},image}={}){
      const ai=binding(env);
      if(!ai)return {ok:false,reason:'visual_critic_unavailable',provider:null,model:null};
      const pixels=normalizeCriticImage(image);
      if(!pixels)return {ok:false,reason:'image_required',provider:'cloudflare_workers_ai',model};
      const chain=[...new Set([model,...CRITIC_CHAIN])];
      const attempted=[];
      let output=null,servedBy=null;
      for(const candidate of chain){
        try{
          output=await ai.run(candidate,{image:pixels,prompt:criticPrompt(intent),max_tokens:512});
          servedBy=candidate;
          break;
        }catch(error){
          const diagnostic=sanitizeWorkersAiError(error);
          attempted.push({model:candidate,diagnostic});
          if(isAllocationExhausted(error)){
            return {ok:false,reason:'free_allocation_exhausted',provider:'cloudflare_workers_ai',model:candidate,waitState:'WAITING_FOR_FREE_COMPUTE',paidFallback:false,diagnostic,attempted};
          }
        }
      }
      if(!servedBy){
        const last=attempted[attempted.length-1]||{};
        return {ok:false,reason:'visual_critic_request_failed',provider:'cloudflare_workers_ai',model:last.model||model,diagnostic:last.diagnostic,attempted};
      }
      const parsed=parseCriticResponse(output);
      if(!parsed)return {ok:false,reason:'visual_critic_unparseable_response',provider:'cloudflare_workers_ai',model:servedBy};
      const dimensions={};
      for(const [key,value] of Object.entries(parsed.dimensions||{})){
        if(Number.isFinite(Number(value)))dimensions[key]=Math.min(100,Math.max(0,Number(value)));
      }
      return {
        ok:true,
        provider:'cloudflare_workers_ai',
        model:servedBy,
        overallScore:Math.min(100,Math.max(0,Number(parsed.overallScore))),
        confidence:Math.min(1,Math.max(0,Number(parsed.confidence)||0)),
        dimensions,
        problems:Array.isArray(parsed.problems)?parsed.problems:[],
        regions:Array.isArray(parsed.regions)?parsed.regions:[],
      };
    },
  };
}
