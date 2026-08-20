import {executeHyroPlan,getHyroTelemetry} from '../cloudflare-worker/hyro-execution.js';
import {hmacHex} from '../cloudflare-worker/providers/bybit-signed-client.js';

class MemoryKV{
  constructor(){this.m=new Map();}
  async get(k,type){if(!this.m.has(k))return null;const v=this.m.get(k);return type==='json'?JSON.parse(v):v;}
  async put(k,v){this.m.set(k,String(v));}
  async delete(k){this.m.delete(k);}
}
const apiKey=process.env.HYRO_BYBIT_API_KEY,apiSecret=process.env.HYRO_BYBIT_API_SECRET;
if(!apiKey||!apiSecret)throw new Error('DEMO credentials missing');
const kv=new MemoryKV();
await kv.put('v7717:hyro:profile',JSON.stringify({phase:'CHALLENGE',accountSize:5000,internal:{},funded:null}));
await kv.put('v77173:hyro:control',JSON.stringify({manualPaused:false}));
const env={TRADING_STATE:kv,HYRO_BYBIT_MODE:'DEMO',HYRO_AUTO_EXECUTION:'true',HYRO_BYBIT_API_KEY:apiKey,HYRO_BYBIT_API_SECRET:apiSecret,HYRO_ACCOUNT_ID:'V78026_DEMO'};
const base='https://api-demo.bybit.com',recv='5000';
async function signed(method,path,p={}){const ts=String(Date.now()),upper=method.toUpperCase();let url=base+path,body='',payload='';if(upper==='GET'){const q=new URLSearchParams();for(const [k,v] of Object.entries(p))if(v!==undefined&&v!==null&&v!=='')q.set(k,String(v));payload=q.toString();if(payload)url+='?'+payload;}else{body=JSON.stringify(p);payload=body;}const sign=await hmacHex(apiSecret,ts+apiKey+recv+payload);const r=await fetch(url,{method:upper,headers:{'X-BAPI-API-KEY':apiKey,'X-BAPI-TIMESTAMP':ts,'X-BAPI-RECV-WINDOW':recv,'X-BAPI-SIGN':sign,'Content-Type':'application/json'},body:upper==='GET'?undefined:body});const j=await r.json().catch(()=>null);if(!r.ok||Number(j?.retCode)!==0)throw new Error(`${path}: ${j?.retMsg||r.status} [${j?.retCode??'HTTP'}]`);return j;}
async function priceOf(symbol){const r=await fetch(`https://api.bybit.com/v5/market/tickers?category=linear&symbol=${symbol}`),j=await r.json();const p=Number(j?.result?.list?.[0]?.lastPrice);if(!Number.isFinite(p)||p<=0)throw new Error(`price unavailable ${symbol}`);return p;}
async function exactOrders(symbol,orderLinkId){const ids=new Set();for(const [path,params] of [['/v5/order/realtime',{category:'linear',symbol,orderLinkId}],['/v5/order/history',{category:'linear',symbol,orderLinkId,limit:5}]]){try{const j=await signed('GET',path,params);for(const x of j?.result?.list||[])if(x.orderLinkId===orderLinkId&&x.orderId)ids.add(x.orderId);}catch{}}return [...ids];}
async function cancelExact(symbol,orderId,orderLinkId){try{return await signed('POST','/v5/order/cancel',{category:'linear',symbol,orderId,orderLinkId});}catch(e){console.log('CLEANUP_CANCEL_WARNING',String(e.message||e));return null;}}
const telemetry=await getHyroTelemetry(env);if(!telemetry.connected)throw new Error(`DEMO telemetry unavailable: ${telemetry.reason}`);
const active=new Set([...(telemetry.positions||[]).map(x=>x.symbol),...(telemetry.openOrders||[]).map(x=>x.symbol)]);if(active.size>=3)throw new Error(`DEMO gate blocked: active slots=${active.size}`);
const candidates=['DOGEUSDT','XRPUSDT','ADAUSDT','TRXUSDT','SOLUSDT','ETHUSDT','BTCUSDT'];const symbol=candidates.find(x=>!active.has(x));if(!symbol)throw new Error('No inactive DEMO symbol available');
const px=await priceOf(symbol);const mkPlan=(tag)=>({setupId:`V78026-${tag}-${Date.now()}`,scanId:`V78026-${tag}`,symbol,side:'BUY',action:'LIMIT',entry:px*0.98,sl:px*0.96,tp:px*1.02,riskMultiplier:0.25});

