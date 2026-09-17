import {createWorkersAiClient,selectWorkersAiModel} from './workers-ai.js';
import {listProviderAdapters} from './provider-adapter-registry.js';

// Live runtime evidence. The build sandbox has no egress, so this runs in the deployed
// Worker: it is the only place that can honestly answer whether a runtime responds.
// The probe is deliberately minimal — the fewest diffusion steps the model allows — so
// collecting evidence never eats the free allocation that real work needs.
const PROBE_STEPS=1;

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
        });
        continue;
      }
      const model=selectWorkersAiModel('TEXT_TO_IMAGE');
      const result=await createWorkersAiClient().generate(env,{
        taskType:'TEXT_TO_IMAGE',prompt:'probe',steps:PROBE_STEPS,
      });
      providers.push({
        providerId:adapter.id,
        // The binding is present, so the runtime is discovered even if it did not answer.
        runtimeDiscovered:{ok:true,at,source:`binding:${adapter.id}`,detail:model},
        health:result.ok
          ?{ok:true,at,detail:`responded:${result.model}`}
          :{ok:false,at,detail:result.error,waitState:result.waitState??null,paidFallback:false},
      });
      continue;
    }
    // Network-reached providers are probed by their own adapters during execution; the
    // probe records that they are registered without claiming an unverified health pass.
    providers.push({
      providerId:adapter.id,
      runtimeDiscovered:{ok:true,at,source:'adapter_registry',detail:adapter.baseUrl},
      health:{ok:false,at,detail:'health_probe_deferred_to_execution'},
    });
  }

  return {ok:true,at,mode:'FREE_ONLY',paidFallback:false,autoPurchase:false,providers};
}
