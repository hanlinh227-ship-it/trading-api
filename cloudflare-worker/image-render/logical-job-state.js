import {applyLogicalJobEvent,cancelLogicalJob,createLogicalJob,nextLogicalJobActions,retryLogicalJobScenes} from './logical-job-engine.js';
import {cancelImageBatch,createImageBatch,getImageBatchStatus} from './batch-client.js';

const STATE_KEY='image-logical-job-state-v3';
const TERMINAL=new Set(['complete','complete_with_failures','cancelled']);
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8'}});
const clone=value=>structuredClone(value);

function v2Eligible(scene){
  const intent=scene?.intent||{};
  return intent.privacyClass==='PUBLIC'&&Array.isArray(intent.referenceAssets)&&intent.referenceAssets.length===0&&['TEXT_TO_IMAGE','MULTI_SCENE_BATCH'].includes(intent.taskType);
}

function physicalManifest(state,chunk){
  const selected=chunk.sceneIds.map(id=>state.scenes.find(scene=>scene.id===id)).filter(Boolean);
  const strict=selected.some(scene=>scene.intent?.qualityProfile!=='STRUCTURAL');
  return {
    batch_id:`${state.jobId}-${chunk.id}`,
    data_class:'PUBLIC',
    quality_mode:strict?'STRICT':'STRUCTURAL',
    scheduler_config:{concurrency:4},
    retry_policy:{maxAttempts:3},
    preferred_models:[],
    scenes:selected.map(scene=>({
      scene_id:scene.id,
      status:'queued',
      attempts:[],
      compiled_prompt:String(scene.intent?.promptCompiled||scene.prompt||''),
      negative_prompt:Array.isArray(scene.intent?.negativeConstraints)?scene.intent.negativeConstraints.join(', '):'',
      dimensions:{width:Number(scene.intent?.target?.width||512),height:Number(scene.intent?.target?.height||512)},
    })),
  };
}

function mapPhysicalStatus(status){
  if(status==='complete')return 'complete';
  if(status==='complete_unverified')return 'complete_unverified';
  if(status==='failed_quality')return 'failed_quality';
  if(['failed_provider','failed'].includes(status))return 'failed_provider';
  return 'provider_processing';
}

