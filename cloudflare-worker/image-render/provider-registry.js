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

export function createImageProviderRegistry({fetchImpl=fetch}={}){
  const ids=['ai_horde'];
  const mesh=createImageProviderMesh();
  return {
    list(){return [...ids];},
    listRegistrations(){return mesh.listRegistrations();},
    eligible(intent){return mesh.eligible(intent);},
    get(id,env={}){
      if(String(id||'')!=='ai_horde')return null;
      const apiKey=resolveAiHordeKey(env);
      return {
        id:'ai_horde',
        mode:'FREE_ONLY',
        monetaryCost:'zero',
        paidFallback:false,
        autoPurchase:false,
        privacyClasses:['PUBLIC'],
        referenceSafe:false,
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
