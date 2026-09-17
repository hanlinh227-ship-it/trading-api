import {createWorkersAiClient,selectWorkersAiModel} from './workers-ai.js';
import {createVisualCriticRuntime} from './critic-runtime.js';
import {listProviderAdapters} from './provider-adapter-registry.js';
import {fullyPreservedMask,solidGreyscalePng} from './png.js';

// Live runtime evidence. This runs in the deployed Worker because build sandboxes cannot
// honestly prove inference availability. Each materially different capability is probed
// independently: a working FLUX request is not evidence that img2img, inpainting or the
// visual critic also work.
const PROBE_STEPS=1;
// FLUX takes a plain step count, but the img2img and inpainting pipelines multiply steps by
// strength and reject the request when the result rounds to zero: production answered
// "ValueError: After adjusting the num_inference..." to a probe asking for 1 step at
// strength 0.05. These paths ask for the smallest request that is still well formed.
const PROBE_EDIT_STEPS=4;
const PROBE_STRENGTH=1;
const PROBE_SIZE=256;

// The probe used to carry its images as base64 literals. Both were truncated -- no IEND,
// an IDAT shorter than its own length field -- and the inpainting runtime rejected them
// with "broken data stream when reading image", which was read as a missing runtime rather
// than as a corrupt probe. Generating them makes the probe image correct by construction.
const PROBE_IMAGE_BYTES=solidGreyscalePng(PROBE_SIZE,PROBE_SIZE,128);
// Nothing is editable: the probe only needs the runtime to accept the call, not to redraw.
const PROBE_MASK_BYTES=fullyPreservedMask(PROBE_SIZE,PROBE_SIZE);

const decodeBytes=bytes=>Array.from(bytes);
const waitEvidence=(result,at,model)=>({
  ok:false,
  at,
  model,
  detail:result?.error||'provider_request_failed',
  waitState:result?.waitState??null,
  paidFallback:false,
  ...(result?.diagnostic&&typeof result.diagnostic==='object'?{diagnostic:result.diagnostic}:{}),
  // Every model the task chain tried, so a task reported unavailable names what was
  // actually rejected instead of one model standing in for the whole capability.
  ...(Array.isArray(result?.attempted)&&result.attempted.length?{attempted:result.attempted}:{}),
});
const okEvidence=(result,at,model)=>result?.ok
  ?{ok:true,at,model:result.model||model,detail:`responded:${result.model||model}`}
  :waitEvidence(result,at,model);

async function probeWorkersAiTasks(env,at){
  const client=createWorkersAiClient();
  const image=decodeBytes(PROBE_IMAGE_BYTES);
  const mask=decodeBytes(PROBE_MASK_BYTES);
  const textModel=selectWorkersAiModel('TEXT_TO_IMAGE');
  const refModel=selectWorkersAiModel('REFERENCE_GENERATION');
  const inpaintModel=selectWorkersAiModel('INPAINT');

  const text=await client.generate(env,{taskType:'TEXT_TO_IMAGE',prompt:'probe',steps:PROBE_STEPS});
  const ref=await client.generate(env,{taskType:'REFERENCE_GENERATION',prompt:'a plain grey square',image,width:PROBE_SIZE,height:PROBE_SIZE,strength:PROBE_STRENGTH,steps:PROBE_EDIT_STEPS});
  const inpaint=await client.generate(env,{taskType:'INPAINT',prompt:'a plain grey square',image,mask,width:PROBE_SIZE,height:PROBE_SIZE,strength:PROBE_STRENGTH,steps:PROBE_EDIT_STEPS});
  const critic=await createVisualCriticRuntime().review(env,{
    intent:{taskType:'TEXT_TO_IMAGE',promptOriginal:'a plain gray square'},
    image,
  });

  return {
    TEXT_TO_IMAGE:okEvidence(text,at,textModel),
    REFERENCE_GENERATION:okEvidence(ref,at,refModel),
    INPAINT:okEvidence(inpaint,at,inpaintModel),
    VISUAL_CRITIC:critic?.ok
      ?{ok:true,at,model:critic.model,detail:`responded:${critic.model}`}
      :{
        ok:false,
        at,
        model:critic?.model||null,
        detail:critic?.reason||'visual_critic_request_failed',
        waitState:critic?.waitState??null,
        paidFallback:false,
        ...(critic?.diagnostic&&typeof critic.diagnostic==='object'?{diagnostic:critic.diagnostic}:{}),
        ...(Array.isArray(critic?.attempted)&&critic.attempted.length?{attempted:critic.attempted}:{}),
      },
  };
}

export async function probeImageRuntimes(env={},{now=()=>new Date().toISOString()}={}){
  const at=now();
  const providers=[];

  for(const adapter of listProviderAdapters()){
    if(adapter.authentication==='worker_ai_binding'){
      const bound=Boolean(env?.AI&&typeof env.AI.run==='function');
      if(!bound){
        providers.push({
          providerId:adapter.id,
          runtimeDiscovered:{ok:false,at,detail:'workers_ai_binding_unavailable'},
          health:{ok:false,at,detail:'workers_ai_binding_unavailable'},
          taskHealth:{},
        });
        continue;
      }
      const taskHealth=await probeWorkersAiTasks(env,at);
      const textHealth=taskHealth.TEXT_TO_IMAGE;
      providers.push({
        providerId:adapter.id,
        runtimeDiscovered:{ok:true,at,source:`binding:${adapter.id}`,detail:selectWorkersAiModel('TEXT_TO_IMAGE')},
        health:textHealth?.ok
          ?{ok:true,at,detail:textHealth.detail}
          :{
            ok:false,
            at,
            detail:textHealth?.detail||'provider_request_failed',
            waitState:textHealth?.waitState??null,
            paidFallback:false,
            ...(textHealth?.diagnostic?{diagnostic:textHealth.diagnostic}:{}),
          },
        taskHealth,
      });
      continue;
    }
    providers.push({
      providerId:adapter.id,
      runtimeDiscovered:{ok:true,at,source:'adapter_registry',detail:adapter.baseUrl},
      health:{ok:false,at,detail:'health_probe_deferred_to_execution'},
      taskHealth:{},
    });
  }

  return {ok:true,at,mode:'FREE_ONLY',paidFallback:false,autoPurchase:false,providers};
}