export function createImageLogicalJobClass({
  batchClient={createImageBatch,getImageBatchStatus,cancelImageBatch},
  now=()=>Date.now(),
}={}){
  return class ImageLogicalJobState{
    constructor(state,env){this.storage=state.storage;this.env=env||{};}
    async load(){return await this.storage.get(STATE_KEY);}
    async save(state){await this.storage.put(STATE_KEY,state);return state;}
    async schedule(seconds=2){if(typeof this.storage.setAlarm==='function')await this.storage.setAlarm(now()+Math.max(2000,Number(seconds||2)*1000));}
    async clearAlarm(){if(typeof this.storage.deleteAlarm==='function')await this.storage.deleteAlarm();}
    response(state,status=200){return json({ok:true,state,summary:{jobId:state.jobId,status:state.status,sceneCount:state.sceneCount,completeScenes:state.scenes.filter(scene=>['complete','complete_unverified'].includes(scene.status)).length,failedScenes:state.scenes.filter(scene=>['failed_quality','failed_provider'].includes(scene.status)).length,chunks:state.chunks.length}},status);}

    async fetch(request){
      const url=new URL(request.url);
      if(url.pathname==='/create'&&request.method==='POST'){
        let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
        let state;try{state=createLogicalJob({jobId:body?.jobId,scenes:body?.scenes,chunkSize:body?.chunkSize??100});}catch(error){return json({ok:false,error:String(error?.message||error)},400);}
        await this.save(state);await this.schedule(2);return this.response(state,201);
      }
      if(url.pathname==='/status'&&request.method==='GET'){
        const state=await this.load();return state?this.response(state):json({ok:false,error:'image_logical_job_not_found'},404);
      }
      if(url.pathname==='/cancel'&&request.method==='DELETE'){
        let state=await this.load();if(!state)return json({ok:false,error:'image_logical_job_not_found'},404);
        for(const chunk of state.chunks){if(chunk.physicalBatchId)await Promise.resolve(batchClient.cancelImageBatch(this.env,chunk.physicalBatchId)).catch(()=>null);}
        state=cancelLogicalJob(state);await this.save(state);await this.clearAlarm();return this.response(state);
      }
      if(url.pathname==='/retry'&&request.method==='POST'){
        let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
        let state=await this.load();if(!state)return json({ok:false,error:'image_logical_job_not_found'},404);
        const ids=Array.isArray(body?.sceneIds)?body.sceneIds.map(String).filter(Boolean):[];
        state=retryLogicalJobScenes(state,ids);
        const selected=new Set(ids);
        for(const chunk of state.chunks){if(chunk.sceneIds.some(id=>selected.has(id))){chunk.status='queued';delete chunk.physicalBatchId;}}
        await this.save(state);await this.schedule(2);return this.response(state);
      }
      if(url.pathname==='/tick'&&request.method==='POST'){
        const state=await this.cycle();return state?this.response(state):json({ok:false,error:'image_logical_job_not_found'},404);
      }
      return json({ok:false,error:'not_found'},404);
    }

    async alarm(){await this.cycle();}

    async cycle(){
      let state=await this.load();if(!state)return null;
      if(TERMINAL.has(state.status)){await this.clearAlarm();return state;}

      for(const snapshot of state.chunks.filter(chunk=>chunk.status==='submitted'&&chunk.physicalBatchId)){
        let result;try{result=await batchClient.getImageBatchStatus(this.env,snapshot.physicalBatchId);}catch{result={ok:false};}
        if(!result?.ok){state.status='waiting_for_free_compute';await this.save(state);await this.schedule(10);return state;}
        for(const physicalScene of result?.state?.scenes||[]){
          const logical=state.scenes.find(scene=>scene.id===physicalScene.scene_id);if(!logical)continue;
          const mapped=mapPhysicalStatus(physicalScene.status);
          if(logical.status!==mapped)state=applyLogicalJobEvent(state,{type:'SCENE_STATUS',sceneId:logical.id,status:mapped});
        }
        const physicalStatus=result?.summary?.status;
        const chunk=state.chunks.find(item=>item.id===snapshot.id);
        if(chunk&&['complete','complete_with_failures','cancelled','failed'].includes(physicalStatus))chunk.status=physicalStatus;
      }

      if(state.status==='waiting_for_free_compute')state=applyLogicalJobEvent(state,{type:'RESUME'});
      const actions=nextLogicalJobActions(state,{maxChunks:1});
      if(actions.length){
        const action=actions[0];
        const chunk=state.chunks.find(item=>item.id===action.chunkId);
        const selected=action.sceneIds.map(id=>state.scenes.find(scene=>scene.id===id)).filter(Boolean);
        if(!selected.every(v2Eligible)){
          state=applyLogicalJobEvent(state,{type:'WAITING_FOR_SAFE_FREE_RUNTIME'});
          await this.save(state);await this.schedule(30);return state;
        }
        const manifest=physicalManifest(state,chunk);
        let created;try{created=await batchClient.createImageBatch(this.env,manifest.batch_id,manifest);}catch{created={ok:false};}
        if(!created?.ok){
          state=applyLogicalJobEvent(state,{type:'WAITING_FOR_FREE_COMPUTE'});
          await this.save(state);await this.schedule(10);return state;
        }
        chunk.status='submitted';chunk.physicalBatchId=manifest.batch_id;
        for(const sceneId of action.sceneIds)state=applyLogicalJobEvent(state,{type:'SCENE_STATUS',sceneId,status:'provider_processing'});
      }

      await this.save(state);
      if(TERMINAL.has(state.status))await this.clearAlarm();else await this.schedule(2);
      return state;
    }
  };
}

export const ImageLogicalJobState=createImageLogicalJobClass();
