import {
  applySceneQualityDecision,
  modelHistoryFromState,
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
import {createVisualCriticRuntime} from './critic-runtime.js';
import {sourceBytesFor,maskBytesFor} from './workers-ai-provider.js';
import {planRepair} from './repair-planner.js';

const STATE_KEY='image-render-batch-state-v2';
const TERMINAL_BATCH_STATES=new Set(['complete','complete_with_failures','cancelled','failed']);
const ACTIVE_SCENE_STATES=new Set(['provider_wait','provider_processing','qa_pending']);

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8'}});
const latestAttempt=scene=>scene?.attempts?.[scene.attempts.length-1]||null;
const clone=value=>structuredClone(value);

// Routing history is keyed by the model that actually produced the image, so a model the
// provider substituted away from is not judged on output it never generated.
const modelHistory=state=>modelHistoryFromState(state);

// Work that is bound to an image -- a reference, a source, a mask, or a task that cannot
// exist without one -- may never be handed to a provider that was not chosen for it.
const REFERENCE_BOUND_TASKS=new Set(['REFERENCE_GENERATION','CHARACTER_CONSISTENCY','PRODUCT_CONSISTENCY','IMAGE_EDIT_GLOBAL','IMAGE_EDIT_LOCAL','INPAINT','OUTPAINT','BACKGROUND_REPLACE','OBJECT_REPLACE','TEXT_RENDER_EDIT','MULTI_IMAGE_COMPOSE','STYLE_TRANSFER','TARGETED_REPAIR']);

function sceneIsReferenceBound(scene={}){
  if(Array.isArray(scene.reference_assets)&&scene.reference_assets.length>0)return true;
  if(scene.source_image||scene.mask)return true;
  return REFERENCE_BOUND_TASKS.has(String(scene.task_type||''));
}

// The control plane already decided where this scene runs. Honouring that decision is the
// whole job here: picking a provider again is what silently moved reference work onto the
// volunteer provider. Only a manifest from before routing existed -- prompt-only, PUBLIC,
// no route recorded -- may still fall back to the registry's default.
function resolveSceneProvider({state,scene,registry,env}){
  const routed=String(scene.provider_id||'').trim();
  if(routed){
    const provider=registry.get?.(routed,env);
    return provider?{id:routed,provider}:{id:routed,provider:null,error:'routed_provider_unavailable'};
  }
  const privacy=String(scene.privacy_class||state.data_class||'PUBLIC');
  if(sceneIsReferenceBound(scene)||privacy!=='PUBLIC')return {id:null,provider:null,error:'reference_route_lost'};
  const ids=registry.list?.()||[];
  const id=ids.includes('ai_horde')?'ai_horde':ids[0]||null;
  if(!id)return {id:null,provider:null,error:'provider_adapter_unavailable'};
  return {id,provider:registry.get?.(id,env)||null,error:null};
}

// Rendered bytes are held beside the batch that produced them, never in trading state and
// never beyond the batch's own lifetime. They are what `/assets` serves and what the critic
// actually looks at.
const assetKey=(sceneId,attempt)=>`image-render-asset:${sceneId}:${attempt}`;

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
      // Serves an image this batch produced. The bytes never leave the batch that made
      // them, and a reference that does not belong to this batch cannot reach anything.
      if(url.pathname==='/asset'&&request.method==='GET'){
        const ref=String(url.searchParams.get('ref')||'').trim();
        if(!ref.startsWith('image-render-asset:'))return json({ok:false,error:'image_render_asset_ref_required'},400);
        const record=await this.storage.get(ref);
        if(!record||!Array.isArray(record.bytes))return json({ok:false,error:'image_render_asset_not_found'},404);
        return new Response(Uint8Array.from(record.bytes),{status:200,headers:{'content-type':String(record.contentType||'image/png'),'cache-control':'no-store'}});
      }
      if(url.pathname==='/tick'&&request.method==='POST'){
        const state=await this.cycle();
        if(!state)return json({ok:false,error:'image_render_batch_not_found'},404);
        return this.response(state);
      }
      return json({ok:false,error:'not_found'},404);
    }

    async alarm(){await this.cycle();}

    // Rendered bytes live in this batch's own storage, keyed to the attempt that made
    // them. The state we persist carries a reference, never the image itself.
    async storeGeneration(sceneId,attempt,generation){
      const bytes=Array.isArray(generation?.bytes)?generation.bytes:null;
      const record={...generation};
      delete record.bytes;
      if(!bytes||bytes.length===0)return {generation:record,bytes:null};
      const ref=assetKey(sceneId,attempt);
      try{
        await this.storage.put(ref,{contentType:generation.contentType||'image/png',bytes,at:new Date(now()).toISOString()});
      }catch{
        // An image the store will not take is a failed attempt, not a crashed alarm.
        // Losing the cycle here would strand every other scene in the batch.
        return {generation:{...record,assetRef:null,storeError:'image_render_asset_not_stored',byteLength:bytes.length},bytes:null};
      }
      // The superseded attempt's image has nothing left to serve, and keeping it would
      // grow this batch's storage with every retry.
      if(attempt>1)await Promise.resolve(this.storage.delete?.(assetKey(sceneId,attempt-1))).catch(()=>null);
      return {generation:{...record,assetRef:ref,byteLength:bytes.length},bytes};
    }

    // The visual critic is only offered when its runtime is really present. Without it the
    // quality layer reports PASS_UNVERIFIED rather than claiming the image was looked at.
    visualCriticFor(bytes){
      const ai=this.env?.AI;
      if(!ai||typeof ai.run!=='function'||!bytes||bytes.length===0)return null;
      const runtime=createVisualCriticRuntime();
      return async ({scene})=>runtime.review(this.env,{intent:scene?.intent||{},image:bytes});
    }

    async settleQuality(state,sceneId,generation,bytes,qualityEvaluator,capabilities={}){
      const updatedScene=state.scenes.find(item=>item.scene_id===sceneId);
      if(!updatedScene||updatedScene.status!=='qa_pending')return state;
      let quality;
      try{
        quality=await qualityEvaluator({
          scene:updatedScene,
          generation,
          qualityMode:state.quality_mode||'STRICT',
          visualCritic:this.visualCriticFor(bytes),
        });
      }catch{quality={decision:'RETRY_MODEL',verified:false,reasons:['visual_critic_error']};}
      let next=applySceneQualityDecision(state,{sceneId,quality,completedAt:new Date(now()).toISOString()});

      // A fixable fault in a finished image is worth repairing rather than re-rolling:
      // a fresh render throws away everything the first one got right. The planner decides
      // whether a repair is possible at all with the runtime we actually have.
      const scene=next.scenes.find(item=>item.scene_id===sceneId);
      if(!scene||scene.status!=='retry_pending')return next;
      if(!['REPAIR_LOCAL','REPAIR_GLOBAL'].includes(String(quality.repairAction||'')))return next;
      const repairCount=(scene.attempts||[]).filter(attempt=>attempt.repair).length;
      const plan=planRepair({
        intent:scene.intent||{destructiveRedrawAllowed:scene.destructive_redraw_allowed===true},
        criticResult:quality.critic,
        capabilities,
        attempts:{total:scene.attempts?.length||0,totalLimit:Number(next.retry?.maxAttempts||3)+2,repair:repairCount,repairLimit:2},
      });
      if(!['GLOBAL_EDIT','LOCAL_MASKED_EDIT'].includes(plan.action))return next;
      scene.pending_repair={action:plan.action,reason:plan.reason,target:plan.target||null,sourceRef:generation?.assetRef||null};
      return next;
    }

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
      // Model ranking is per provider, and only providers that publish a live model list
      // take part. A routed model stays the scene's first candidate either way.
      const rankedByProvider=new Map();
      for(const sceneId of ids){
        const scene=state.scenes.find(item=>item.scene_id===sceneId);
        if(!scene)continue;
        const attemptNumber=(scene.attempts?.length||0)+1;
        const route=resolveSceneProvider({state,scene,registry,env:this.env});
        const sceneCandidates=Array.isArray(scene.model_candidates)?scene.model_candidates:[];
        const seed=sceneSeed(scene,attemptNumber,now());

        if(!route.provider){
          // The route the control plane chose cannot run. The scene fails with that reason
          // rather than being quietly re-routed somewhere it was never cleared for.
          state=markSceneSubmitted(state,{sceneId,provider:route.id||'none',model:sceneCandidates[0]||'',jobId:'provider-route-unavailable',seed,submittedAt:new Date(now()).toISOString()});
          state=markSceneProviderResult(state,{sceneId,generation:null,error:route.error||'provider_adapter_unavailable',completedAt:new Date(now()).toISOString()});
          continue;
        }

        if(!rankedByProvider.has(route.id)){
          let ranked=[];
          if(route.provider.listModels){
            try{
              const listed=await route.provider.listModels();
              if(listed?.ok)ranked=rankImageModels({models:listed.models||[],preferredModels:state.preferred_models||state.model_candidates||[],history:modelHistory(state),limit:8});
            }catch{ranked=[];}
          }
          rankedByProvider.set(route.id,ranked);
        }
        const ranked=rankedByProvider.get(route.id)||[];
        const selectedModel=sceneCandidates.find(name=>ranked.some(item=>item.name===name))
          ||sceneCandidates[0]
          ||ranked[0]?.name
          ||null;
        const dims=scene.dimensions||{};
        // A planned repair edits the image the previous attempt produced, so the scene the
        // provider sees names the repair task and carries that image as its source.
        const repair=scene.pending_repair||null;
        const repairSource=repair?.sourceRef?await this.storage.get(repair.sourceRef):null;
        const executedScene=repair&&repairSource
          ?{...scene,task_type:repair.action==='GLOBAL_EDIT'?'IMAGE_EDIT_GLOBAL':'TARGETED_REPAIR',source_image:{id:'previous-render',bytes:repairSource.bytes}}
          :scene;
        let submitted;
        try{
          submitted=await route.provider.submit({
            sceneId,
            attempt:attemptNumber,
            scene:executedScene,
            taskType:executedScene.task_type||null,
            prompt:scene.compiled_prompt||scene.original_prompt||'',
            negativePrompt:scene.negative_prompt||'',
            width:Number(dims.width||512),
            height:Number(dims.height||512),
            steps:Number(scene.steps||20),
            strength:scene.strength,
            n:1,
            seed,
            models:selectedModel?[selectedModel]:[],
          });
        }catch{submitted={ok:false,error:'provider_submit_failed'};}

        if(!submitted?.ok||!submitted?.jobId){
          state=markSceneSubmitted(state,{sceneId,provider:route.id,model:selectedModel||'',jobId:'provider-submit-failed',seed,submittedAt:new Date(now()).toISOString()});
          state=markSceneProviderResult(state,{sceneId,generation:null,error:submitted?.error||'provider_submit_failed',completedAt:new Date(now()).toISOString()});
          // An exhausted free allocation is a wait, not a defect. It is recorded so the
          // logical job can say so instead of reporting a failed render.
          if(submitted?.waitState)state.wait_state=String(submitted.waitState);
          // Reference-bound work whose reference-safe runtime rejected every model it has
          // is not a bad scene: the runtime is not there. Saying so is the honest answer,
          // and it is the one that keeps the reference rather than re-rolling without it.
          else if(sceneIsReferenceBound(scene)&&submitted?.error==='provider_request_failed')state.wait_state='WAITING_FOR_SAFE_FREE_RUNTIME';
          if(submitted?.diagnostic)state.scenes.find(item=>item.scene_id===sceneId).provider_diagnostic=clone(submitted.diagnostic);
          continue;
        }

        state=markSceneSubmitted(state,{sceneId,provider:route.id,model:submitted.model||selectedModel||'',jobId:submitted.jobId,seed,submittedAt:new Date(now()).toISOString()});
        if(repair&&repairSource){
          const live=state.scenes.find(item=>item.scene_id===sceneId);
          live.attempts.at(-1).repair={action:repair.action,reason:repair.reason,target:repair.target};
          delete live.pending_repair;
        }

        // A synchronous runtime already has the image. Holding it for a poll that will
        // never come would strand the scene, so it is settled on the spot.
        if(submitted.synchronous&&submitted.generation){
          const {generation,bytes}=await this.storeGeneration(sceneId,attemptNumber,submitted.generation);
          state=markSceneProviderResult(state,{sceneId,generation,completedAt:new Date(now()).toISOString()});
          state=await this.settleQuality(state,sceneId,generation,bytes,qualityEvaluator,route.provider.capabilities||{});
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
