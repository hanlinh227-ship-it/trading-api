import {ResearchRuntime} from '../crypto-research-gateway/src/research.ts';
import {PROVIDERS} from '../crypto-research-gateway/src/providers/index.ts';
import {BybitProvider} from '../crypto-research-gateway/src/providers/bybit.ts';
import {createBybitBridgeFetchJson} from './research-bybit-transport.js';

const SERVICE_NAME='crypto-research-gateway';
const SERVICE_VERSION='0.1.0';
const RUNTIME_MODE='zero-local-research-safe';
const DEPLOYMENT_RELEASE='live-price-execution-v1';
const HEALTH_TTL_MS=30_000;
const MAX_BODY_BYTES=256_000;
const FALLBACK_TIMEOUT_MS=12_000;
const MAX_EXECUTION_QUOTE_AGE_MS=5_000;
const DEFAULT_FALLBACK_GATEWAY_URL='https://crypto-research-gateway-prod-production.up.railway.app';
const ACTIONS=new Set(['snapshot','candles','orderbook','funding_oi','execution_quote']);
const INSTRUMENTS=new Set(['spot','perpetual']);
const SIDES=new Set(['LONG','SHORT']);
const EXECUTION_VENUES=new Set(['bybit','binance']);
const MARKET_TOOLS=['market_snapshot','market_candles','market_orderbook','market_execution_quote','derivatives_funding_oi'];
const ALLOWED_KEYS=new Set(['action','symbol','instrument','preferredVenue','interval','limit','side','executionVenue']);
const encoder=new TextEncoder();
let bybitTransportConfigured=false;

function configureCloudflareBybit(env={}){
  if(bybitTransportConfigured||!env.AI_BRIDGE)return;
  try{
    PROVIDERS.bybit=new BybitProvider({fetchJson:createBybitBridgeFetchJson(env)});
  }catch(error){
    const message=String(error?.message||error);
    PROVIDERS.bybit=new BybitProvider({fetchJson:async()=>{throw new Error(message);}});
  }
  bybitTransportConfigured=true;
}

function json(body,status=200){
  return new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
}

function validOptionalString(value,min,max){
  return value===undefined||(typeof value==='string'&&value.length>=min&&value.length<=max);
}

function parseMarketInput(value){
  if(!value||typeof value!=='object'||Array.isArray(value))return null;
  const raw=value;
  if(Object.keys(raw).some(key=>!ALLOWED_KEYS.has(key)))return null;
  if(typeof raw.action!=='string'||!ACTIONS.has(raw.action))return null;
  if(typeof raw.symbol!=='string'||raw.symbol.length<3||raw.symbol.length>40)return null;
  const instrument=raw.instrument===undefined?'spot':raw.instrument;
  if(typeof instrument!=='string'||!INSTRUMENTS.has(instrument))return null;
  if(!validOptionalString(raw.preferredVenue,2,20))return null;
  if(!validOptionalString(raw.interval,1,12))return null;
  if(raw.limit!==undefined&&(!Number.isInteger(raw.limit)||raw.limit<1||raw.limit>500))return null;
  if(raw.side!==undefined&&(typeof raw.side!=='string'||!SIDES.has(raw.side)))return null;
  if(raw.executionVenue!==undefined&&(typeof raw.executionVenue!=='string'||!EXECUTION_VENUES.has(raw.executionVenue)))return null;
  if(raw.action==='execution_quote'&&!raw.side)return null;
  return {
    action:raw.action,
    symbol:raw.symbol.toUpperCase(),
    instrument,
    ...(raw.preferredVenue===undefined?{}:{preferredVenue:raw.preferredVenue}),
    ...(raw.interval===undefined?{}:{interval:raw.interval}),
    ...(raw.limit===undefined?{}:{limit:raw.limit}),
    ...(raw.side===undefined?{}:{side:raw.side}),
    ...(raw.executionVenue===undefined?{}:{executionVenue:raw.executionVenue}),
  };
}

async function parseJsonBody(request){
  const declared=Number(request.headers.get('content-length')||0);
  if(Number.isFinite(declared)&&declared>MAX_BODY_BYTES)throw new Error('body_too_large');
  const text=await request.text();
  if(encoder.encode(text).byteLength>MAX_BODY_BYTES)throw new Error('body_too_large');
  return JSON.parse(text);
}

function shouldUseBybitSafetyFallback(input,result){
  if(!result||result.ok!==false||result.degraded!==true)return false;
  if(input.action!=='execution_quote')return false;
  return input.executionVenue===undefined||input.executionVenue==='bybit';
}

