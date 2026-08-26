const PROVIDERS=['claude','codex','deepseek'];
const MCP_VERSION='2025-03-26';
const headers={'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff','access-control-allow-origin':'*','access-control-allow-headers':'content-type,mcp-session-id,authorization','access-control-allow-methods':'POST,OPTIONS'};
const reply=(body,status=200)=>new Response(JSON.stringify(body),{status,headers});
const rpc=(id,result)=>reply({jsonrpc:'2.0',id,result});
const err=(id,code,message)=>reply({jsonrpc:'2.0',id,error:{code,message}});
async function bridge(env,evidence){
  if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=='function')throw new Error('AI_BRIDGE_BINDING_MISSING');
  const secret=String(env.V11_AI_BRIDGE_SECRET||'');
  if(!secret)throw new Error('AI_BRIDGE_SECRET_MISSING');
  const r=await env.AI_BRIDGE.fetch(new Request('http://127.0.0.1:8789/review',{method:'POST',headers:{authorization:'Bearer '+secret,'content-type':'application/json',accept:'application/json'},body:JSON.stringify({evidence}),signal:AbortSignal.timeout(125000)}));
  const text=await r.text();let j;try{j=JSON.parse(text);}catch{throw new Error('AI_BRIDGE_INVALID_JSON');}
  if(!r.ok)throw new Error('AI_BRIDGE_HTTP_'+r.status+':'+text.slice(0,1000));
  return j;
}
async function health(env){
  const base={ok:false,service:'TRADING_3AI_MCP',providers:PROVIDERS,binding:false,secret:false};
  try{
    base.binding=!!(env.AI_BRIDGE&&typeof env.AI_BRIDGE.fetch==='function');base.secret=!!String(env.V11_AI_BRIDGE_SECRET||'');
    if(!base.binding||!base.secret)return base;
    const r=await env.AI_BRIDGE.fetch(new Request('http://127.0.0.1:8789/health',{headers:{authorization:'Bearer '+String(env.V11_AI_BRIDGE_SECRET)}}));
    const t=await r.text();let j={};try{j=JSON.parse(t);}catch{}
    const p=j.providers||{};base.bridgeHttp=r.status;base.bridgeService=j.service||null;base.providerStatus={};
    for(const n of PROVIDERS)base.providerStatus[n]=p[n]||{configured:false};
    base.ok=r.ok&&PROVIDERS.every(n=>Boolean(base.providerStatus[n]?.configured));return base;
  }catch(e){base.error=String(e?.message||e);return base;}
}
function toolResult(data,isError=false){return {content:[{type:'text',text:JSON.stringify(data)}],structuredContent:data,isError};}
export async function handleChatGptMcp(req,env){
  const u=new URL(req.url);if(u.pathname!=='/mcp'&&u.pathname!=='/mcp/health')return null;
  if(u.pathname==='/mcp/health')return reply(await health(env));
  if(req.method==='OPTIONS')return new Response(null,{status:204,headers});
  if(req.method!=='POST')return reply({error:'METHOD_NOT_ALLOWED'},405);
  let m;try{m=await req.json();}catch{return err(null,-32700,'Parse error');}
  const id=m?.id??null,method=String(m?.method||'');
  if(method==='initialize')return rpc(id,{protocolVersion:MCP_VERSION,capabilities:{tools:{listChanged:false}},serverInfo:{name:'Trading 3AI',version:'2.0.0'},instructions:'Protected research-only gateway to Claude, OpenAI/Codex and DeepSeek. Use run_3ai_task for explicit multi-AI analysis and three_ai_health to verify connectivity. Never claim a provider responded unless its returned status is OK.'});
  if(method==='notifications/initialized')return new Response(null,{status:202,headers});
  if(method==='ping')return rpc(id,{});
  if(method==='tools/list')return rpc(id,{tools:[
    {name:'three_ai_health',title:'Check Trading 3AI',description:'Verify Cloudflare-to-VPS bridge configuration and Claude, OpenAI/Codex and DeepSeek provider availability. Read-only.',inputSchema:{type:'object',properties:{},additionalProperties:false}},
    {name:'run_3ai_task',title:'Run Trading 3AI Task',description:'Run Claude, OpenAI/Codex and DeepSeek on the same evidence package and return each real provider result plus quorum. Research/analysis only; never executes trades.',inputSchema:{type:'object',properties:{instruction:{type:'string'},context:{type:'string'}},required:['instruction'],additionalProperties:false}}
  ]});
  if(method==='tools/call'){
    const name=String(m?.params?.name||'');
    if(name==='three_ai_health'){const h=await health(env);return rpc(id,toolResult(h,!h.ok));}
    if(name!=='run_3ai_task')return err(id,-32602,'Unknown tool');
    const a=m?.params?.arguments||{},instruction=String(a.instruction||'').trim(),context=String(a.context||'').slice(0,50000);if(!instruction)return err(id,-32602,'instruction is required');
    try{
      const taskId='chatgpt-'+crypto.randomUUID();
      const j=await bridge(env,{mode:'CHATGPT_MCP_3AI',task_id:taskId,instruction:instruction.slice(0,20000),context:{text:context},requestedProviders:PROVIDERS});
      const providers={};for(const p of PROVIDERS)providers[p]=j?.providers?.[p]||{status:'UNAVAILABLE'};
      const okProviders=PROVIDERS.filter(p=>String(providers[p]?.status||'').toUpperCase()==='OK');
      const out={ok:okProviders.length>=2,quorum:okProviders.length,requiredQuorum:2,task_id:taskId,providers,bridgeMeta:{returnedEarly:j?.returnedEarly??null,decisionLatencyMs:j?.decisionLatencyMs??null}};
      return rpc(id,toolResult(out,!out.ok));
    }catch(e){return rpc(id,toolResult({ok:false,error:'3AI_GATEWAY_ERROR',message:String(e?.message||e)},true));}
  }
  return err(id,-32601,'Method not found');
}
