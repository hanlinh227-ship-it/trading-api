import {buildModelMeshPlan} from './model-mesh-runtime.js';
import {sanitizeDataClass} from './model-mesh/contracts.js';
import {providerConfigurationStatus} from './model-mesh/provider-client.js';

const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

export function createModelMeshHandler({skillSnapshot,modelSnapshot,routeSkill,executeWorkers=null,probeProviders=null}={}){
  if(!skillSnapshot||!modelSnapshot||typeof routeSkill!=='function')throw new Error('MODEL_MESH_HANDLER_CONFIG_REQUIRED');
  return async function handleModelMesh(request,env={}){
    const url=new URL(request.url);
    if(!url.pathname.startsWith('/brain/mesh/'))return null;
    if(url.pathname==='/brain/mesh/health'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const providers=providerConfigurationStatus(modelSnapshot,env);
      return json({
        ok:true,
        mode:'FREE_ONLY',
        sourceSha:modelSnapshot.source_sha,
        routingAuthority:false,
        reasoningAuthority:false,
        maxParallelStandard:2,
        maxParallelDeep:4,
        executionEnabled:String(env.MODEL_MESH_EXECUTION_ENABLED||'0')==='1',
        executionTokenConfigured:Boolean(env.MODEL_MESH_EXECUTION_TOKEN),
        eligibleModelCount:Array.isArray(modelSnapshot.models)?modelSnapshot.models.length:0,
        configuredProviderCount:providers.filter(row=>row.configured).length,
        activeProviderCount:providers.filter(row=>row.active).length,
        providers,
      });
    }
    if(url.pathname==='/brain/mesh/probe'){
      if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
      const expected=String(env.MODEL_MESH_EXECUTION_TOKEN||'');
      const supplied=String(request.headers.get('x-model-mesh-token')||'');
      if(!expected||!supplied||supplied!==expected)return json({ok:false,error:'unauthorized'},401);
      if(typeof probeProviders!=='function')return json({ok:false,error:'mesh_probe_not_configured'},503);
      const result=await probeProviders(env,{modelSnapshot});
      return json(result);
    }
    if(url.pathname==='/brain/mesh/plan'){
      if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
      let body;try{body=await request.json();}catch{return json({ok:false,error:'invalid_json'},400);}
      if(typeof body?.text!=='string'||!body.text.trim())return json({ok:false,error:'invalid_text'},400);
      const dataClass=sanitizeDataClass(body.dataClass);
      if(dataClass==='SECRET')return json({ok:false,error:'secret_external_mesh_forbidden'},403);
      const route=routeSkill({text:body.text});
      const plan=await buildModelMeshPlan({...body,dataClass,profile:route.profile,route},{skillSnapshot,modelSnapshot});
      return json(plan);
    }
    if(url.pathname==='/brain/mesh/execute'){
      if(typeof executeWorkers!=='function')return json({ok:false,error:'mesh_execution_not_configured'},503);
      return executeWorkers(request,env,{skillSnapshot,modelSnapshot,routeSkill});
    }
    return null;
  };
}
