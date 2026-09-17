import {
  aiHordeHealth,
  cancelAiHordeImage,
  checkAiHordeImage,
  listAiHordeModels,
  resolveAiHordeKey,
  statusAiHordeImage,
  submitAiHordeImage,
} from './ai-horde.js';
import {createImageProviderMesh} from './provider-mesh.js';
import {createWorkersAiProvider} from './workers-ai-provider.js';

export function createImageProviderRegistry({fetchImpl=fetch}={}){
  const ids=['cloudflare_workers_ai','ai_horde'];
  const mesh=createImageProviderMesh();
  return {
    list(){return [...ids];},
    listRegistrations(){return mesh.listRegistrations();},
    eligible(intent){return mesh.eligible(intent);},
    get(id,env={}){
      const providerId=String(id||'');
      // The reference-safe runtime is only handed out when its binding is really there,
      // so an absent binding fails the route closed instead of quietly falling through to
      // a provider that must never see a reference image.
      if(providerId==='cloudflare_workers_ai'){
        return env?.AI&&typeof env.AI.run==='function'?createWorkersAiProvider({env}):null;
      }
      if(providerId!=='ai_horde')return null;
      const apiKey=resolveAiHordeKey(env);
      return {
        id:'ai_horde',
        mode:'FREE_ONLY',
        monetaryCost:'zero',
        paidFallback:false,
        autoPurchase:false,
        privacyClasses:['PUBLIC'],
        referenceSafe:false,
        capabilities:{globalEdit:false,localEdit:false,segment:false},
        health:()=>aiHordeHealth({fetchImpl}),
        listModels:()=>listAiHordeModels({fetchImpl}),
        submit:input=>submitAiHordeImage({...input,apiKey,fetchImpl}),
        check:jobId=>checkAiHordeImage({jobId,apiKey,fetchImpl}),
        status:jobId=>statusAiHordeImage({jobId,apiKey,fetchImpl}),
        cancel:jobId=>cancelAiHordeImage({jobId,apiKey,fetchImpl}),
      };
    },
  };
}
