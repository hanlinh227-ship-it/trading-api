// ============================================================================
// NON_PRODUCTION / QUARANTINED — see docs/ai-coengineer/DECISIONS.md DECISION-005
//
// This module is NOT part of current production execution authority. It is
// not imported by cloudflare-worker/index.js, hub-v77171.js, or
// engine-v77168.js and has no wired route, scheduled handler, or active
// credential binding in the production Worker entrypoint chain.
//
// Do NOT delete this file. Do NOT wire it into a production path without an
// explicit reviewed decision (V78-090) promoting it to a real
// AccountAdapter/ExecutionVenue pilot per
// docs/ai-coengineer/V78_SYSTEM_REDESIGN_MANDATE.md.
//
// Reference: docs/ai-coengineer/DECISIONS.md DECISION-005,
//            docs/ai-coengineer/V78_KV_KEY_REGISTRY.md Section 12,
//            docs/ai-coengineer/V78_EXECUTION_AUTHORITY_MAP.md Section 3.
// ============================================================================

const enc=new TextEncoder();
async function hmac(secret,msg){const key=await crypto.subtle.importKey("raw",enc.encode(secret),{name:"HMAC",hash:"SHA-256"},false,["sign"]);const sig=await crypto.subtle.sign("HMAC",key,enc.encode(msg));return [...new Uint8Array(sig)].map(b=>b.toString(16).padStart(2,"0")).join("");}
export function binanceUsdm(env={}){const base=String(env.BINANCE_FUTURES_BASE_URL||"https://fapi.binance.com").replace(/\/$/,""),apiKey=env.BINANCE_FUTURES_API_KEY||"",secret=env.BINANCE_FUTURES_API_SECRET||"";async function req(path,{method="GET",params={},signed=false}={}){const p=new URLSearchParams();for(const [k,v] of Object.entries(params))if(v!==undefined&&v!==null)p.set(k,String(v));if(signed){if(!apiKey||!secret)throw new Error("BINANCE_FUTURES_CREDENTIALS_MISSING");p.set("timestamp",String(Date.now()));p.set("recvWindow",String(params.recvWindow||5000));p.set("signature",await hmac(secret,p.toString()));}const url=`${base}${path}${p.toString()?`?${p}`:""}`;const r=await fetch(url,{method,headers:apiKey?{"X-MBX-APIKEY":apiKey}:{}}),j=await r.json().catch(()=>null);if(!r.ok||j?.code<0)throw new Error(`BINANCE_${j?.code||r.status}:${j?.msg||"request failed"}`);return j;}
return {exchangeInfo:()=>req("/fapi/v1/exchangeInfo"),klines:(symbol,interval="1m",limit=120)=>req("/fapi/v1/klines",{params:{symbol,interval,limit}}),bookTicker:symbol=>req("/fapi/v1/ticker/bookTicker",{params:{symbol}}),markPrice:symbol=>req("/fapi/v1/premiumIndex",{params:{symbol}}),account:()=>req("/fapi/v3/account",{signed:true}),positions:()=>req("/fapi/v3/positionRisk",{signed:true}),setLeverage:(symbol,leverage)=>req("/fapi/v1/leverage",{method:"POST",signed:true,params:{symbol,leverage}}),setMarginType:(symbol,marginType)=>req("/fapi/v1/marginType",{method:"POST",signed:true,params:{symbol,marginType}}),order:params=>req("/fapi/v1/order",{method:"POST",signed:true,params}),cancelAll:symbol=>req("/fapi/v1/allOpenOrders",{method:"DELETE",signed:true,params:{symbol}})};}
export function symbolFilters(exchangeInfo,symbol){const s=exchangeInfo?.symbols?.find(x=>x.symbol===symbol);if(!s)return null;const f=Object.fromEntries((s.filters||[]).map(x=>[x.filterType,x]));return {status:s.status,contractType:s.contractType,pricePrecision:s.pricePrecision,quantityPrecision:s.quantityPrecision,tickSize:Number(f.PRICE_FILTER?.tickSize||0),stepSize:Number(f.LOT_SIZE?.stepSize||0),marketStepSize:Number(f.MARKET_LOT_SIZE?.stepSize||f.LOT_SIZE?.stepSize||0),minQty:Number(f.LOT_SIZE?.minQty||0),minNotional:Number(f.MIN_NOTIONAL?.notional||5)};}
export function floorStep(v,step){if(!(step>0))return v;return Math.floor(v/step+1e-12)*step;}
