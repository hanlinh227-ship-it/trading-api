import {buildModelMeshPlan} from './model-mesh-runtime.js';
import {sanitizeDataClass} from './model-mesh/contracts.js';
import {providerRuntimeStatus} from './model-mesh/runtime-health.js';
import {selectionCandidate,MODEL_MESH_LIMITS,MODEL_MESH_SELECTION_FILTERS} from './model-mesh/contracts.js';
import {timingSafeToken} from './model-mesh/auth.js';
import {scheduleSelfHeal} from './model-mesh/self-heal.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

export function createModelMeshHandler({skillSnapshot,modelSnapshot,routeSkill,executeWorkers=null,probeProviders=null}={}){
  if(!skillSnapshot||!modelSnapshot||typeof routeSkill!=='function')throw new Error('MODEL_MESH_HANDLER_CONFIG_REQUIRED');
  return async function handleModelMesh(request,env={},ctx={}){
    const url=new URL(request.url);
    if(!url.pathname.startsWith('/brain/mesh/'))return null;
    if(url.pathname==='/brain/mesh/health'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const providers=await providerRuntimeStatus(modelSnapshot,env);
      return json({
        ok:true,
        mode:'FREE_ONLY',
        sourceSha:modelSnapshot.source_sha,
        routingAuthority:false,
        reasoningAuthority:false,
        maxParallelStandard:MODEL_MESH_LIMITS.STANDARD,
        maxParallelDeep:MODEL_MESH_LIMITS.DEEP,
        maxParallelFast:MODEL_MESH_LIMITS.FAST,
        selectionFilters:MODEL_MESH_SELECTION_FILTERS,
        executionEnabled:String(env.MODEL_MESH_EXECUTION_ENABLED||'0')==='1',
        executionTokenConfigured:Boolean(env.MODEL_MESH_EXECUTION_TOKEN),
        eligibleModelCount:(modelSnapshot.models||[]).filter(model=>selectionCandidate(model)).length,
        configuredProviderCount:providers.filter(row=>row.configured).length,
        activeProviderCount:providers.filter(row=>row.active).length,
        providers,
      });
    }
    if(url.pathname==='/brain/mesh/probe'){
      if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
      const expected=String(env.MODEL_MESH_EXECUTION_TOKEN||'');
      const supplied=String(request.headers.get('x-model-mesh-token')||'');
      if(!await timingSafeToken(expected,supplied))return json({ok:false,error:'unauthorized'},401);
      if(typeof probeProviders!=='function')return json({ok:false,error:'mesh_probe_not_configured'},503);
      const result=await probeProviders(env,{modelSnapshot,ctx});
      return json(result);
    }
    if(url.pathname==='/brain/mesh/plan'){
      if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
      let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
      if(typeof body?.text!=='string'||!body.text.trim())return json({ok:false,error:'invalid_text'},400);
      const dataClass=sanitizeDataClass(body.dataClass);
      if(dataClass==='SECRET')return json({ok:false,error:'secret_external_mesh_forbidden'},403);
      const route=routeSkill({text:body.text});
      const plan=await buildModelMeshPlan({...body,dataClass,profile:route.profile,route},{skillSnapshot,modelSnapshot,env});
      // Graceful zero is a correct answer, but if it was caused by expired
      // evidence rather than by genuinely dead providers, the mesh must be able
      // to recover without waiting for the external refresh schedule.
      if(plan.selectionReason==='no_live_healthy_provider')scheduleSelfHeal({env,ctx,probeProviders,modelSnapshot});
      return json(plan);
    }
    if(url.pathname==='/brain/mesh/execute'){
      if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
      if(typeof executeWorkers!=='function')return json({ok:false,error:'mesh_execution_not_configured'},503);
      return executeWorkers(request,env,{skillSnapshot,modelSnapshot,routeSkill,ctx});
    }
    return null;
  };
}
