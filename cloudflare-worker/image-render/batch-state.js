import {createBatchState,nextSubmissionSceneIds,markSceneSubmitted,markSceneProviderResult,applySceneQualityDecision,cancelBatchState,resetFailedScenesForRetry,summarizeBatch} from './batch-engine.js';
import {createImageProviderRegistry} from './provider-registry.js';
import {rankImageModels} from './model-router.js';
import {evaluateImageQuality} from './quality-policy.js';

const STATE_KEY='image-render-batch-state-v2';
const TERMINAL_BATCH_STATES=new Set(['complete','complete_with_failures','failed','cancelled']);
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

async function readJson(request){try{return await request.json();}catch{return null;}}

export function createImageRenderBatchClass({registryFactory=createImageProviderRegistry,qualityEvaluator=evaluateImageQuality,now=()=>Date.now()}={}){
  return class ImageRenderBatchState{
    constructor(ctx,env){this.storage=ctx.storage;this.env=env||{};this.now=now;this.registry=registryFactory();}

    async load(){return await this.storage.get(STATE_KEY)||null;}
    async save(state){await this.storage.put(STATE_KEY,state);return state;}
    provider(){return this.registry.get('ai_horde',this.env);}

    async schedule(state,nearestProviderWaitSeconds=2){
      if(TERMINAL_BATCH_STATES.has(String(state?.status||''))){if(typeof this.storage.deleteAlarm==='function')await this.storage.deleteAlarm();return;}
      const delay=Math.min(30000,Math.max(2000,Number(nearestProviderWaitSeconds||2)*1000));
      await this.storage.setAlarm(this.now()+delay);
    }

    async cycle(){
      let state=await this.load();
      if(!state||TERMINAL_BATCH_STATES.has(String(state.status||'')))return state;
      const provider=this.provider();
      if(!provider){state.status='failed';state.error='image_render_provider_unavailable';await this.save(state);return state;}
      let nearestWait=2;

      for(const scene of [...state.scenes]){
        if(!['provider_wait','provider_processing'].includes(scene.status))continue;
        const attempt=scene.attempts?.[scene.attempts.length-1];
        if(!attempt?.provider_job_id)continue;
        const checked=await provider.check(attempt.provider_job_id);
        if(!checked?.ok||checked?.faulted){
          state=markSceneProviderResult(state,{sceneId:scene.scene_id,error:checked?.error||'provider_faulted',completedAt:new Date(this.now()).toISOString()});
          continue;
        }
        if(!checked.done){
          const current=state.scenes.find(x=>x.scene_id===scene.scene_id);if(current)current.status='provider_processing';
          nearestWait=Math.min(30,Math.max(2,Number(checked.waitTime||2)));
          continue;
        }
        const status=await provider.status(attempt.provider_job_id);
        const generation=status?.generations?.[0];
        if(!status?.ok||!generation){
          state=markSceneProviderResult(state,{sceneId:scene.scene_id,error:status?.error||'provider_generation_missing',completedAt:new Date(this.now()).toISOString()});
          continue;
        }
        state=markSceneProviderResult(state,{sceneId:scene.scene_id,generation,completedAt:new Date(this.now()).toISOString()});
        const current=state.scenes.find(x=>x.scene_id===scene.scene_id);
        const quality=await qualityEvaluator({scene:current,generation,qualityMode:state.quality_mode||'STRICT'});
        state=applySceneQualityDecision(state,{sceneId:scene.scene_id,quality,completedAt:new Date(this.now()).toISOString()});
      }

      const runnable=nextSubmissionSceneIds(state);
      if(runnable.length){
        const listed=await provider.listModels();
        const models=listed?.ok?listed.models:[];
        for(const sceneId of runnable){
          const scene=state.scenes.find(x=>x.scene_id===sceneId);if(!scene)continue;
          const ranked=rankImageModels({models,preferredModels:scene.model_candidates||[],history:state.model_history||{},limit:4});
          const selected=ranked.find(x=>Number(x.workerCount||0)>0);
          if(!selected){
            state=markSceneSubmitted(state,{sceneId,provider:'ai_horde',model:'',jobId:'',seed:null,submittedAt:new Date(this.now()).toISOString()});
            state=markSceneProviderResult(state,{sceneId,error:'no_eligible_free_image_model',completedAt:new Date(this.now()).toISOString()});
            continue;
          }
          const seed=`${sceneId}-${(scene.attempts?.length||0)+1}`;
          const submitted=await provider.submit({
            prompt:scene.compiled_prompt||scene.original_prompt,
            negativePrompt:scene.negative_prompt||'',
            width:Number(scene?.dimensions?.width)||512,
            height:Number(scene?.dimensions?.height)||512,
            n:1,seed,models:[selected.name],
          });
          if(!submitted?.ok){
            state=markSceneSubmitted(state,{sceneId,provider:'ai_horde',model:selected.name,jobId:'',seed,submittedAt:new Date(this.now()).toISOString()});
            state=markSceneProviderResult(state,{sceneId,error:submitted?.error||'provider_submit_failed',completedAt:new Date(this.now()).toISOString()});
            continue;
          }
          state=markSceneSubmitted(state,{sceneId,provider:'ai_horde',model:selected.name,jobId:submitted.jobId,seed,submittedAt:new Date(this.now()).toISOString()});
        }
      }

      await this.save(state);
      await this.schedule(state,nearestWait);
      return state;
    }

    async fetch(request){
      const url=new URL(request.url);
      if(url.pathname==='/create'&&request.method==='POST'){
        const body=await readJson(request);if(!body?.manifest)return json({ok:false,error:'manifest_required'},400);
        const existing=await this.load();
        if(existing)return json({ok:true,idempotent:true,state:existing,summary:summarizeBatch(existing)},200);
        const state=createBatchState(body.manifest);await this.save(state);await this.schedule(state,2);
        return json({ok:true,state,summary:summarizeBatch(state)},201);
      }
      if(url.pathname==='/status'&&request.method==='GET'){
        const state=await this.load();if(!state)return json({ok:false,error:'batch_not_found'},404);
        return json({ok:true,state,summary:summarizeBatch(state)});
      }
      if(url.pathname==='/cancel'&&request.method==='DELETE'){
        let state=await this.load();if(!state)return json({ok:false,error:'batch_not_found'},404);
        const provider=this.provider();
        if(provider){for(const scene of state.scenes||[]){if(!['provider_wait','provider_processing'].includes(scene.status))continue;const attempt=scene.attempts?.[scene.attempts.length-1];if(attempt?.provider_job_id)await provider.cancel(attempt.provider_job_id).catch(()=>null);}}
        state=cancelBatchState(state,{cancelledAt:new Date(this.now()).toISOString()});await this.save(state);if(typeof this.storage.deleteAlarm==='function')await this.storage.deleteAlarm();
        return json({ok:true,state,summary:summarizeBatch(state)});
      }
      if(url.pathname==='/retry'&&request.method==='POST'){
        const body=await readJson(request);let state=await this.load();if(!state)return json({ok:false,error:'batch_not_found'},404);
        state=resetFailedScenesForRetry(state,Array.isArray(body?.sceneIds)?body.sceneIds:[]);await this.save(state);await this.schedule(state,2);
        return json({ok:true,state,summary:summarizeBatch(state)});
      }
      if(url.pathname==='/tick'&&request.method==='POST'){
        const state=await this.cycle();if(!state)return json({ok:false,error:'batch_not_found'},404);return json({ok:true,state,summary:summarizeBatch(state)});
      }
      return json({ok:false,error:'not_found'},404);
    }

    async alarm(){await this.cycle();}
  };
}

export const ImageRenderBatchState=createImageRenderBatchClass();
