import {applySceneQualityDecision,cancelBatchState,createBatchState,markSceneProviderResult,markSceneSubmitted,nextSubmissionSceneIds,resetFailedScenesForRetry,summarizeBatch,TERMINAL_STATES} from './batch-engine.js';
import {compileScenePrompt} from './prompt-compiler.js';
import {rankImageModels} from './model-router.js';
import {createImageProviderRegistry} from './provider-registry.js';
import {evaluateImageQuality} from './quality-policy.js';

const STORAGE_KEY='image-render-batch-state-v2';
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const terminal=state=>state.scenes.length>0&&state.scenes.every(scene=>TERMINAL_STATES.has(scene.status));
const latestAttempt=scene=>scene?.attempts?.[scene.attempts.length-1]||null;
const batchHistory=state=>{
  const out={};
  for(const scene of state.scenes)for(const attempt of scene.attempts||[]){
    const model=String(attempt.model||'');if(!model)continue;
    out[model]??={successes:0,failures:0};
    if(['PASS','PASS_UNVERIFIED'].includes(String(attempt.QA_result||'')))out[model].successes+=1;
    else if(attempt.QA_result||attempt.provider_error)out[model].failures+=1;
  }
  return out;
};

export function createImageRenderBatchClass({registryFactory=createImageProviderRegistry,qualityEvaluator=evaluateImageQuality,now=()=>Date.now()}={}){
  return class ImageRenderBatchState{
    constructor(ctx,env){this.storage=ctx.storage;this.env=env||{};this.registry=registryFactory();this.qualityEvaluator=qualityEvaluator;this.now=now;}
    async load(){return this.storage.get(STORAGE_KEY);}
    async save(state){await this.storage.put(STORAGE_KEY,state);return state;}
    async schedule(state,nearestProviderWaitSeconds=2){if(terminal(state)||state.cancelled)return;const delay=Math.min(30_000,Math.max(2_000,Number(nearestProviderWaitSeconds||2)*1000));await this.storage.setAlarm(this.now()+delay);}
    async fetch(request){
      const url=new URL(request.url);
      if(url.pathname==='/create'){
        if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
        if(await this.load())return json({ok:false,error:'batch_already_exists'},409);
        let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
        if(!body?.manifest?.batch_id||!Array.isArray(body?.manifest?.scenes)||!body.manifest.scenes.length)return json({ok:false,error:'invalid_manifest'},400);
        const state=createBatchState(body.manifest);await this.save(state);await this.schedule(state,2);
        return json({ok:true,batchId:state.batch_id,summary:summarizeBatch(state),scenes:state.scenes},201);
      }
      const state=await this.load();if(!state)return json({ok:false,error:'batch_not_found'},404);
      if(url.pathname==='/status'){
        if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
        return json({ok:true,batchId:state.batch_id,summary:summarizeBatch(state),scenes:state.scenes});
      }
      if(url.pathname==='/cancel'){
        if(request.method!=='DELETE')return json({ok:false,error:'method_not_allowed'},405);
        const provider=this.registry.get('ai_horde',this.env);
        if(provider){
          for(const scene of state.scenes){const attempt=latestAttempt(scene);if(['provider_wait','provider_processing','qa_pending'].includes(scene.status)&&attempt?.provider_job_id){try{await provider.cancel(attempt.provider_job_id);}catch{}}}
        }
        const next=cancelBatchState(state);await this.save(next);return json({ok:true,batchId:next.batch_id,summary:summarizeBatch(next),scenes:next.scenes});
      }
      if(url.pathname==='/retry'){
        if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
        let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
        const next=resetFailedScenesForRetry(state,body?.sceneIds);await this.save(next);await this.schedule(next,2);return json({ok:true,batchId:next.batch_id,summary:summarizeBatch(next),scenes:next.scenes});
      }
      if(url.pathname==='/tick'){
        if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
        const next=await this.cycle(state);return json({ok:true,batchId:next.batch_id,summary:summarizeBatch(next),scenes:next.scenes});
      }
      return json({ok:false,error:'not_found'},404);
    }
    async alarm(){const state=await this.load();if(state)await this.cycle(state);}
    async cycle(inputState){
      let state=structuredClone(inputState);const provider=this.registry.get('ai_horde',this.env);let nearestWait=2;
      if(!provider){await this.save(state);await this.schedule(state,30);return state;}

      for(const sceneSnapshot of [...state.scenes]){
        const scene=state.scenes.find(item=>item.scene_id===sceneSnapshot.scene_id);if(!scene||!['provider_wait','provider_processing'].includes(scene.status))continue;
        const attempt=latestAttempt(scene);if(!attempt?.provider_job_id)continue;
        let check;try{check=await provider.check(attempt.provider_job_id);}catch{check={ok:false,error:'provider_check_failed'};}
        if(!check?.ok||check?.faulted){state=markSceneProviderResult(state,{sceneId:scene.scene_id,ok:false,error:check?.error||'provider_faulted',completedAt:new Date(this.now()).toISOString()});continue;}
        if(!check.done){nearestWait=Math.max(nearestWait,Number(check.waitTime||2));state=markSceneProviderResult(state,{sceneId:scene.scene_id,ok:true,processing:true});continue;}
        let status;try{status=await provider.status(attempt.provider_job_id);}catch{status={ok:false,error:'provider_status_failed'};}
        const generation=status?.ok&&status?.done&&Array.isArray(status.generations)?status.generations[0]:null;
        state=markSceneProviderResult(state,{sceneId:scene.scene_id,ok:Boolean(generation),generation,error:generation?null:(status?.error||'provider_generation_missing'),completedAt:new Date(this.now()).toISOString()});
        const updated=state.scenes.find(item=>item.scene_id===scene.scene_id);
        if(updated?.status==='qa_pending'&&generation){
          const quality=await this.qualityEvaluator({scene:updated,generation,qualityMode:state.manifest?.quality_mode||'STRICT'});
          state=applySceneQualityDecision(state,{sceneId:updated.scene_id,quality,completedAt:new Date(this.now()).toISOString()});
        }
      }

      const candidates=nextSubmissionSceneIds(state);
      if(candidates.length){
        let listed;try{listed=await provider.listModels();}catch{listed={ok:false,models:[]};}
        if(listed?.ok&&Array.isArray(listed.models)&&listed.models.length){
          const history=batchHistory(state);
          for(const sceneId of candidates){
            const scene=state.scenes.find(item=>item.scene_id===sceneId);if(!scene)continue;
            const compiled=compileScenePrompt(scene,state.manifest||{});scene.compiled_prompt=compiled.prompt;scene.negative_prompt=compiled.negativePrompt;
            const ranked=rankImageModels({models:listed.models,preferredModels:scene.model_candidates||[],history,limit:4});
            const selected=ranked[0];if(!selected)continue;
            const seed=scene.seed_strategy??String(this.now()+Number(scene.scene_id||0));
            let submitted;try{submitted=await provider.submit({sceneId:scene.scene_id,prompt:compiled.prompt,negativePrompt:compiled.negativePrompt,width:scene.dimensions?.width,height:scene.dimensions?.height,n:1,seed,models:[selected.name]});}catch{submitted={ok:false,error:'provider_submit_failed'};}
            if(submitted?.ok&&submitted.jobId){state=markSceneSubmitted(state,{sceneId:scene.scene_id,provider:'ai_horde',model:selected.name,jobId:submitted.jobId,seed,submittedAt:new Date(this.now()).toISOString()});}
            else{
              const synthetic=`submit-failed-${this.now()}-${scene.scene_id}`;
              state=markSceneSubmitted(state,{sceneId:scene.scene_id,provider:'ai_horde',model:selected.name,jobId:synthetic,seed,submittedAt:new Date(this.now()).toISOString()});
              state=markSceneProviderResult(state,{sceneId:scene.scene_id,ok:false,error:submitted?.error||'provider_submit_failed',completedAt:new Date(this.now()).toISOString()});
            }
          }
        }
      }
      await this.save(state);await this.schedule(state,nearestWait);return state;
    }
  };
}

export const ImageRenderBatchState=createImageRenderBatchClass();
export {STORAGE_KEY};
