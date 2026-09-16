const TASKS=new Set([
  'TEXT_TO_IMAGE','REFERENCE_GENERATION','IMAGE_EDIT_GLOBAL','IMAGE_EDIT_LOCAL','INPAINT','OUTPAINT',
  'BACKGROUND_REPLACE','STYLE_TRANSFER','OBJECT_REPLACE','TEXT_RENDER_EDIT','MULTI_IMAGE_COMPOSE',
  'CHARACTER_CONSISTENCY','PRODUCT_CONSISTENCY','MULTI_SCENE_BATCH','TARGETED_REPAIR',
]);
const PRIVACY=new Set(['PUBLIC','INTERNAL','CONFIDENTIAL','SECRET']);
const QUALITY=new Set(['STRUCTURAL','STRICT','STRICT_VISUAL']);
const asList=value=>Array.isArray(value)?value.map(v=>String(v).trim()).filter(Boolean):[];
const cleanObject=value=>value&&typeof value==='object'&&!Array.isArray(value)?value:null;
const unique=list=>[...new Set(list)];

function normalizeTask(value){
  const task=String(value||'TEXT_TO_IMAGE').trim().toUpperCase();
  if(!TASKS.has(task))throw new Error('unsupported_image_task');
  return task;
}

function normalizePrivacy(value){
  const privacy=String(value||'').trim().toUpperCase();
  if(!PRIVACY.has(privacy))throw new Error('invalid_privacy_class');
  return privacy;
}

function aspectRatio(width,height){
  const gcd=(a,b)=>b?gcd(b,a%b):a;
  const d=gcd(width,height);
  return `${width/d}:${height/d}`;
}

export function compileImageIntent(input={}){
  const prompt=String(input.prompt??input.promptOriginal??'').trim();
  if(!prompt)throw new Error('invalid_prompt');
  const taskType=normalizeTask(input.taskType);
  const privacyClass=normalizePrivacy(input.dataClass??input.privacyClass);
  const subjectCount=input.subjectCount===undefined?null:Number(input.subjectCount);
  if(subjectCount!==null&&(!Number.isInteger(subjectCount)||subjectCount<1))throw new Error('invalid_subject_count');

  const refs=[];
  if(Array.isArray(input.referenceAssets))refs.push(...input.referenceAssets.filter(Boolean));
  if(cleanObject(input.sourceImage))refs.push(input.sourceImage);
  if(['REFERENCE_GENERATION','CHARACTER_CONSISTENCY','PRODUCT_CONSISTENCY'].includes(taskType)&&refs.length===0)throw new Error('reference_assets_required');
  if(taskType.startsWith('IMAGE_EDIT')&&refs.length===0)throw new Error('source_image_required');

  const explicit=cleanObject(input.explicit)||{};
  const width=Number(input.width??input.target?.width??1024);
  const height=Number(input.height??input.target?.height??1024);
  if(!Number.isInteger(width)||!Number.isInteger(height)||width<=0||height<=0)throw new Error('invalid_target_dimensions');

  const destructiveDefault=['TEXT_TO_IMAGE','REFERENCE_GENERATION','STYLE_TRANSFER','MULTI_IMAGE_COMPOSE'].includes(taskType);
  const destructiveRedrawAllowed=input.destructiveRedrawAllowed===undefined?destructiveDefault:Boolean(input.destructiveRedrawAllowed);

  return {
    contractVersion:'image_intent_v3',
    taskType,
    promptOriginal:prompt,
    promptCompiled:String(input.promptCompiled||prompt).trim(),
    negativeConstraints:asList(input.negativeConstraints),
    subjectCount,
    subjectIdentityConstraints:asList(explicit.subjectIdentityConstraints??input.subjectIdentityConstraints),
    referenceAssets:refs.map(ref=>({...ref})),
    preserveRegions:unique(asList(input.preserveRegions)),
    editableRegions:unique(asList(input.editableRegions)),
    wardrobeConstraints:asList(explicit.wardrobeConstraints??input.wardrobeConstraints),
    propConstraints:asList(explicit.propConstraints??input.propConstraints),
    backgroundConstraints:asList(explicit.backgroundConstraints??input.backgroundConstraints),
    styleConstraints:asList(explicit.styleConstraints??input.styleConstraints),
    cameraConstraints:asList(explicit.cameraConstraints??input.cameraConstraints),
    compositionConstraints:asList(explicit.compositionConstraints??input.compositionConstraints),
    textRenderConstraints:asList(explicit.textRenderConstraints??input.textRenderConstraints),
    continuityConstraints:asList(explicit.continuityConstraints??input.continuityConstraints),
    target:{width,height,aspectRatio:String(input.aspectRatio||aspectRatio(width,height))},
    privacyClass,
    qualityProfile:QUALITY.has(String(input.qualityProfile||'STRICT').toUpperCase())?String(input.qualityProfile||'STRICT').toUpperCase():'STRICT',
    destructiveRedrawAllowed,
  };
}

export function validateImageIntent(intent={}){
  const errors=[];
  if(intent.contractVersion!=='image_intent_v3')errors.push('invalid_contract_version');
  if(!TASKS.has(intent.taskType))errors.push('unsupported_image_task');
  if(!String(intent.promptOriginal||'').trim())errors.push('invalid_prompt');
  if(!PRIVACY.has(intent.privacyClass))errors.push('invalid_privacy_class');
  if(intent.subjectCount!==null&&(!Number.isInteger(intent.subjectCount)||intent.subjectCount<1))errors.push('invalid_subject_count');
  const preserve=new Set(asList(intent.preserveRegions));
  const editable=asList(intent.editableRegions);
  if(editable.some(region=>preserve.has(region)))errors.push('preserve_edit_region_conflict');
  const needsReference=['REFERENCE_GENERATION','CHARACTER_CONSISTENCY','PRODUCT_CONSISTENCY','IMAGE_EDIT_GLOBAL','IMAGE_EDIT_LOCAL'].includes(intent.taskType);
  if(needsReference&&(!Array.isArray(intent.referenceAssets)||intent.referenceAssets.length===0))errors.push('reference_assets_required');
  if(!intent.target||!Number.isInteger(intent.target.width)||!Number.isInteger(intent.target.height)||intent.target.width<=0||intent.target.height<=0)errors.push('invalid_target_dimensions');
  return {ok:errors.length===0,errors};
}

export const IMAGE_INTENT_TASKS=Object.freeze([...TASKS]);
