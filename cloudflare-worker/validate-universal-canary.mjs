const USER_ADAPTERS=Object.freeze(['chatgpt','claude','gemini']);
const FORBIDDEN_RESPONSE_TERMS=Object.freeze(['chainOfThought','hidden_reasoning','chain_of_thought','raw_private_payload','raw_private_tool_payload']);

function cleanBaseUrl(value){
  const text=String(value||'').trim().replace(/\/+$/,'');
  if(!/^https:\/\//i.test(text))throw new Error('WORKER_BASE_URL_REQUIRED');
  return text;
}
function cleanSha(value){
  const text=String(value||'').trim().toLowerCase();
  if(!/^[a-f0-9]{40}$/.test(text))throw new Error('SOURCE_SHA_REQUIRED');
  return text;
}
function sanitizeCheck(value,tokens){
  const text=JSON.stringify(value);
  for(const term of FORBIDDEN_RESPONSE_TERMS)if(text.includes(term))throw new Error(`UNIVERSAL_CANARY_FORBIDDEN_RESPONSE_FIELD:${term}`);
  for(const token of Object.values(tokens))if(token&&text.includes(token))throw new Error('UNIVERSAL_CANARY_TOKEN_ECHO');
}
async function requestJson(fetchImpl,baseUrl,path,{clientId,token,body}={}){
  const headers={'x-brain-client':clientId,authorization:`Bearer ${token}`};
  const init={method:body===undefined?'GET':'POST',headers};
  if(body!==undefined){headers['content-type']='application/json';init.body=JSON.stringify(body);}
  const response=await fetchImpl(`${baseUrl}${path}`,init);
  const text=await response.text();
  let value;
  try{value=JSON.parse(text);}catch{throw new Error(`UNIVERSAL_CANARY_INVALID_JSON:${path}`);}
  if(!response.ok)throw new Error(`UNIVERSAL_CANARY_HTTP_${response.status}:${path}`);
  return value;
}

export async function runUniversalCanary({baseUrl,sourceSha,clients,fetchImpl=fetch}={}){
  const endpoint=cleanBaseUrl(baseUrl);
  const expected=cleanSha(sourceSha);
  if(!clients||typeof clients!=='object')throw new Error('UNIVERSAL_CANARY_CLIENTS_REQUIRED');
  for(const id of USER_ADAPTERS)if(!String(clients[id]||'').trim())throw new Error(`UNIVERSAL_CANARY_CLIENT_TOKEN_REQUIRED:${id}`);
  const primary='chatgpt';
  const primaryToken=String(clients[primary]);

  const health=await requestJson(fetchImpl,endpoint,'/brain/universal/health',{clientId:primary,token:primaryToken});
  sanitizeCheck(health,clients);
  if(health.ok!==true||health.brainAuthority!=='GITHUB_BRAIN_V4'||health.sourceSha!==expected||health.fastZeroRtt!==true||health.fastExternalRoutingCalls!==0){
    throw new Error('UNIVERSAL_BRAIN_HEALTH_FAILED');
  }

  const capabilities=await requestJson(fetchImpl,endpoint,'/brain/universal/capabilities',{clientId:primary,token:primaryToken});
  sanitizeCheck(capabilities,clients);
  const advertised=new Set(Array.isArray(capabilities.userAdapters)?capabilities.userAdapters:(Array.isArray(capabilities.adapters)?capabilities.adapters:[]));
  for(const id of USER_ADAPTERS)if(!advertised.has(id))throw new Error(`UNIVERSAL_CANARY_ADAPTER_MISSING:${id}`);
  if(capabilities.paidFallback!==false||capabilities.permissionWidening!==false)throw new Error('UNIVERSAL_CANARY_CAPABILITY_SAFETY_FAILED');

  for(const id of USER_ADAPTERS){
    const body={
      text:'explain recursion briefly',request_id:`canary-${id}`,session_id:'production-canary',freshness:'none',data_class:'PUBLIC',requested_action_class:'informational'
    };
    const routed=await requestJson(fetchImpl,endpoint,'/brain/universal/route',{clientId:id,token:String(clients[id]),body});
    sanitizeCheck(routed,clients);
    if(routed.ok!==true||routed.clientId!==id||routed.sourceSha!==expected)throw new Error(`UNIVERSAL_ADAPTER_ROUTE_FAILED:${id}`);
  }

  const highRisk=await requestJson(fetchImpl,endpoint,'/brain/universal/route',{
    clientId:primary,
    token:primaryToken,
    body:{text:'giao dịch BTC live',request_id:'canary-live',session_id:'production-canary',freshness:'live',data_class:'PUBLIC',requested_action_class:'live_or_trading'}
  });
  sanitizeCheck(highRisk,clients);
  if(highRisk.ok!==true||highRisk.profile!=='DEEP'||highRisk.onlineBrainRequired!==true||highRisk.safeDegradedAllowed!==false){
    throw new Error('UNIVERSAL_HIGH_RISK_FAIL_CLOSED_FAILED');
  }

  return Object.freeze({ok:true,sourceSha:expected,adapters:[...USER_ADAPTERS],highRiskFailClosed:true});
}

async function main(){
  const clients={
    chatgpt:String(process.env.BRAIN_CLIENT_CHATGPT_TOKEN||''),
    claude:String(process.env.BRAIN_CLIENT_CLAUDE_TOKEN||''),
    gemini:String(process.env.BRAIN_CLIENT_GEMINI_TOKEN||''),
  };
  const result=await runUniversalCanary({
    baseUrl:process.env.WORKER_BASE_URL,
    sourceSha:process.env.SKILL_GATEWAY_SOURCE_SHA||process.env.GITHUB_SHA,
    clients,
  });
  console.log(`UNIVERSAL_BRAIN_HEALTH=PASS sourceSha=${result.sourceSha}`);
  console.log(`UNIVERSAL_ADAPTER_CANARY=PASS ${result.adapters.join(' ')}`);
  console.log('UNIVERSAL_HIGH_RISK_FAIL_CLOSED=PASS');
}

if(import.meta.url===`file://${process.argv[1]}`){
  main().catch(error=>{console.error(String(error?.message||error));process.exit(1);});
}
