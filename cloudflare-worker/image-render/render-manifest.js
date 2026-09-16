export const IMAGE_BATCH_MAX_SCENES=100;
export const IMAGE_BATCH_DEFAULT_CONCURRENCY=4;
export const IMAGE_BATCH_MAX_CONCURRENCY=8;
export const IMAGE_BATCH_MAX_ATTEMPTS=3;
export const IMAGE_BATCH_MAX_PROMPT_CHARS=12000;
export const IMAGE_BATCH_MAX_NEGATIVE_PROMPT_CHARS=6000;

const asArray=value=>Array.isArray(value)?value:[];
const nonEmpty=value=>String(value??'').trim();
const boundedInt=(value,min,max,fallback)=>{
  const parsed=Number(value);
  if(!Number.isFinite(parsed))return fallback;
  return Math.min(max,Math.max(min,Math.round(parsed)));
};
const copyObject=value=>value&&typeof value==='object'&&!Array.isArray(value)?structuredClone(value):{};

function validateScene(scene,index){
  if(!scene||typeof scene!=='object'||Array.isArray(scene))return {ok:false,status:400,error:'invalid_scene'};
  const prompt=nonEmpty(scene.prompt);
  if(!prompt)return {ok:false,status:400,error:'invalid_scene_prompt'};
  if(prompt.length>IMAGE_BATCH_MAX_PROMPT_CHARS)return {ok:false,status:413,error:'scene_prompt_too_large'};
  const negative=String(scene.negativePrompt??'');
  if(negative.length>IMAGE_BATCH_MAX_NEGATIVE_PROMPT_CHARS)return {ok:false,status:413,error:'scene_negative_prompt_too_large'};
  return {ok:true,scene:{...structuredClone(scene),sceneId:nonEmpty(scene.sceneId)||String(index+1),prompt,negativePrompt:negative.trim()}};
}

export function validateImageBatchRequest(body={}){
  if(!body||typeof body!=='object'||Array.isArray(body))return {ok:false,status:400,error:'invalid_batch_request'};
  if(body.dataClass===undefined||body.dataClass===null||nonEmpty(body.dataClass)==='')return {ok:false,status:400,error:'data_class_required'};
  if(nonEmpty(body.dataClass)!=='PUBLIC')return {ok:false,status:403,error:'ai_horde_public_data_only'};
  if(body.referenceImages!==undefined||body.sourceImage!==undefined)return {ok:false,status:409,error:'reference_images_not_enabled_for_volunteer_provider'};
  const rawScenes=asArray(body.scenes);
  if(!rawScenes.length)return {ok:false,status:400,error:'batch_scenes_required'};
  if(rawScenes.length>IMAGE_BATCH_MAX_SCENES)return {ok:false,status:413,error:'batch_scene_limit_exceeded'};

  const scenes=[];const ids=new Set();
  for(let index=0;index<rawScenes.length;index+=1){
    const checked=validateScene(rawScenes[index],index);
    if(!checked.ok)return checked;
    if(ids.has(checked.scene.sceneId))return {ok:false,status:409,error:'duplicate_scene_id'};
    ids.add(checked.scene.sceneId);scenes.push(checked.scene);
  }

  const schedulerInput=copyObject(body.schedulerConfig);
  const retryInput=copyObject(body.retryPolicy);
  const qualityMode=['STRUCTURAL','STRICT'].includes(nonEmpty(body.qualityMode).toUpperCase())?nonEmpty(body.qualityMode).toUpperCase():'STRICT';
  const consistencyMode=nonEmpty(body.consistencyMode).toUpperCase()==='FLEXIBLE'?'FLEXIBLE':'STRICT';
  return {ok:true,request:{
    ...structuredClone(body),
    dataClass:'PUBLIC',
    qualityMode,
    consistencyMode,
    scenes,
    globalConstraints:asArray(body.globalConstraints).map(nonEmpty).filter(Boolean),
    sharedCharacterState:copyObject(body.sharedCharacterState),
    sharedStyleState:Array.isArray(body.sharedStyleState)?body.sharedStyleState.map(nonEmpty).filter(Boolean):copyObject(body.sharedStyleState),
    schedulerConfig:{...schedulerInput,concurrency:boundedInt(schedulerInput.concurrency,1,IMAGE_BATCH_MAX_CONCURRENCY,IMAGE_BATCH_DEFAULT_CONCURRENCY)},
    retryPolicy:{...retryInput,maxAttempts:boundedInt(retryInput.maxAttempts,1,IMAGE_BATCH_MAX_ATTEMPTS,IMAGE_BATCH_MAX_ATTEMPTS)},
  }};
}

export function createRenderManifest(request,{batchId,createdAt=new Date().toISOString()}={}){
  const id=nonEmpty(batchId);
  if(!id)throw new TypeError('batchId is required');
  if(!request||request.dataClass!=='PUBLIC'||!Array.isArray(request.scenes)||!request.scenes.length)throw new TypeError('validated batch request required');
  const created=nonEmpty(createdAt)||new Date().toISOString();
  const manifest={
    version:2,
    batch_id:id,
    created_at:created,
    data_class:'PUBLIC',
    quality_mode:request.qualityMode||'STRICT',
    consistency_mode:request.consistencyMode||'STRICT',
    output_format:nonEmpty(request.outputFormat)||'webp',
    user_instruction:nonEmpty(request.userInstruction),
    global_constraints:structuredClone(request.globalConstraints||[]),
    shared_character_state:structuredClone(request.sharedCharacterState||{}),
    shared_style_state:structuredClone(request.sharedStyleState||[]),
    scheduler_config:structuredClone(request.schedulerConfig||{concurrency:IMAGE_BATCH_DEFAULT_CONCURRENCY}),
    retry_policy:structuredClone(request.retryPolicy||{maxAttempts:IMAGE_BATCH_MAX_ATTEMPTS}),
    qa_policy:structuredClone(request.qaPolicy||{}),
    status:'queued',
    scenes:[],
  };
  manifest.scenes=request.scenes.map((scene,index)=>({
    scene_id:String(scene.sceneId||index+1),
    original_prompt:String(scene.prompt),
    compiled_prompt:null,
    negative_prompt:String(scene.negativePrompt||''),
    width:scene.width??request.width??null,
    height:scene.height??request.height??null,
    aspect_ratio:scene.aspectRatio??request.aspectRatio??null,
    seed_strategy:scene.seedStrategy??request.seedStrategy??'AUTO',
    model_candidates:Array.isArray(scene.modelCandidates)?structuredClone(scene.modelCandidates):[],
    expected_subject_count:scene.expectedSubjectCount??null,
    locked_identity_facts:structuredClone(scene.lockedIdentityFacts||{}),
    locked_wardrobe_facts:structuredClone(scene.lockedWardrobeFacts||{}),
    locked_environment_facts:structuredClone(scene.lockedEnvironmentFacts||{}),
    camera_constraints:structuredClone(scene.cameraConstraints||[]),
    continuity_inputs:structuredClone(scene.continuityInputs||{}),
    status:'queued',
    attempts:[],
  }));
  return manifest;
}
