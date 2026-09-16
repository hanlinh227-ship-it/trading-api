import {aiHordeHealth,cancelAiHordeImage,checkAiHordeImage,listAiHordeModels,resolveAiHordeKey,statusAiHordeImage,submitAiHordeImage} from './ai-horde.js';

export function createImageProviderRegistry({fetchImpl=fetch}={}){
  const providers={
    ai_horde:(env={})=>{
      const apiKey=resolveAiHordeKey(env);
      return {
        id:'ai_horde',
        monetaryCost:'zero',
        health:()=>aiHordeHealth({fetchImpl}),
        listModels:()=>listAiHordeModels({fetchImpl}),
        submit:input=>submitAiHordeImage({...input,apiKey,fetchImpl}),
        check:jobId=>checkAiHordeImage({jobId,apiKey,fetchImpl}),
        status:jobId=>statusAiHordeImage({jobId,apiKey,fetchImpl}),
        cancel:jobId=>cancelAiHordeImage({jobId,apiKey,fetchImpl}),
      };
    },
  };
  return {
    list:()=>Object.keys(providers),
    get:(id,env={})=>providers[String(id||'')]?.(env)||null,
  };
}
