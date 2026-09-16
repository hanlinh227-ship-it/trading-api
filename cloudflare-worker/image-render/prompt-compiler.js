const text=value=>String(value??'').trim();
const list=value=>Array.isArray(value)?value.map(text).filter(Boolean):[];

function flattenFacts(value,prefix=''){
  if(value===null||value===undefined)return [];
  if(Array.isArray(value))return value.flatMap(item=>flattenFacts(item,prefix));
  if(typeof value==='object')return Object.entries(value).flatMap(([key,item])=>flattenFacts(item,prefix?`${prefix}.${key}`:key));
  const fact=text(value);
  return fact?[prefix?`${prefix}: ${fact}`:fact]:[];
}

function uniqueParts(parts){
  const seen=new Set();const out=[];
  for(const part of parts.map(text).filter(Boolean)){
    const key=part.toLowerCase();
    if(seen.has(key))continue;
    seen.add(key);out.push(part);
  }
  return out;
}

export function compileScenePrompt(scene,manifest={}){
  if(!scene||typeof scene!=='object')throw new TypeError('scene is required');
  const original=text(scene.original_prompt||scene.prompt);
  if(!original)throw new TypeError('scene original prompt is required');

  const consistencyMode=text(manifest.consistency_mode||manifest.consistencyMode||'STRICT').toUpperCase()==='FLEXIBLE'?'FLEXIBLE':'STRICT';
  const globalConstraints=list(manifest.global_constraints||manifest.globalConstraints);
  const cameraConstraints=list(scene.camera_constraints||scene.cameraConstraints);
  const identityFacts=[
    ...flattenFacts(manifest.shared_character_state||manifest.sharedCharacterState,'character'),
    ...flattenFacts(scene.locked_identity_facts||scene.lockedIdentityFacts,'identity'),
    ...flattenFacts(scene.locked_wardrobe_facts||scene.lockedWardrobeFacts,'wardrobe'),
    ...flattenFacts(scene.locked_environment_facts||scene.lockedEnvironmentFacts,'environment'),
  ];
  const styleFacts=flattenFacts(manifest.shared_style_state||manifest.sharedStyleState,'style');

  const compiledParts=uniqueParts([
    original,
    ...identityFacts,
    ...styleFacts,
    ...globalConstraints,
    ...cameraConstraints,
    consistencyMode==='STRICT'?'continuity lock: preserve the same character identity, proportions, wardrobe, recurring props and world style unless this scene explicitly changes them':'continuity: preserve character identity while allowing requested scene variation',
    'anatomy guard: natural coherent anatomy, no duplicated body parts, no merged limbs',
    'subject-count guard: do not silently add or remove characters or major objects',
  ]);

  const negativeParts=uniqueParts([
    text(scene.negative_prompt||scene.negativePrompt),
    'duplicate character',
    'duplicate object',
    'extra limbs',
    'extra fingers',
    'deformed anatomy',
    'melted body',
    'identity drift',
    'wardrobe change unless explicitly requested',
    'unrequested text',
    'watermark',
    'logo',
  ]);

  const locks={
    consistencyMode,
    identityFacts,
    globalConstraints,
    cameraConstraints,
  };
  return {prompt:compiledParts.join('. '),negativePrompt:negativeParts.join(', '),locks};
}
