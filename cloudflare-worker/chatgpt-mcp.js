const PROVIDERS=['claude','codex','deepseek','qwen','openrouter'];
const MCP_VERSION='2025-03-26';
const headers={'content-type':'application/json; charset=utf-8','cache-control':'no-store','x-content-type-options':'nosniff','access-control-allow-origin':'*','access-control-allow-headers':'content-type,mcp-session-id','access-control-allow-methods':'POST,OPTIONS'};
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
function toolResult(data){return {content:[{type:'text',text:JSON.stringify(data)}],structuredContent:data,isError:false};}
export async function handleChatGptMcp(req,env){
  const u=new URL(req.url);if(u.pathname!=='/mcp')return null;
  if(req.method==='OPTIONS')return new Response(null,{status:204,headers});
  if(req.method!=='POST')return reply({error:'METHOD_NOT_ALLOWED'},405);
  let m;try{m=await req.json();}catch{return err(null,-32700,'Parse error');}
  const id=m?.id??null,method=String(m?.method||'');
  if(method==='initialize')return rpc(id,{protocolVersion:MCP_VERSION,capabilities:{tools:{listChanged:false}},serverInfo:{name:'Trading 5AI',version:'1.0.0'},instructions:'On-demand five-AI analysis gateway. Use run_5ai_task when the user explicitly requests five-AI collaboration or when multi-model review is useful.'});
  if(method==='notifications/initialized')return new Response(null,{status:202,headers});
  if(method==='ping')return rpc(id,{});
  if(method==='tools/list')return rpc(id,{tools:[{name:'run_5ai_task',title:'Run Trading 5AI Task',description:'Run Claude, Codex, DeepSeek, Qwen and OpenRouter in parallel on one analysis/research task and return each provider review. Use for trading analysis, market research, strategy review and cross-model consensus. This tool analyzes only and does not execute trades.',inputSchema:{type:'object',properties:{instruction:{type:'string',description:'Complete task for all five AI models.'},context:{type:'string',description:'Optional supporting market data, quotes, news, code or other evidence.'}},required:['instruction'],additionalProperties:false}}]});
  if(method==='tools/call'){
    const name=String(m?.params?.name||'');if(name!=='run_5ai_task')return err(id,-32602,'Unknown tool');
    const a=m?.params?.arguments||{},instruction=String(a.instruction||'').trim(),context=String(a.context||'').slice(0,50000);if(!instruction)return err(id,-32602,'instruction is required');
    try{const taskId='chatgpt-'+crypto.randomUUID();const j=await bridge(env,{mode:'CHATGPT_MCP_5AI',task_id:taskId,instruction:instruction.slice(0,20000),context:{text:context},requestedProviders:PROVIDERS});const providers={};for(const p of PROVIDERS)providers[p]=j?.providers?.[p]||{status:'UNAVAILABLE'};return rpc(id,toolResult({ok:PROVIDERS.every(p=>String(providers[p]?.status||'').toUpperCase()==='OK'),task_id:taskId,providers}));}catch(e){return rpc(id,{content:[{type:'text',text:'5AI gateway error: '+String(e?.message||e)}],isError:true});}
  }
  return err(id,-32601,'Method not found');
}
