export const IMAGE_BATCH_MAX_SCENES=100;
export const IMAGE_BATCH_DEFAULT_CONCURRENCY=4;
export const IMAGE_BATCH_MAX_CONCURRENCY=8;
export const IMAGE_BATCH_MAX_ATTEMPTS=3;

const nonEmpty=value=>typeof value==='string'&&value.trim().length>0;
const list=value=>Array.isArray(value)?value:[];
const object=value=>value&&typeof value==='object'&&!Array.isArray(value)?value:{};

export function validateImageBatchRequest(body={}){
  if(body?.dataClass===undefined||body?.dataClass===null||String(body.dataClass).trim()==='')return {ok:false,status:400,error:'data_class_required'};
  if(String(body.dataClass)!=='PUBLIC')return {ok:false,status:403,error:'ai_horde_public_data_only'};
  if(body.referenceImages!==undefined||body.sourceImage!==undefined)return {ok:false,status:409,error:'reference_images_not_enabled_for_volunteer_provider'};
  const scenes=list(body.scenes);
  if(!scenes.length)return {ok:false,status:400,error:'batch_scenes_required'};
  if(scenes.length>IMAGE_BATCH_MAX_SCENES)return {ok:false,status:413,error:'batch_scene_limit_exceeded'};
  if(scenes.some(scene=>!nonEmpty(scene?.prompt)))return {ok:false,status:400,error:'invalid_scene_prompt'};
  const concurrency=Math.min(IMAGE_BATCH_MAX_CONCURRENCY,Math.max(1,Number(body?.schedulerConfig?.concurrency)||IMAGE_BATCH_DEFAULT_CONCURRENCY));
  const maxAttempts=Math.min(IMAGE_BATCH_MAX_ATTEMPTS,Math.max(1,Number(body?.retryPolicy?.maxAttempts)||IMAGE_BATCH_MAX_ATTEMPTS));
  return {ok:true,request:{
    ...body,
    dataClass:'PUBLIC',
    qualityMode:body.qualityMode==='STRUCTURAL'?'STRUCTURAL':'STRICT',
    consistencyMode:body.consistencyMode==='FLEXIBLE'?'FLEXIBLE':'STRICT',
    globalConstraints:list(body.globalConstraints).map(String).filter(Boolean),
    sharedCharacterState:object(body.sharedCharacterState),
    sharedStyleState:object(body.sharedStyleState),
    scenes:scenes.map((scene,index)=>({...scene,sceneId:String(scene.sceneId||index+1)})),
    schedulerConfig:{...object(body.schedulerConfig),concurrency},
    retryPolicy:{...object(body.retryPolicy),maxAttempts},
  }};
}

export function createRenderManifest(request,{batchId,createdAt}={}){
  const created=String(createdAt||new Date().toISOString());
  const id=String(batchId||'').trim();
  if(!id)throw new Error('batch_id_required');
  return {
    batch_id:id,
    created_at:created,
    data_class:'PUBLIC',
    user_instruction:String(request?.userInstruction||''),
    quality_mode:request?.qualityMode==='STRUCTURAL'?'STRUCTURAL':'STRICT',
    consistency_mode:request?.consistencyMode==='FLEXIBLE'?'FLEXIBLE':'STRICT',
    output_format:String(request?.outputFormat||'webp'),
    global_constraints:list(request?.globalConstraints).map(String).filter(Boolean),
    shared_character_state:object(request?.sharedCharacterState),
    shared_style_state:object(request?.sharedStyleState),
    scheduler_config:{concurrency:Number(request?.schedulerConfig?.concurrency)||IMAGE_BATCH_DEFAULT_CONCURRENCY},
    retry_policy:{maxAttempts:Number(request?.retryPolicy?.maxAttempts)||IMAGE_BATCH_MAX_ATTEMPTS},
    qa_policy:object(request?.qaPolicy),
    scenes:list(request?.scenes).map((scene,index)=>({
      scene_id:String(scene.sceneId||index+1),
      original_prompt:String(scene.prompt||'').trim(),
      compiled_prompt:'',
      negative_prompt:String(scene.negativePrompt||''),
      dimensions:{width:Number(scene.width||request?.width||512),height:Number(scene.height||request?.height||512)},
      aspect_ratio:String(scene.aspectRatio||request?.aspectRatio||''),
      seed_strategy:scene.seed??null,
      model_candidates:list(scene.models||request?.models).map(String).filter(Boolean),
      expected_subject_count:scene.expectedSubjectCount??null,
      locked_identity_facts:list(scene.lockedIdentityFacts).map(String).filter(Boolean),
      locked_wardrobe_facts:list(scene.lockedWardrobeFacts).map(String).filter(Boolean),
      locked_environment_facts:list(scene.lockedEnvironmentFacts).map(String).filter(Boolean),
      camera_constraints:list(scene.cameraConstraints).map(String).filter(Boolean),
      continuity_inputs:object(scene.continuityInputs),
      status:'queued',
      attempts:[],
    })),
  };
}
