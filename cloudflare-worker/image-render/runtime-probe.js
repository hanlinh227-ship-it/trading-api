import {createWorkersAiClient,selectWorkersAiModel} from './workers-ai.js';
import {createVisualCriticRuntime} from './critic-runtime.js';
import {listProviderAdapters} from './provider-adapter-registry.js';

// Live runtime evidence. This runs in the deployed Worker because build sandboxes cannot
// honestly prove inference availability. Each materially different capability is probed
// independently: a working FLUX request is not evidence that img2img, inpainting or the
// visual critic also work.
const PROBE_STEPS=1;
const PROBE_IMAGE_B64='iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAADHklEQVR4nO3UMQEAIAzAMED5nIMMjiYKenXPzF1A0vkdAPxjABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABBmABD2AEtABH80lN/gAAAAAElFTkSuQmCC';
const PROBE_MASK_B64='iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAADHUlEQVR4nO3UMQEAIAzAMMC/5yFjRxMFvXpnZg6Q9LYDgD0GAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEGAGEfHrAF/LZ/lzEAAAAASUVORK5CYII=';

const decodeBytes=b64=>Array.from(Uint8Array.from(atob(b64),char=>char.charCodeAt(0)));
const waitEvidence=(result,at,model)=>({
  ok:false,
  at,
  model,
  detail:result?.error||'provider_request_failed',
  waitState:result?.waitState??null,
  paidFallback:false,
  ...(result?.diagnostic&&typeof result.diagnostic==='object'?{diagnostic:result.diagnostic}:{}),
});
const okEvidence=(result,at,model)=>result?.ok
  ?{ok:true,at,model:result.model||model,detail:`responded:${result.model||model}`}
  :waitEvidence(result,at,model);

async function probeWorkersAiTasks(env,at){
  const client=createWorkersAiClient();
  const image=decodeBytes(PROBE_IMAGE_B64);
  const mask=decodeBytes(PROBE_MASK_B64);
  const textModel=selectWorkersAiModel('TEXT_TO_IMAGE');
  const refModel=selectWorkersAiModel('REFERENCE_GENERATION');
  const inpaintModel=selectWorkersAiModel('INPAINT');

  const text=await client.generate(env,{taskType:'TEXT_TO_IMAGE',prompt:'probe',steps:PROBE_STEPS});
  const ref=await client.generate(env,{taskType:'REFERENCE_GENERATION',prompt:'preserve the source image',image,width:256,height:256,strength:0.05,steps:PROBE_STEPS});
  const inpaint=await client.generate(env,{taskType:'INPAINT',prompt:'preserve the image',image,mask,width:256,height:256,strength:0.05,steps:PROBE_STEPS});
  const critic=await createVisualCriticRuntime().review(env,{
    intent:{taskType:'TEXT_TO_IMAGE',promptOriginal:'a plain gray square'},
    image:`data:image/png;base64,${PROBE_IMAGE_B64}`,
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
