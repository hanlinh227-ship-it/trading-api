import {routeSkillRequest} from './skill-gateway.js';

const MAX_BODY_BYTES=64_000;
const encoder=new TextEncoder();
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

async function parseBody(request){
  const declared=Number(request.headers.get('content-length')||0);
  if(Number.isFinite(declared)&&declared>MAX_BODY_BYTES)throw new Error('body_too_large');
  const text=await request.text();
  if(encoder.encode(text).byteLength>MAX_BODY_BYTES)throw new Error('body_too_large');
  const value=JSON.parse(text);
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('invalid_body');
  if(Object.keys(value).some(key=>key!=='text'))throw new Error('invalid_field');
  if(typeof value.text!=='string'||value.text.trim().length<1||value.text.length>20_000)throw new Error('invalid_text');
  return {text:value.text};
}

function publicCapsule(capsule){
  return {
    skill_id:capsule.skill_id,
    domain:capsule.domain,
    output_contract:capsule.output_contract,
    permissions:Array.isArray(capsule.permissions)?capsule.permissions:[],
    risk_ceiling:capsule.risk_ceiling,
    capsule_hash:capsule.capsule_hash,
    tools:Array.isArray(capsule.tools)?capsule.tools:[],
    sources:Array.isArray(capsule.sources)?capsule.sources:[],
  };
}

export function createSkillGatewayHandler({snapshot}={}){
  if(!snapshot||snapshot.schema_version!==1)throw new Error('SKILL_GATEWAY_SNAPSHOT_REQUIRED');
  return async function handleSkillGateway(request){
    const url=new URL(request.url);
    if(!['/brain/health','/brain/route'].includes(url.pathname))return null;
    if(url.pathname==='/brain/health'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      return json({
        ok:true,
        service:'skill-mandatory-fast-gateway',
        sourceSha:snapshot.source_sha,
        releaseId:snapshot.release_id,
        schemaVersion:snapshot.schema_version,
        primarySkillRequired:true,
        capsuleRequired:true,
        fallbackPrimarySkill:snapshot.fallback_primary_skill,
        externalRoutingCalls:0,
        generatedAt:snapshot.generated_at,
      });
    }
    if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
    let input;
    try{input=await parseBody(request);}catch{return json({ok:false,error:'invalid_brain_route_request'},400);}
    let route;
    try{route=routeSkillRequest(input,snapshot);}catch(error){return json({ok:false,error:'brain_route_failed',detail:String(error?.message||error).slice(0,120)},503);}
    const capsule=snapshot.capsules[route.primarySkill];
    return json({ok:true,route,capsule:publicCapsule(capsule)});
  };
}
