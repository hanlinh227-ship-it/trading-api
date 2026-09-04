import {hmacHex} from "./providers/bybit-signed-client.js";
import {bybitCredentials,bybitAutoConfig} from "./bybit-auto-config.js";
import {BYBIT_PRIVATE_TRANSPORT,BYBIT_MARKET_TRANSPORT,BYBIT_RUNTIME_CONTRACT_VERSION} from "./bybit-runtime-contract.js";

const DEFAULT_BASES=["https://api.bybit.com","https://api.bytick.com"];
const BRIDGE_PRIVATE_URL="http://127.0.0.1:8789/bybit/private";
const BRIDGE_TIMEOUT_MS=25000;
const clean=o=>Object.fromEntries(Object.entries(o||{}).filter(([,v])=>v!==undefined&&v!==null&&v!==""));
const qs=o=>new URLSearchParams(Object.entries(clean(o)).map(([k,v])=>[k,String(v)])).toString();
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const bridgeSecret=env=>String(env?.V11_AI_BRIDGE_SECRET||env?.BYBIT_VPS_BRIDGE_SECRET||"").trim();
function bases(env={}){
  const demo=String(env.BYBIT_AUTO_DEMO||"").toLowerCase()==="true";
  if(demo)return ["https://api-demo.bybit.com"];
  const preferred=String(env.BYBIT_API_BASE_URL||"").trim().replace(/\/$/,"");
  return [...new Set([preferred,...DEFAULT_BASES].filter(Boolean))];
}
function bybitError(path,status,p,meta={}){const msg=p?.retMsg||meta.bodySnippet||`HTTP ${status}`;const e=new Error(`${path}: ${msg}`);e.bybit={path,httpStatus:status,retCode:Number.isFinite(Number(p?.retCode))?Number(p.retCode):null,retMsg:p?.retMsg||null,base:meta.base||null,attemptedBases:meta.attemptedBases||[],bodySnippet:meta.bodySnippet||null,transport:meta.transport||null,runtimeContract:BYBIT_RUNTIME_CONTRACT_VERSION};return e;}
async function parseResponse(r,path,meta={}){
  const text=await r.text();let p=null;try{p=text?JSON.parse(text):null;}catch{}
  const bodySnippet=!p&&text?String(text).replace(/\s+/g," ").slice(0,240):null;
  if(!r.ok||Number(p?.retCode)!==0)throw bybitError(path,r.status,p,{...meta,bodySnippet});
  return p;
}
function retryableReadError(e){
  const h=Number(e?.bybit?.httpStatus||0),r=Number(e?.bybit?.retCode);
  return [408,425,429,500,502,503,504].includes(h)||[10000,10006,10016].includes(r)||(!h&&!Number.isFinite(r));
}
function unchangedWrite(e){const msg=String(e?.bybit?.retMsg||e?.message||"").toLowerCase();return msg.includes("not modified")||msg.includes("not modify")||msg.includes("already set")||msg.includes("same as current");}
function entryOrderLinkId(body={}){
  const symbol=String(body.symbol||"NA").replace(/[^A-Za-z0-9]/g,"").slice(0,10);
  const side=String(body.side||"")==="Buy"?"B":"S";
  const qty=String(body.qty||"0").replace(/[^0-9]/g,"").slice(-7)||"0";
  const bucket=Math.floor(Date.now()/(5*60*1000)).toString(36);
  return `ba196-${symbol}-${side}-${qty}-${bucket}`.slice(0,36);
}
export function bybitV5(env={}){
  const demo=String(env.BYBIT_AUTO_DEMO||"").toLowerCase()==="true";
  const c=bybitCredentials(env),cfg=bybitAutoConfig(env),baseList=bases(env),recvWindow=String(Math.max(5000,Math.min(20000,Number(cfg.execution?.recvWindow||10000))));
  async function pub(path,params={}){
    const q=qs(params),attempted=[];let lastErr;
    for(const base of baseList){
      attempted.push(base);
      try{const url=`${base}${path}${q?`?${q}`:""}`;const r=await fetch(url,{headers:{accept:"application/json"},signal:AbortSignal.timeout(BRIDGE_TIMEOUT_MS)});return await parseResponse(r,path,{base,attemptedBases:[...attempted],transport:"CLOUDFLARE_PUBLIC_DIRECT"});}
      catch(e){lastErr=e;if(Number(e?.bybit?.httpStatus)!==403&&Number(e?.bybit?.httpStatus)!==429)throw e;}
    }
    if(lastErr?.bybit)lastErr.bybit.attemptedBases=[...attempted];throw lastErr;
  }
  async function signedViaVpsOnce(method,path,paramsOrBody={}){
    if(!(c.apiKey&&c.apiSecret))throw new Error("BYBIT_CREDENTIALS_MISSING");
    if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=="function")throw new Error("BYBIT_VPS_BRIDGE_BINDING_MISSING");
    const secret=bridgeSecret(env);
    if(!secret)throw new Error("BYBIT_VPS_BRIDGE_SECRET_MISSING");
    const upper=String(method).toUpperCase(),payload=upper==="GET"?qs(paramsOrBody):JSON.stringify(clean(paramsOrBody));
    const ts=String(Date.now()),sig=await hmacHex(c.apiSecret,ts+c.apiKey+recvWindow+payload);
    const headers={"X-BAPI-API-KEY":c.apiKey,"X-BAPI-TIMESTAMP":ts,"X-BAPI-RECV-WINDOW":recvWindow,"X-BAPI-SIGN":sig,"Content-Type":"application/json","Accept":"application/json","X-Trading-Runtime-Contract":BYBIT_RUNTIME_CONTRACT_VERSION};
    const requestBody={method:upper,path,query:upper==="GET"?payload:"",body:upper==="GET"?"":payload,headers};
    let r,j;
    try{
      r=await env.AI_BRIDGE.fetch(new Request(BRIDGE_PRIVATE_URL,{method:"POST",headers:{"content-type":"application/json","accept":"application/json","authorization":"Bearer "+secret,"x-trading-runtime-contract":BYBIT_RUNTIME_CONTRACT_VERSION},body:JSON.stringify(requestBody),signal:AbortSignal.timeout(BRIDGE_TIMEOUT_MS)}));
      j=await r.json().catch(()=>null);
    }catch(e){throw bybitError(path,502,null,{bodySnippet:"VPS bridge fetch failed: "+String(e?.message||e).slice(0,180),transport:BYBIT_PRIVATE_TRANSPORT});}
    if(!r.ok||!j)throw bybitError(path,r?.status||502,j?.upstream||null,{bodySnippet:j?.error||"VPS bridge invalid response",transport:j?.transport||BYBIT_PRIVATE_TRANSPORT,attemptedBases:j?.attempts||[]});
    const up=j.upstream||null,status=Number(j.httpStatus||0)||502,transport=j.transport||BYBIT_PRIVATE_TRANSPORT;
    if(!j.ok||Number(up?.retCode)!==0)throw bybitError(path,status,up,{base:j.base||null,attemptedBases:j.attempts||[],transport});
    return up;
  }
  async function signedViaVps(method,path,paramsOrBody={}){
    const upper=String(method).toUpperCase();
    if(upper!=="GET")return signedViaVpsOnce(upper,path,paramsOrBody);
    let last;
    for(let attempt=0;attempt<2;attempt++){
      try{return await signedViaVpsOnce(upper,path,paramsOrBody);}catch(e){last=e;if(attempt===1||!retryableReadError(e))throw e;await sleep(250+attempt*250);}
    }
    throw last;
  }
  async function market(path,params={}){
    if(demo)return pub(path,params);
    try{return await signedViaVps("GET",path,params);}
    catch(vpsError){
      if(String(env.BYBIT_ALLOW_DIRECT_PUBLIC_FALLBACK||"").toLowerCase()==="true"){
        try{return await pub(path,params);}catch(directError){directError.cause=vpsError;throw directError;}
      }
      throw vpsError;
    }
  }
  async function signedDirect(method,path,paramsOrBody={}){
    if(!(c.apiKey&&c.apiSecret))throw new Error("BYBIT_CREDENTIALS_MISSING");
    const upper=String(method).toUpperCase(),payload=upper==="GET"?qs(paramsOrBody):JSON.stringify(clean(paramsOrBody)),attempted=[];let lastErr;
    for(const base of baseList){
      attempted.push(base);
      try{
        const ts=String(Date.now()),sig=await hmacHex(c.apiSecret,ts+c.apiKey+recvWindow+payload),url=`${base}${path}${upper==="GET"&&payload?`?${payload}`:""}`;
        const r=await fetch(url,{method:upper,headers:{"X-BAPI-API-KEY":c.apiKey,"X-BAPI-TIMESTAMP":ts,"X-BAPI-RECV-WINDOW":recvWindow,"X-BAPI-SIGN":sig,"Content-Type":"application/json",accept:"application/json","X-Trading-Runtime-Contract":BYBIT_RUNTIME_CONTRACT_VERSION},body:upper==="GET"?undefined:payload,signal:AbortSignal.timeout(BRIDGE_TIMEOUT_MS)});
        return await parseResponse(r,path,{base,attemptedBases:[...attempted],transport:"CLOUDFLARE_PRIVATE_DIRECT"});
      }catch(e){lastErr=e;if(Number(e?.bybit?.httpStatus)!==403&&Number(e?.bybit?.httpStatus)!==429)throw e;}
    }
    if(lastErr?.bybit)lastErr.bybit.attemptedBases=[...attempted];throw lastErr;
  }
  async function signed(method,path,paramsOrBody={}){
    if(demo)return signedDirect(method,path,paramsOrBody);
    try{return await signedViaVps(method,path,paramsOrBody);}
    catch(e){
      if(String(env.BYBIT_ALLOW_DIRECT_PRIVATE_FALLBACK||"").toLowerCase()==="true")return signedDirect(method,path,paramsOrBody);
      throw e;
    }
  }
  async function setLeverage(symbol,leverage){
    try{return await signed("POST","/v5/position/set-leverage",{category:"linear",symbol,buyLeverage:String(leverage),sellLeverage:String(leverage)});}
    catch(e){
      if(Number(e?.bybit?.retCode)===110043||unchangedWrite(e))return {retCode:0,retMsg:"LEVERAGE_UNCHANGED",result:{},idempotent:true,requestedLeverage:Number(leverage)};
      throw e;
    }
  }
  async function tradingStop(body={}){
    try{return await signed("POST","/v5/position/trading-stop",{category:"linear",...body});}
    catch(e){
      if(unchangedWrite(e))return {retCode:0,retMsg:"TRADING_STOP_UNCHANGED",result:{},idempotent:true,requested:{...body}};
      throw e;
    }
  }
  async function createOrder(body={}){
    const reduceOnly=body.reduceOnly===true||String(body.closeOnTrigger||"").toLowerCase()==="true";
    const enriched={category:"linear",...body};
    if(!reduceOnly){
      const side=String(body.side||"");
      const p=await signed("GET","/v5/position/list",{category:"linear",settleCoin:"USDT",limit:200});
      const rows=p?.result?.list||[],sameDirectionCount=rows.filter(x=>Number(x?.size||0)>0&&String(x?.side||"")===side).length;
      const maxSameDirection=Math.max(1,Number(cfg?.risk?.maxSameDirectionPositions||3));
      if(side&&sameDirectionCount>=maxSameDirection){
        const e=new Error(`SAME_DIRECTION_EXPOSURE_CAP: ${side} ${sameDirectionCount}/${maxSameDirection}`);
        e.bybit={path:"LOCAL_ORDER_PREFLIGHT",httpStatus:0,retCode:null,retMsg:"SAME_DIRECTION_EXPOSURE_CAP",transport:"LOCAL_FAIL_CLOSED",runtimeContract:BYBIT_RUNTIME_CONTRACT_VERSION};
        throw e;
      }
      if(!enriched.orderLinkId)enriched.orderLinkId=entryOrderLinkId(enriched);
    }
    return signed("POST","/v5/order/create",enriched);
  }
  return {
    credentialSource:c.source,credentialsPresent:!!(c.apiKey&&c.apiSecret),bases:baseList,privateTransport:demo?"CLOUDFLARE_BYBIT_DEMO_DIRECT":BYBIT_PRIVATE_TRANSPORT,marketTransport:demo?"CLOUDFLARE_BYBIT_DEMO_PUBLIC":BYBIT_MARKET_TRANSPORT,runtimeContract:BYBIT_RUNTIME_CONTRACT_VERSION,recvWindowMs:Number(recvWindow),
    serverTime:()=>market("/v5/market/time"),
    wallet:()=>signed("GET","/v5/account/wallet-balance",{accountType:"UNIFIED",coin:"USDT"}),
    positions:()=>signed("GET","/v5/position/list",{category:"linear",settleCoin:"USDT",limit:200}),
    openOrders:()=>signed("GET","/v5/order/realtime",{category:"linear",settleCoin:"USDT",openOnly:0,limit:50}),
    closedPnl:(startTime,endTime,cursor="")=>signed("GET","/v5/position/closed-pnl",{category:"linear",startTime,endTime,limit:100,cursor}),
    instruments:(cursor="")=>market("/v5/market/instruments-info",{category:"linear",limit:1000,cursor}),
    tickers:()=>market("/v5/market/tickers",{category:"linear"}),
    kline:(symbol,interval="1",limit=200)=>market("/v5/market/kline",{category:"linear",symbol,interval,limit}),
    klineRange:(symbol,{interval="1",start,end,limit=200}={})=>market("/v5/market/kline",{category:"linear",symbol,interval,start,end,limit}),
    ticker:(symbol)=>market("/v5/market/tickers",{category:"linear",symbol}),
    order:createOrder,
    orderStatus:(symbol,orderId)=>signed("GET","/v5/order/realtime",{category:"linear",symbol,orderId,limit:1}),
    setLeverage,
    tradingStop,
    cancelAll:(symbol)=>signed("POST","/v5/order/cancel-all",{category:"linear",symbol}),
    public:pub,market,signed
  };
}
export function normalizeBybitFilter(x={}){const lot=x.lotSizeFilter||{},price=x.priceFilter||{},lev=x.leverageFilter||{};return {symbol:x.symbol,status:x.status,contractType:x.contractType,settleCoin:x.settleCoin,minQty:Number(lot.minOrderQty||0),maxQty:Number(lot.maxOrderQty||0),qtyStep:Number(lot.qtyStep||0),minNotional:Number(lot.minNotionalValue||5),tickSize:Number(price.tickSize||0),minLeverage:Number(lev.minLeverage||1),maxLeverage:Number(lev.maxLeverage||0),leverageStep:Number(lev.leverageStep||1)};}
export function floorStep(v,step){if(!(step>0))return Number(v);return Math.floor((Number(v)+1e-12)/step)*step;}
export function roundTick(v,tick){if(!(tick>0))return Number(v);return Math.round(Number(v)/tick)*tick;}
