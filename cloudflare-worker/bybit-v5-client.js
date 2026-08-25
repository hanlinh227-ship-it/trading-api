import {hmacHex} from "./providers/bybit-signed-client.js";
import {bybitCredentials} from "./bybit-auto-config.js";

const DEFAULT_BASES=["https://api.bybit.com","https://api.bytick.com"];
const RECV_WINDOW="5000";
const clean=o=>Object.fromEntries(Object.entries(o||{}).filter(([,v])=>v!==undefined&&v!==null&&v!==""));
const qs=o=>new URLSearchParams(Object.entries(clean(o)).map(([k,v])=>[k,String(v)])).toString();
function bases(env={}){
  const preferred=String(env.BYBIT_API_BASE_URL||"").trim().replace(/\/$/,"");
  return [...new Set([preferred,...DEFAULT_BASES].filter(Boolean))];
}
function bybitError(path,status,p,meta={}){const msg=p?.retMsg||meta.bodySnippet||`HTTP ${status}`;const e=new Error(`${path}: ${msg}`);e.bybit={path,httpStatus:status,retCode:Number.isFinite(Number(p?.retCode))?Number(p.retCode):null,retMsg:p?.retMsg||null,base:meta.base||null,attemptedBases:meta.attemptedBases||[],bodySnippet:meta.bodySnippet||null,transport:meta.transport||null};return e;}
async function parseResponse(r,path,meta={}){
  const text=await r.text();let p=null;try{p=text?JSON.parse(text):null;}catch{}
  const bodySnippet=!p&&text?String(text).replace(/\s+/g," ").slice(0,240):null;
  if(!r.ok||Number(p?.retCode)!==0)throw bybitError(path,r.status,p,{...meta,bodySnippet});
  return p;
}
export function bybitV5(env={}){
  const c=bybitCredentials(env),baseList=bases(env);
  async function pub(path,params={}){
    const q=qs(params),attempted=[];let lastErr;
    for(const base of baseList){
      attempted.push(base);
      try{const url=`${base}${path}${q?`?${q}`:""}`;const r=await fetch(url,{headers:{accept:"application/json"}});return await parseResponse(r,path,{base,attemptedBases:[...attempted],transport:"CLOUDFLARE_PUBLIC_DIRECT"});}
      catch(e){lastErr=e;if(Number(e?.bybit?.httpStatus)!==403)throw e;}
    }
    if(lastErr?.bybit)lastErr.bybit.attemptedBases=[...attempted];throw lastErr;
  }
  async function signedViaVps(method,path,paramsOrBody={}){
    if(!(c.apiKey&&c.apiSecret))throw new Error("BYBIT_CREDENTIALS_MISSING");
    if(!env.AI_BRIDGE||typeof env.AI_BRIDGE.fetch!=="function")throw new Error("BYBIT_VPS_BRIDGE_BINDING_MISSING");
    const bridgeSecret=String(env.V11_AI_BRIDGE_SECRET||"");
    if(!bridgeSecret)throw new Error("BYBIT_VPS_BRIDGE_SECRET_MISSING");
    const upper=String(method).toUpperCase(),payload=upper==="GET"?qs(paramsOrBody):JSON.stringify(clean(paramsOrBody));
    const ts=String(Date.now()),sig=await hmacHex(c.apiSecret,ts+c.apiKey+RECV_WINDOW+payload);
    const headers={"X-BAPI-API-KEY":c.apiKey,"X-BAPI-TIMESTAMP":ts,"X-BAPI-RECV-WINDOW":RECV_WINDOW,"X-BAPI-SIGN":sig,"Content-Type":"application/json","Accept":"application/json"};
    const requestBody={method:upper,path,query:upper==="GET"?payload:"",body:upper==="GET"?"":payload,headers};
    let r,j;
    try{
      r=await env.AI_BRIDGE.fetch(new Request("http://127.0.0.1:8789/bybit/private",{method:"POST",headers:{"content-type":"application/json","accept":"application/json","authorization":"Bearer "+bridgeSecret},body:JSON.stringify(requestBody),signal:AbortSignal.timeout(20000)}));
      j=await r.json().catch(()=>null);
    }catch(e){throw bybitError(path,502,null,{bodySnippet:"VPS bridge fetch failed: "+String(e?.message||e).slice(0,180),transport:"VPS_BYBIT_PRIVATE_PROXY"});}
    if(!r.ok||!j)throw bybitError(path,r?.status||502,j?.upstream||null,{bodySnippet:j?.error||"VPS bridge invalid response",transport:"VPS_BYBIT_PRIVATE_PROXY",attemptedBases:j?.attempts||[]});
    const up=j.upstream||null,status=Number(j.httpStatus||0)||502;
    if(!j.ok||Number(up?.retCode)!==0)throw bybitError(path,status,up,{base:j.base||null,attemptedBases:j.attempts||[],transport:"VPS_BYBIT_PRIVATE_PROXY"});
    return up;
  }
  async function market(path,params={}){
    try{return await signedViaVps("GET",path,params);}
    catch(vpsError){
      if(String(env.BYBIT_ALLOW_DIRECT_PUBLIC_FALLBACK??"true").toLowerCase()==="true"){
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
        const ts=String(Date.now()),sig=await hmacHex(c.apiSecret,ts+c.apiKey+RECV_WINDOW+payload),url=`${base}${path}${upper==="GET"&&payload?`?${payload}`:""}`;
        const r=await fetch(url,{method:upper,headers:{"X-BAPI-API-KEY":c.apiKey,"X-BAPI-TIMESTAMP":ts,"X-BAPI-RECV-WINDOW":RECV_WINDOW,"X-BAPI-SIGN":sig,"Content-Type":"application/json",accept:"application/json"},body:upper==="GET"?undefined:payload});
        return await parseResponse(r,path,{base,attemptedBases:[...attempted],transport:"CLOUDFLARE_PRIVATE_DIRECT"});
      }catch(e){lastErr=e;if(Number(e?.bybit?.httpStatus)!==403)throw e;}
    }
    if(lastErr?.bybit)lastErr.bybit.attemptedBases=[...attempted];throw lastErr;
  }
  async function signed(method,path,paramsOrBody={}){
    try{return await signedViaVps(method,path,paramsOrBody);}
    catch(e){
      if(String(env.BYBIT_ALLOW_DIRECT_PRIVATE_FALLBACK||"").toLowerCase()==="true")return signedDirect(method,path,paramsOrBody);
      throw e;
    }
  }
  async function setLeverage(symbol,leverage){
    try{return await signed("POST","/v5/position/set-leverage",{category:"linear",symbol,buyLeverage:String(leverage),sellLeverage:String(leverage)});}
    catch(e){
      if(Number(e?.bybit?.retCode)===110043)return {retCode:0,retMsg:"LEVERAGE_UNCHANGED",result:{},idempotent:true,requestedLeverage:Number(leverage)};
      throw e;
    }
  }
  return {
    credentialSource:c.source,credentialsPresent:!!(c.apiKey&&c.apiSecret),bases:baseList,privateTransport:"VPS_BYBIT_PRIVATE_PROXY",marketTransport:"VPS_BYBIT_MARKET_PROXY",
    serverTime:()=>market("/v5/market/time"),
    wallet:()=>signed("GET","/v5/account/wallet-balance",{accountType:"UNIFIED",coin:"USDT"}),
    positions:()=>signed("GET","/v5/position/list",{category:"linear",settleCoin:"USDT",limit:200}),
    openOrders:()=>signed("GET","/v5/order/realtime",{category:"linear",settleCoin:"USDT",openOnly:0,limit:50}),
    closedPnl:(startTime,endTime)=>signed("GET","/v5/position/closed-pnl",{category:"linear",startTime,endTime,limit:100}),
    instruments:(cursor="")=>market("/v5/market/instruments-info",{category:"linear",limit:1000,cursor}),
    tickers:()=>market("/v5/market/tickers",{category:"linear"}),
    kline:(symbol,interval="1",limit=200)=>market("/v5/market/kline",{category:"linear",symbol,interval,limit}),
    klineRange:(symbol,{interval="1",start,end,limit=200}={})=>market("/v5/market/kline",{category:"linear",symbol,interval,start,end,limit}),
    ticker:(symbol)=>market("/v5/market/tickers",{category:"linear",symbol}),
    order:body=>signed("POST","/v5/order/create",{category:"linear",...body}),
    orderStatus:(symbol,orderId)=>signed("GET","/v5/order/realtime",{category:"linear",symbol,orderId,limit:1}),
    setLeverage,
    tradingStop:(body)=>signed("POST","/v5/position/trading-stop",{category:"linear",...body}),
    cancelAll:(symbol)=>signed("POST","/v5/order/cancel-all",{category:"linear",symbol}),
    public:pub,market,signed
  };
}
export function normalizeBybitFilter(x={}){const lot=x.lotSizeFilter||{},price=x.priceFilter||{},lev=x.leverageFilter||{};return {symbol:x.symbol,status:x.status,contractType:x.contractType,settleCoin:x.settleCoin,minQty:Number(lot.minOrderQty||0),maxQty:Number(lot.maxOrderQty||0),qtyStep:Number(lot.qtyStep||0),minNotional:Number(lot.minNotionalValue||5),tickSize:Number(price.tickSize||0),minLeverage:Number(lev.minLeverage||1),maxLeverage:Number(lev.maxLeverage||0),leverageStep:Number(lev.leverageStep||1)};}
export function floorStep(v,step){if(!(step>0))return Number(v);return Math.floor((Number(v)+1e-12)/step)*step;}
export function roundTick(v,tick){if(!(tick>0))return Number(v);return Math.round(Number(v)/tick)*tick;}