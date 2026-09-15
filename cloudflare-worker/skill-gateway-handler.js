import {routeSkillRequest} from './skill-gateway.js';

const MAX_BODY_BYTES=64_000;
const encoder=new TextEncoder();
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
const LEGION_MAX_PARALLEL={FAST:0,STANDARD:2,DEEP:4};
const LEGION_DIVISIONS=[
  'engineering','security','research','data_rag','creative','ux_ui','design_2d','design_3d',
  'automation','browser_mcp','deployment','trading_quant_research','business','game','academic','checker_grader'
];
const LEGION_EXECUTION_PATTERNS=[
  'single_specialist','parallel_specialists','maker_checker','corrective_rag','agentic_rag','mcp_specialist_router','multimodal_team'
];
const LEARNING_LAYERS=['experience','curated','exploration'];

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

function legionBase(snapshot){
  return {
    sourceSha:snapshot.source_sha,
    releaseId:snapshot.release_id,
    routing_authority:false,
    reasoning_authority:false,
    externalRoutingCalls:0,
    stableRequestDependency:false,
  };
}

function legionStatus(snapshot){
  return {
    ok:true,
    service:'peer-tri-layer-ai-legion',
    ...legionBase(snapshot),
    status:'ready',
    singleCommander:'GITHUB_BRAIN_V4',
    maxParallel:LEGION_MAX_PARALLEL,
    tradingDefault:'research_only',
    liveFinancialExecution:false,
  };
}

function legionCapabilities(snapshot){
  return {
    ok:true,
    ...legionBase(snapshot),
    divisions:LEGION_DIVISIONS,
    maxParallel:LEGION_MAX_PARALLEL,
    executionPatterns:LEGION_EXECUTION_PATTERNS,
    workerSelection:'bounded_capability_match',
    modelExecutionLayer:'adaptive_free_model_mesh',
    opencodeWorker:'optional_bounded_execution',
    permissionWidening:false,
  };
}

function learningStatus(snapshot){
  return {
    ok:true,
    service:'peer-tri-layer-learning',
    ...legionBase(snapshot),
    status:'idle',
    activeJobs:0,
    layers:LEARNING_LAYERS,
    epistemicRelationship:'peer',
    fixedLayerPriority:false,
    majorityVoteForTruth:false,
    stableDirectWrite:false,
    promotionRequiresEvidence:true,
    highRiskSelfApproval:false,
  };
}

export function createSkillGatewayHandler({snapshot}={}){
  if(!snapshot||snapshot.schema_version!==1||snapshot.presentation?.mode!=='plain')throw new Error('SKILL_GATEWAY_SNAPSHOT_REQUIRED');
  return async function handleSkillGateway(request){
    const url=new URL(request.url);
    const supported=[
      '/brain/health','/brain/route','/brain/legion/health','/brain/legion/capabilities','/brain/learning/status'
    ];
    if(!supported.includes(url.pathname))return null;
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
        plainLanguagePresentation:true,
        presentationLocale:snapshot.presentation.locale,
        fallbackPrimarySkill:snapshot.fallback_primary_skill,
        externalRoutingCalls:0,
        generatedAt:snapshot.generated_at,
      });
    }
    if(url.pathname==='/brain/legion/health'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      return json(legionStatus(snapshot));
    }
    if(url.pathname==='/brain/legion/capabilities'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      return json(legionCapabilities(snapshot));
    }
    if(url.pathname==='/brain/learning/status'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      return json(learningStatus(snapshot));
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
