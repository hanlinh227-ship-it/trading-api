const PROVIDERS=['claude','codex','deepseek'];
const json=(body,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff','access-control-allow-origin':'*'}});
async function callBridge(env,payload){
  if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=='function')return {response:null,error:'AI_BRIDGE_BINDING_MISSING'};
  const secret=String(env.V11_AI_BRIDGE_SECRET||'');if(!secret)return {response:null,error:'AI_BRIDGE_SECRET_MISSING'};
  try{return {response:await env.AI_BRIDGE.fetch(new Request('http://127.0.0.1:8789/review',{method:'POST',headers:{'content-type':'application/json',accept:'application/json',authorization:'Bearer '+secret},body:JSON.stringify({evidence:{mode:'CHATGPT_3AI_COUNCIL',task_id:payload.task_id,instruction:payload.task,context:{mode:payload.mode,source:'CHATGPT_CUSTOM_ACTION'},requestedProviders:PROVIDERS}}),signal:AbortSignal.timeout(125000)})),error:null};}catch(e){return {response:null,error:'AI_BRIDGE_FETCH_FAILED:'+String(e?.message||e)};}
}
export async function handleGpt5AiAction(req,env){
  const u=new URL(req.url);if(u.pathname!=='/api/5ai/council'&&u.pathname!=='/api/3ai/council'&&u.pathname!=='/api/3ai/health')return null;
  if(req.method==='OPTIONS')return new Response(null,{status:204,headers:{'access-control-allow-origin':'*','access-control-allow-methods':'GET, POST, OPTIONS','access-control-allow-headers':'Authorization, Content-Type'}});
  const expected=String(env.GPT_5AI_ACTION_KEY||'');if(!expected)return json({ok:false,error:'CHATGPT_ACTION_KEY_NOT_CONFIGURED'},503);
  if(String(req.headers.get('authorization')||'')!=='Bearer '+expected)return json({ok:false,error:'UNAUTHORIZED'},401);
  if(u.pathname==='/api/3ai/health'){
    if(req.method!=='GET'&&req.method!=='POST')return json({ok:false,error:'METHOD_NOT_ALLOWED'},405);
    if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=='function')return json({ok:false,error:'AI_BRIDGE_BINDING_MISSING'},503);
    try{const r=await env.AI_BRIDGE.fetch(new Request('http://127.0.0.1:8789/health',{headers:{authorization:'Bearer '+String(env.V11_AI_BRIDGE_SECRET||'')}}));const t=await r.text();let d={};try{d=JSON.parse(t);}catch{};const p=d.providers||{};const configured=PROVIDERS.filter(n=>Boolean(p[n]?.configured));return json({ok:r.ok&&configured.length===3,service:'CHATGPT_3AI_ACTION',bridgeHttp:r.status,providers:p,core:PROVIDERS,configured},r.ok&&configured.length===3?200:503);}catch(e){return json({ok:false,error:'AI_BRIDGE_HEALTH_FAILED',message:String(e?.message||e)},503);}
  }
  if(req.method!=='POST')return json({ok:false,error:'METHOD_NOT_ALLOWED'},405);
  let body;try{body=await req.json();}catch{return json({ok:false,error:'INVALID_JSON'},400)}
  const task=String(body?.task||'').trim(),mode=String(body?.mode||'general').trim();if(!task)return json({ok:false,error:'TASK_REQUIRED'},400);if(task.length>20000)return json({ok:false,error:'TASK_TOO_LARGE'},413);
  const taskId='gpt-3ai-'+Date.now()+'-'+crypto.randomUUID().slice(0,8),bridge=await callBridge(env,{task_id:taskId,task,mode});if(!bridge.response)return json({ok:false,task_id:taskId,error:bridge.error,providers:{}},503);
  let result;try{result=await bridge.response.json();}catch{return json({ok:false,task_id:taskId,error:'AI_BRIDGE_INVALID_JSON',providers:{}},502)}
  const providers={};for(const p of PROVIDERS)providers[p]=result?.providers?.[p]||{status:'MISSING'};const okProviders=PROVIDERS.filter(p=>String(providers[p]?.status||'').toUpperCase()==='OK');const ok=bridge.response.ok&&okProviders.length>=2;
  return json({ok,task_id:taskId,mode,quorum:okProviders.length,requiredQuorum:2,coreProviders:PROVIDERS,providers,compatibilityRoute:u.pathname==='/api/5ai/council'},ok?200:502);
}
