const flattenState=state=>Object.entries(state||{}).flatMap(([name,facts])=>{
  const values=Array.isArray(facts)?facts:[facts];
  return values.filter(v=>v!==undefined&&v!==null&&String(v).trim()).map(v=>`${name}: ${String(v).trim()}`);
});
const lines=(label,items)=>items.length?`${label}: ${items.join('; ')}`:'';

export function compileScenePrompt(scene,manifest){
  const identityFacts=[...flattenState(manifest?.shared_character_state),...(scene?.locked_identity_facts||[])];
  const wardrobeFacts=[...(scene?.locked_wardrobe_facts||[])];
  const environmentFacts=[...(scene?.locked_environment_facts||[])];
  const globalConstraints=[...(manifest?.global_constraints||[])];
  const cameraConstraints=[...(scene?.camera_constraints||[])];
  const styleFacts=flattenState(manifest?.shared_style_state);
  const promptParts=[
    String(scene?.original_prompt||'').trim(),
    lines('CHARACTER LOCK',identityFacts),
    lines('WARDROBE LOCK',wardrobeFacts),
    lines('ENVIRONMENT LOCK',environmentFacts),
    lines('STYLE LOCK',styleFacts),
    lines('CAMERA CONSTRAINTS',cameraConstraints),
    lines('GLOBAL CONSTRAINTS',globalConstraints),
  ].filter(Boolean);
  const negative=[String(scene?.negative_prompt||'').trim(),'duplicate character','extra limbs','deformed anatomy','unrequested text','watermark'].filter(Boolean);
  return {
    prompt:promptParts.join('\n'),
    negativePrompt:[...new Set(negative)].join(', '),
    locks:{
      consistencyMode:String(manifest?.consistency_mode||'STRICT'),
      identityFacts,
      wardrobeFacts,
      environmentFacts,
      cameraConstraints,
      globalConstraints,
    },
  };
}