function isValidFallbackExecutionQuote(input,quote){
  if(!quote||typeof quote!=='object')return false;
  if(quote.executionVerified!==true||quote.status!=='OK'||quote.venue!=='bybit')return false;
  if(quote.instrument!==input.instrument||quote.side!==input.side)return false;
  const bid=Number(quote.bid);
  const ask=Number(quote.ask);
  const executablePrice=Number(quote.executablePrice);
  const quoteAgeMs=Number(quote.quoteAgeMs);
  if(!Number.isFinite(bid)||!Number.isFinite(ask)||!Number.isFinite(executablePrice)||!Number.isFinite(quoteAgeMs))return false;
  if(bid<=0||ask<=0||bid>ask||quoteAgeMs<0||quoteAgeMs>MAX_EXECUTION_QUOTE_AGE_MS)return false;
  const expected=input.side==='LONG'?ask:bid;
  return executablePrice===expected;
}

async function runBybitSafetyFallback(input,result,{fallbackFetch,fallbackGatewayUrl}){
  if(!shouldUseBybitSafetyFallback(input,result))return null;
  const base=String(fallbackGatewayUrl||'').replace(/\/+$/,'');
  if(!base.startsWith('https://'))return null;
  try{
    const response=await fallbackFetch(base+'/research/market',{
      method:'POST',
      headers:{'content-type':'application/json','accept':'application/json'},
      body:JSON.stringify(input),
      signal:AbortSignal.timeout(FALLBACK_TIMEOUT_MS),
    });
    if(!response.ok)return null;
    const text=await response.text();
    if(encoder.encode(text).byteLength>MAX_BODY_BYTES)return null;
    const payload=JSON.parse(text);
    if(!payload||typeof payload!=='object'||payload.ok!==true)return null;
    const quote=payload.executionQuote;
    if(!isValidFallbackExecutionQuote(input,quote))return null;
    return {
      ...payload,
      edgeRuntimeProvider:'cloudflare-workers',
      upstreamFallback:'railway',
      fallbackReason:String(result.error||result.reason||'cloudflare_bybit_degraded').slice(0,160),
    };
  }catch{
    return null;
  }
}

export function createResearchGatewayHandler({
  runtime=new ResearchRuntime(),
  now=()=>Date.now(),
  fallbackFetch=fetch,
  fallbackGatewayUrl=DEFAULT_FALLBACK_GATEWAY_URL,
}={}){
  let probePromise=null;
  let healthValidUntil=0;

  async function ensureHealth(){
    if(runtime.getLastProbeAt()!==null&&now()<healthValidUntil)return null;
    if(!probePromise){
      probePromise=Promise.resolve(runtime.probeAll())
        .then(()=>{healthValidUntil=now()+HEALTH_TTL_MS;return null;})
        .catch(error=>error instanceof Error?error:new Error('provider_probe_failed'))
        .finally(()=>{probePromise=null;});
    }
    return probePromise;
  }

  return async function handleResearchGateway(request,env={}){
    const url=new URL(request.url);
    if(!['/health','/capabilities','/research/market'].includes(url.pathname))return null;
    configureCloudflareBybit(env);

    if(url.pathname==='/health'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      const probeError=await ensureHealth();
      const providers=runtime.getHealth();
      const healthyProviders=Object.entries(providers).filter(([,status])=>status?.ok===true).map(([id])=>id);
      const degradedProviders=Object.entries(providers).filter(([,status])=>status?.ok!==true).map(([id])=>id);
      return json({
        ok:true,
        service:SERVICE_NAME,
        version:SERVICE_VERSION,
        runtimeMode:RUNTIME_MODE,
        runtimeProvider:'cloudflare-workers',
        deploymentRelease:DEPLOYMENT_RELEASE,
        deploymentSourceSha:String(env.RUNTIME_REVISION||''),
        localInstallRequired:false,
        bybitTransportPriority:['cloudflare-vpc-bridge','railway-safety-fallback'],
        lastPublicProbeTimestamp:runtime.getLastProbeAt(),
        healthyProviders,
        degradedProviders,
        providers,
        ...(probeError?{probeError:probeError.message}:{}),
      });
    }

    if(url.pathname==='/capabilities'){
      if(request.method!=='GET')return json({ok:false,error:'method_not_allowed'},405);
      return json({service:SERVICE_NAME,version:SERVICE_VERSION,runtimeMode:RUNTIME_MODE,runtimeProvider:'cloudflare-workers',localInstallRequired:false,tools:MARKET_TOOLS});
    }

    if(request.method!=='POST')return json({ok:false,error:'method_not_allowed'},405);
    let raw;
    try{raw=await parseJsonBody(request);}catch{return json({ok:false,degraded:false,error:'invalid_research_request'},400);}
    const input=parseMarketInput(raw);
    if(!input)return json({ok:false,degraded:false,error:'invalid_research_request'},400);
    await ensureHealth();
    const result=await runtime.runMarket(input);
    const fallback=await runBybitSafetyFallback(input,result,{fallbackFetch,fallbackGatewayUrl});
    if(fallback)return json(fallback,200);
    return json(result,result?.degraded===true&&result?.ok===false?503:200);
  };
}

const defaultHandler=createResearchGatewayHandler();
export const handleResearchGateway=(request,env)=>defaultHandler(request,env);