// Acceptance 1: one genuine DEMO order must be acknowledged with venue orderId.
const normalPlan=mkPlan('NORMAL');const normal=await executeHyroPlan(env,normalPlan);if(!(normal.ok&&normal.executed&&normal.order?.state==='ACKNOWLEDGED'&&normal.order?.orderId))throw new Error(`NORMAL_DEMO_FAIL ${JSON.stringify(normal)}`);const normalIds=await exactOrders(symbol,normal.order.orderLinkId);if(!normalIds.includes(normal.order.orderId))throw new Error('NORMAL_DEMO venue lookup did not confirm orderId');console.log('DEMO_ACK',JSON.stringify({symbol,setupId:normalPlan.setupId,state:normal.order.state,orderId:normal.order.orderId,orderLinkId:normal.order.orderLinkId,venueOrderCount:normalIds.length}));await cancelExact(symbol,normal.order.orderId,normal.order.orderLinkId);

// Wait briefly so the exact cancelled order is reflected before the next gate telemetry call.
await new Promise(r=>setTimeout(r,1200));

// Acceptance 2: forward a real DEMO create successfully, then deliberately drop its response.
// The first call must persist RECONCILE_REQUIRED. The retry must reconcile the already-created
// venue order BEFORE current account gates and must not POST a second create.
const ambPlan=mkPlan('AMBIG');const originalFetch=globalThis.fetch;let dropped=false,forwardedCreates=0;globalThis.fetch=async(input,init={})=>{const url=String(input);if(!dropped&&String(init.method||'GET').toUpperCase()==='POST'&&url.includes('api-demo.bybit.com/v5/order/create')){forwardedCreates++;const res=await originalFetch(input,init);const clone=res.clone();const j=await clone.json().catch(()=>null);if(res.ok&&Number(j?.retCode)===0&&j?.result?.orderId){dropped=true;throw new Error('V78-026_SIMULATED_RESPONSE_LOSS_AFTER_VENUE_ACCEPT');}return res;}return originalFetch(input,init);};
let first;try{first=await executeHyroPlan(env,ambPlan);}finally{globalThis.fetch=originalFetch;}
if(first?.gate?.reason!=='RECONCILE_REQUIRED')throw new Error(`AMBIG_FIRST_FAIL ${JSON.stringify(first)}`);const stored1=await kv.get(`v7718:hyro:intent:${ambPlan.setupId}`,'json');if(stored1?.state!=='RECONCILE_REQUIRED')throw new Error(`AMBIG_STATE_NOT_PERSISTED ${stored1?.state}`);
const second=await executeHyroPlan(env,ambPlan);if(!(second.ok&&second.idempotent&&second.existing?.state==='ACKNOWLEDGED'&&second.existing?.orderId))throw new Error(`AMBIG_RETRY_FAIL ${JSON.stringify(second)}`);if(forwardedCreates!==1)throw new Error(`DUPLICATE_CREATE_CALLS ${forwardedCreates}`);const ambIds=await exactOrders(symbol,second.existing.orderLinkId);if(ambIds.length!==1||ambIds[0]!==second.existing.orderId)throw new Error(`DUPLICATE_VENUE_ORDERS ${JSON.stringify(ambIds)}`);console.log('AMBIG_RECONCILE',JSON.stringify({symbol,setupId:ambPlan.setupId,firstReason:first.gate.reason,persistedAfterFirst:stored1.state,retryState:second.existing.state,orderId:second.existing.orderId,orderLinkId:second.existing.orderLinkId,forwardedCreatePosts:forwardedCreates,venueOrderCount:ambIds.length}));await cancelExact(symbol,second.existing.orderId,second.existing.orderLinkId);

// Acceptance 3: legacy state-less record remains acknowledged/idempotent and cannot resubmit.
await new Promise(r=>setTimeout(r,1200));const legacyPlan=mkPlan('LEGACY');const legacyKey=`v7718:hyro:intent:${legacyPlan.setupId}`;await kv.put(legacyKey,JSON.stringify({id:legacyPlan.setupId,orderLinkId:'legacy-v78026',orderId:'legacy-order-id',symbol,side:'Buy',status:'SUBMITTED'}));let legacyPosts=0;globalThis.fetch=async(input,init={})=>{if(String(init.method||'GET').toUpperCase()==='POST'&&String(input).includes('/v5/order/create'))legacyPosts++;return originalFetch(input,init);};let legacy;try{legacy=await executeHyroPlan(env,legacyPlan);}finally{globalThis.fetch=originalFetch;}if(!(legacy.ok&&legacy.idempotent&&!legacy.executed&&legacy.existing?.orderId==='legacy-order-id'))throw new Error(`LEGACY_COMPAT_FAIL ${JSON.stringify(legacy)}`);if(legacyPosts!==0)throw new Error(`LEGACY_RESUBMIT_DETECTED ${legacyPosts}`);console.log('LEGACY_COMPAT',JSON.stringify({setupId:legacyPlan.setupId,idempotent:legacy.idempotent,orderId:legacy.existing.orderId,createPosts:legacyPosts}));
console.log('V78-026 DEMO ACCEPTANCE PASS');
