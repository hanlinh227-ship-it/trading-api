import {sanitizeDataClass} from './model-mesh/contracts.js';
import {callTinyFish} from './evidence/tinyfish-client.js';
import {checkTinyFishGuard,recordTinyFishGuard} from './evidence/tinyfish-guard.js';
import {readJsonBounded} from './model-mesh/providers/response.js';
import {timingSafeToken} from './model-mesh/auth.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

export function createBrainEvidenceHandler({routeSkill,fetchImpl=fetch}={}){
  if(typeof routeSkill!=='function')throw new Error('BRAIN_EVIDENCE_ROUTE_REQUIRED');
  return async function handleBrainEvidence(request,env={}){
    const url=new URL(request.url);if(!url.pathname.startsWith('/brain/evidence/'))return null;
    if(url.pathname==='/brain/evidence/health'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      return json({ok:true,provider:'tinyfish',mode:'FREE_ONLY',configured:Boolean(env.TINY_FISH_API),admissionControlConfigured:Boolean(env.TINYFISH_CIRCUIT),allowedOperations:['search','fetch'],routingAuthority:false,reasoningAuthority:false});
    }
    if(!['/brain/evidence/query','/brain/evidence/probe'].includes(url.pathname))return null;
    if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
    if(!await timingSafeToken(String(env?.MODEL_MESH_EXECUTION_TOKEN||''),String(request.headers.get('x-model-mesh-token')||'')))return json({ok:false,error:'unauthorized'},401);
    if(Number(request.headers.get('content-length')||0)>32768)return json({ok:false,error:'request_too_large'},413);
    let body;try{body=await readJsonBounded(request,32768);}catch{return json({ok:false,error:'invalid_or_oversize_json'},400);}
    if(typeof body?.text!=='string'||!body.text.trim()||body.text.length>500)return json({ok:false,error:'invalid_text'},400);
    const dataClass=sanitizeDataClass(body.dataClass);if(dataClass==='SECRET')return json({ok:false,error:'secret_external_evidence_forbidden'},403);
    const route=routeSkill({text:body.text});if(route.profile==='FAST')return json({ok:false,error:'fast_external_evidence_forbidden'},409);
    const operation=url.pathname.endsWith('/probe')?'search':String(body.operation||'search').toLowerCase();
    if(!['search','fetch'].includes(operation))return json({ok:false,error:'tinyfish_paid_or_unknown_operation_forbidden'},400);
    const guard=await checkTinyFishGuard(env.TINYFISH_CIRCUIT);if(!guard.allowed)return json({ok:false,error:'tinyfish_guard_blocked',guardState:guard.state,retryAfterMs:guard.retryAfterMs},429);
    const result=await callTinyFish({operation,query:body.text,urls:body.urls,apiKey:env.TINY_FISH_API,fetchImpl});
    await recordTinyFishGuard(env.TINYFISH_CIRCUIT,result);
    return json({ok:result.ok,provider:'tinyfish',mode:'FREE_ONLY',operation,status:result.status,category:result.category,attempts:result.attempts,evidence:result.evidence,route:{profile:route.profile,primarySkill:route.primarySkill,externalRoutingCalls:0},routingAuthority:false,reasoningAuthority:false},result.ok?200:503);
  };
}
