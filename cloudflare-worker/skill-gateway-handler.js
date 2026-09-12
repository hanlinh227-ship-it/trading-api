import {routeSkillRequest} from './skill-gateway.js';

const MAX_BODY_BYTES=64_000;
const encoder=new TextEncoder();
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

async function readBody(request){
  const declared=Number(request.headers.get('content-length')||0);
  if(Number.isFinite(declared)&&declared>MAX_BODY_BYTES)throw new Error('body_too_large');
  const text=await request.text();
  if(encoder.encode(text).byteLength>MAX_BODY_BYTES)throw new Error('body_too_large');
  const value=JSON.parse(text);
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('invalid_body');
  const keys=Object.keys(value);
  if(keys.length!==1||keys[0]!=='text')throw new Error('invalid_body');
  if(typeof value.text!=='string'||value.text.trim().length<1||value.text.length>32_000)throw new Error('invalid_text');
  return value;
}

function capsuleView(route){
  const capsule=route.capsule;
  return {
    skillId:capsule.skill_id,
    domain:capsule.domain,
    outputContract:capsule.output_contract,
    capsuleHash:capsule.capsule_hash,
    permissions:Array.isArray(capsule.permissions)?capsule.permissions:[],
    riskCeiling:capsule.risk_ceiling,
    responseChecks:Array.isArray(capsule.response_checks)?capsule.response_checks:[],
  };
}

export function createSkillGatewayHandler({snapshot,router=routeSkillRequest,freshGitContext=true,lastKnownGood=true}={}){
  if(!snapshot||snapshot.schema_version!==1)throw new Error('skill_gateway_snapshot_required');
  return async function handleSkillGateway(request){
    const url=new URL(request.url);
    if(!['/brain/route','/brain/health'].includes(url.pathname))return null;
    if(url.pathname==='/brain/health'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      return json({
        ok:true,
        service:'skill-mandatory-fast-gateway',
        schemaVersion:snapshot.schema_version,
        sourceSha:snapshot.source_sha,
        releaseId:snapshot.release_id||null,
        freshGitContext:Boolean(freshGitContext),
        lastKnownGood:Boolean(lastKnownGood),
        fallbackPrimarySkill:snapshot.fallback_primary_skill,
        primarySkillRequired:true,
        executionCapsuleRequired:true,
        externalRoutingCalls:0,
      });
    }
    if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
    let input;
    try{input=await readBody(request);}catch(error){
      return json({ok:false,error:String(error?.message||error)==='body_too_large'?'body_too_large':'invalid_brain_route_request'},String(error?.message||error)==='body_too_large'?413:400);
    }
    try{
      const route=router({text:input.text},snapshot);
      return json({
        ok:true,
        profile:route.profile,
        domain:route.domain,
        primarySkill:route.primarySkill,
        supportingSkills:route.supportingSkills,
        capsule:capsuleView(route),
        requiresFreshState:route.requiresFreshState,
        requiresAuthority:route.requiresAuthority,
        toolRequirement:route.toolRequirement,
        sourceSha:route.sourceSha,
        routeLatencyMs:route.routeLatencyMs,
        externalRoutingCalls:0,
        qualityGate:{primarySkillPresent:true,capsulePresent:true,routeValid:true},
      });
    }catch(error){
      return json({ok:false,error:'brain_route_failed',detail:String(error?.message||error).slice(0,160)},500);
    }
  };
}
