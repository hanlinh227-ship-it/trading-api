import {sanitizeDataClass} from './model-mesh/contracts.js';
import {callTinyFish} from './evidence/tinyfish-client.js';
import {checkTinyFishGuard,recordTinyFishGuard} from './evidence/tinyfish-guard.js';
import {readJsonBounded} from './model-mesh/providers/response.js';
import {timingSafeToken} from './model-mesh/auth.js';
import {collectSecretValues,redactCredentials,PROVIDER_SECRET_NAMES} from './security/secret-scan.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

export function createBrainEvidenceHandler({routeSkill,fetchImpl=fetch}={}){
  if(typeof routeSkill!=='function')throw new Error('BRAIN_EVIDENCE_ROUTE_REQUIRED');
  return async function handleBrainEvidence(request,env={}){
    const url=new URL(request.url);if(!url.pathname.startsWith('/brain/evidence/'))return null;
    if(url.pathname==='/brain/evidence/health'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      return json({
        ok:true,provider:'tinyfish',mode:'FREE_ONLY',
        configured:Boolean(env.TINY_FISH_API),
        admissionControlConfigured:Boolean(env.TINYFISH_CIRCUIT),
        allowedOperations:['search','fetch'],
        // TinyFish is an OPTIONAL evidence capability. The Brain and the Model
        // Mesh are fully operational without it; nothing in /brain/route,
        // /brain/health or /brain/mesh/* reads this provider.
        optional:true,
        hardDependency:false,
        degradesTo:'no_external_evidence',
        routingAuthority:false,reasoningAuthority:false,
      });
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
    // Not configured is an explicit, cheap, OPTIONAL-capability answer -- never
    // an attempt to reach a provider without a credential.
    if(!env.TINY_FISH_API)return json({ok:false,error:'evidence_provider_not_configured',provider:'tinyfish',mode:'FREE_ONLY',optional:true,hardDependency:false,routingAuthority:false,reasoningAuthority:false},503);

    // Admission control is required BEFORE any external call: without it we
    // cannot bound cost or request rate, so this stays fail-closed.
    const guard=await checkTinyFishGuard(env.TINYFISH_CIRCUIT);if(!guard.allowed)return json({ok:false,error:'tinyfish_guard_blocked',guardState:guard.state,retryAfterMs:guard.retryAfterMs,optional:true,hardDependency:false},429);

    const result=await callTinyFish({operation,query:body.text,urls:body.urls,apiKey:env.TINY_FISH_API,fetchImpl});

    // Bookkeeping AFTER a completed call is not a correctness precondition: the
    // request is already spent and the evidence already in hand. Failing to
    // record the circuit transition must degrade the guard, not discard good
    // evidence (the call has been made either way, so throwing the result away
    // buys no safety and costs a retry that spends quota again).
    const recorded=await recordTinyFishGuard(env.TINYFISH_CIRCUIT,result);

    const secretValues=collectSecretValues(env,PROVIDER_SECRET_NAMES);
    const evidence=(result.evidence||[]).map(row=>({...row,title:redactCredentials(row.title,{secretValues}),snippet:redactCredentials(row.snippet,{secretValues})}));

    return json({
      ok:result.ok,provider:'tinyfish',mode:'FREE_ONLY',operation,
      status:result.status,category:result.category,attempts:result.attempts,evidence,
      optional:true,hardDependency:false,
      guardStatePersisted:Boolean(recorded.persisted),
      route:{profile:route.profile,primarySkill:route.primarySkill,externalRoutingCalls:0},
      routingAuthority:false,reasoningAuthority:false,
    },result.ok?200:503);
  };
}
