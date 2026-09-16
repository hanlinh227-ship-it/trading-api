import {
  applySceneQualityDecision,
  cancelBatchState,
  createBatchState,
  markSceneProviderResult,
  markSceneSubmitted,
  nextSubmissionSceneIds,
  resetFailedScenesForRetry,
  summarizeBatch,
} from './batch-engine.js';
import {rankImageModels} from './model-router.js';
import {createImageProviderRegistry} from './provider-registry.js';
import {evaluateImageQuality} from './quality-policy.js';

const STATE_KEY='image-render-batch-state-v2';
const TERMINAL_BATCH_STATES=new Set(['complete','complete_with_failures','cancelled','failed']);
const ACTIVE_SCENE_STATES=new Set(['provider_wait','provider_processing','qa_pending']);

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8'}});
const latestAttempt=scene=>scene?.attempts?.[scene.attempts.length-1]||null;
const clone=value=>structuredClone(value);

function modelHistory(state){
  const history={};
  for(const scene of state.scenes||[]){
    for(const attempt of scene.attempts||[]){
      const model=String(attempt?.model||'').trim();
      if(!model)continue;
      history[model]||={successes:0,failures:0};
      if(['PASS','PASS_UNVERIFIED'].includes(attempt.qa_result)) history[model].successes+=1;
      if(['RETRY_PROMPT','RETRY_MODEL','RETRY_SEED','FAIL_TERMINAL','provider_failure'].includes(attempt.qa_result)) history[model].failures+=1;
    }
  }
  return history;
}

function chosenProviderId(registry){
  const ids=registry?.list?.()||[];
  return ids.includes('ai_horde')?'ai_horde':ids[0]||null;
}

function sceneSeed(scene,attemptNumber,nowValue){
  const raw=`${scene.scene_id}:${attemptNumber}:${nowValue}`;
  let hash=2166136261;
  for(let i=0;i<raw.length;i+=1){hash^=raw.charCodeAt(i);hash=Math.imul(hash,16777619);}
  return String(hash>>>0);
}

function generationFromStatus(statusResult){
  return Array.isArray(statusResult?.generations)&&statusResult.generations.length?statusResult.generations[0]:null;
}

