import {WORKERS_AI_MODELS} from './workers-ai.js';
import {benchmarkSuiteFor} from './benchmark-suite.js';

// The visual critic runs on the Worker's own AI binding. There is no fallback that fakes
// a verdict: without a real critic the caller gets ok:false and the quality layer reports
// PASS_UNVERIFIED rather than claiming the output was looked at.
const CRITIC_MODEL=WORKERS_AI_MODELS.visionLarge;

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

// Ask about the dimensions that decide this task, so a reference render is judged on
// identity rather than on generic prettiness.
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

// The model returns text. Anything that is not parseable JSON with a numeric score is
// unverified: a critic that did not answer is not a pass.
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
      if(!image)return {ok:false,reason:'image_required',provider:'cloudflare_workers_ai',model};
      let output;
      try{
        output=await ai.run(model,{image,prompt:criticPrompt(intent),max_tokens:512});
      }catch(error){
        if(isAllocationExhausted(error)){
          return {ok:false,reason:'free_allocation_exhausted',provider:'cloudflare_workers_ai',model,waitState:'WAITING_FOR_FREE_COMPUTE',paidFallback:false};
        }
        return {ok:false,reason:'visual_critic_request_failed',provider:'cloudflare_workers_ai',model};
      }
      const parsed=parseCriticResponse(output);
      if(!parsed)return {ok:false,reason:'visual_critic_unparseable_response',provider:'cloudflare_workers_ai',model};
      const dimensions={};
      for(const [key,value] of Object.entries(parsed.dimensions||{})){
        if(Number.isFinite(Number(value)))dimensions[key]=Math.min(100,Math.max(0,Number(value)));
      }
      return {
        ok:true,
        provider:'cloudflare_workers_ai',
        model,
        overallScore:Math.min(100,Math.max(0,Number(parsed.overallScore))),
        confidence:Math.min(1,Math.max(0,Number(parsed.confidence)||0)),
        dimensions,
        problems:Array.isArray(parsed.problems)?parsed.problems:[],
        regions:Array.isArray(parsed.regions)?parsed.regions:[],
      };
    },
  };
}