export function createImageRenderBatchClass({
  registryFactory=options=>createImageProviderRegistry(options),
  qualityEvaluator=evaluateImageQuality,
  now=()=>Date.now(),
}={}){
  return class ImageRenderBatchState{
    constructor(state,env){
      this.storage=state.storage;
      this.env=env||{};
    }

    async load(){return await this.storage.get(STATE_KEY);}
    async save(state){await this.storage.put(STATE_KEY,state);return state;}

    async schedule(seconds=2){
      if(typeof this.storage.setAlarm!=='function')return;
      const delay=Math.min(30_000,Math.max(2_000,Number(seconds||2)*1000));
      await this.storage.setAlarm(now()+delay);
    }

    async clearAlarm(){
      if(typeof this.storage.deleteAlarm==='function')await this.storage.deleteAlarm();
    }

    response(state,status=200){return json({ok:true,state,summary:summarizeBatch(state)},status);}

    async fetch(request){
      const url=new URL(request.url);
      if(url.pathname==='/create'&&request.method==='POST'){
        let body=null;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
        if(!body?.manifest?.batch_id||!Array.isArray(body?.manifest?.scenes))return json({ok:false,error:'image_render_manifest_required'},400);
        const state=createBatchState(body.manifest);
        await this.save(state);
        if(!TERMINAL_BATCH_STATES.has(summarizeBatch(state).status))await this.schedule(2);
        return this.response(state,201);
      }
      if(url.pathname==='/status'&&request.method==='GET'){
        const state=await this.load();
        if(!state)return json({ok:false,error:'image_render_batch_not_found'},404);
        return this.response(state);
      }
      if(url.pathname==='/cancel'&&request.method==='DELETE'){
        let state=await this.load();
        if(!state)return json({ok:false,error:'image_render_batch_not_found'},404);
        const registry=registryFactory({});
        const cancellations=[];
        for(const scene of state.scenes||[]){
          if(!ACTIVE_SCENE_STATES.has(scene.status))continue;
          const attempt=latestAttempt(scene);
          const provider=registry.get?.(attempt?.provider,this.env);
          if(provider?.cancel&&attempt?.provider_job_id)cancellations.push(Promise.resolve(provider.cancel(attempt.provider_job_id)).catch(()=>null));
        }
        await Promise.all(cancellations);
        state=cancelBatchState(state);
        await this.save(state);
        await this.clearAlarm();
        return this.response(state);
      }
      if(url.pathname==='/retry'&&request.method==='POST'){
        let body=null;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
        let state=await this.load();
        if(!state)return json({ok:false,error:'image_render_batch_not_found'},404);
        state=resetFailedScenesForRetry(state,Array.isArray(body?.sceneIds)?body.sceneIds:[]);
        await this.save(state);
        if(!TERMINAL_BATCH_STATES.has(summarizeBatch(state).status))await this.schedule(2);
        return this.response(state);
      }
      if(url.pathname==='/tick'&&request.method==='POST'){
        const state=await this.cycle();
        if(!state)return json({ok:false,error:'image_render_batch_not_found'},404);
        return this.response(state);
      }
      return json({ok:false,error:'not_found'},404);
    }

    async alarm(){await this.cycle();}

    async cycle(){
      let state=await this.load();
      if(!state)return null;
      if(TERMINAL_BATCH_STATES.has(summarizeBatch(state).status)){await this.clearAlarm();return state;}
      const registry=registryFactory({});
      let nearestProviderWaitSeconds=2;

      for(const snapshotScene of [...state.scenes]){
        if(!['provider_wait','provider_processing'].includes(snapshotScene.status))continue;
        const scene=state.scenes.find(item=>item.scene_id===snapshotScene.scene_id);
        const attempt=latestAttempt(scene);
        const provider=registry.get?.(attempt?.provider,this.env);
        if(!provider||!attempt?.provider_job_id){
          state=markSceneProviderResult(state,{sceneId:scene.scene_id,generation:null,error:'provider_adapter_unavailable',completedAt:new Date(now()).toISOString()});
          continue;
        }
        let check;
        try{check=await provider.check(attempt.provider_job_id);}catch{check={ok:false,error:'provider_check_failed'};}
        if(!check?.ok||check?.faulted||check?.isPossible===false){
          state=markSceneProviderResult(state,{sceneId:scene.scene_id,generation:null,error:check?.error||'provider_job_failed',completedAt:new Date(now()).toISOString()});
          continue;
        }
        nearestProviderWaitSeconds=Math.min(nearestProviderWaitSeconds||30,Math.max(2,Number(check.waitTime||2)));
        if(!check.done){
          const live=state.scenes.find(item=>item.scene_id===scene.scene_id);
          live.status='provider_processing';
          continue;
        }
        let statusResult;
        try{statusResult=await provider.status(attempt.provider_job_id);}catch{statusResult={ok:false,error:'provider_status_failed'};}
        const generation=statusResult?.ok?generationFromStatus(statusResult):null;
        state=markSceneProviderResult(state,{sceneId:scene.scene_id,generation,error:statusResult?.error||'provider_generation_missing',completedAt:new Date(now()).toISOString()});
        const updatedScene=state.scenes.find(item=>item.scene_id===scene.scene_id);
        if(updatedScene.status==='qa_pending'){
          let quality;
          try{quality=await qualityEvaluator({scene:updatedScene,generation,qualityMode:state.quality_mode||'STRICT'});}catch{quality={decision:'RETRY_MODEL',verified:false,reasons:['visual_critic_error']};}
          state=applySceneQualityDecision(state,{sceneId:scene.scene_id,quality,completedAt:new Date(now()).toISOString()});
        }
      }

      const ids=nextSubmissionSceneIds(state);
      if(ids.length){
        const providerId=chosenProviderId(registry);
        const provider=providerId?registry.get?.(providerId,this.env):null;
        let ranked=[];
        if(provider?.listModels){
          try{
            const listed=await provider.listModels();
            if(listed?.ok)ranked=rankImageModels({models:listed.models||[],preferredModels:state.preferred_models||state.model_candidates||[],history:modelHistory(state),limit:8});
          }catch{ranked=[];}
        }
        const fallbackModel=ranked[0]?.name||null;
        for(const sceneId of ids){
          const scene=state.scenes.find(item=>item.scene_id===sceneId);
          if(!scene)continue;
          const attemptNumber=(scene.attempts?.length||0)+1;
          const sceneCandidates=Array.isArray(scene.model_candidates)?scene.model_candidates:[];
          const selectedModel=ranked.find(item=>sceneCandidates.includes(item.name))?.name||fallbackModel||sceneCandidates[0]||null;
          const dims=scene.dimensions||{};
          const seed=sceneSeed(scene,attemptNumber,now());
          let submitted;
          try{
            submitted=provider?.submit?await provider.submit({
              sceneId,
              prompt:scene.compiled_prompt||scene.original_prompt||'',
              negativePrompt:scene.negative_prompt||'',
              width:Number(dims.width||512),
              height:Number(dims.height||512),
              steps:Number(scene.steps||20),
              n:1,
              seed,
              models:selectedModel?[selectedModel]:[],
            }):{ok:false,error:'provider_adapter_unavailable'};
          }catch{submitted={ok:false,error:'provider_submit_failed'};}
          if(submitted?.ok&&submitted?.jobId){
            state=markSceneSubmitted(state,{sceneId,provider:providerId,model:selectedModel||'',jobId:submitted.jobId,seed,submittedAt:new Date(now()).toISOString()});
          }else{
            state=markSceneSubmitted(state,{sceneId,provider:providerId||'none',model:selectedModel||'',jobId:'provider-submit-failed',seed,submittedAt:new Date(now()).toISOString()});
            state=markSceneProviderResult(state,{sceneId,generation:null,error:submitted?.error||'provider_submit_failed',completedAt:new Date(now()).toISOString()});
          }
        }
      }

      await this.save(state);
      const summary=summarizeBatch(state);
      if(TERMINAL_BATCH_STATES.has(summary.status))await this.clearAlarm();
      else await this.schedule(nearestProviderWaitSeconds);
      return state;
    }
  };
}

export const ImageRenderBatchState=createImageRenderBatchClass();
