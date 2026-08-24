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
function bybitError(path,status,p,meta={}){const msg=p?.retMsg||meta.bodySnippet||`HTTP ${status}`;const e=new Error(`${path}: ${msg}`);e.bybit={path,httpStatus:status,retCode:Number.isFinite(Number(p?.retCode))?Number(p.retCode):null,retMsg:p?.retMsg||null,base:meta.base||null,attemptedBases:meta.attemptedBases||[],bodySnippet:meta.bodySnippet||null};return e;}
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
      try{const r=await fetch(`${base}${path}${q?`?${q}`:""}`,{headers:{accept:"application/json"}});return await parseResponse(r,path,{base,attemptedBases:[...attempted]});}
      catch(e){lastErr=e;if(Number(e?.bybit?.httpStatus)!==403)throw e;}
    }
    if(lastErr?.bybit)lastErr.bybit.attemptedBases=[...attempted];throw lastErr;
  }
  async function signed(method,path,paramsOrBody={}){
    if(!(c.apiKey&&c.apiSecret))throw new Error("BYBIT_CREDENTIALS_MISSING");
    const upper=String(method).toUpperCase(),payload=upper==="GET"?qs(paramsOrBody):JSON.stringify(clean(paramsOrBody)),attempted=[];let lastErr;
    for(const base of baseList){
      attempted.push(base);
      try{
        const ts=String(Date.now()),sig=await hmacHex(c.apiSecret,ts+c.apiKey+RECV_WINDOW+payload),url=`${base}${path}${upper==="GET"&&payload?`?${payload}`:""}`;
        const r=await fetch(url,{method:upper,headers:{"X-BAPI-API-KEY":c.apiKey,"X-BAPI-TIMESTAMP":ts,"X-BAPI-RECV-WINDOW":RECV_WINDOW,"X-BAPI-SIGN":sig,"Content-Type":"application/json",accept:"application/json"},body:upper==="GET"?undefined:payload});
        return await parseResponse(r,path,{base,attemptedBases:[...attempted]});
      }catch(e){lastErr=e;if(Number(e?.bybit?.httpStatus)!==403)throw e;}
    }
    if(lastErr?.bybit)lastErr.bybit.attemptedBases=[...attempted];throw lastErr;
  }
  return {
    credentialSource:c.source,credentialsPresent:!!(c.apiKey&&c.apiSecret),bases:baseList,
    serverTime:()=>pub("/v5/market/time"),
    wallet:()=>signed("GET","/v5/account/wallet-balance",{accountType:"UNIFIED",coin:"USDT"}),
    positions:()=>signed("GET","/v5/position/list",{category:"linear",settleCoin:"USDT",limit:200}),
    openOrders:()=>signed("GET","/v5/order/realtime",{category:"linear",settleCoin:"USDT",openOnly:0,limit:50}),
    closedPnl:(startTime,endTime)=>signed("GET","/v5/position/closed-pnl",{category:"linear",startTime,endTime,limit:100}),
    instruments:(cursor="")=>pub("/v5/market/instruments-info",{category:"linear",limit:1000,cursor}),
    tickers:()=>pub("/v5/market/tickers",{category:"linear"}),
    kline:(symbol,interval="1",limit=200)=>pub("/v5/market/kline",{category:"linear",symbol,interval,limit}),
    klineRange:(symbol,{interval="1",start,end,limit=200}={})=>pub("/v5/market/kline",{category:"linear",symbol,interval,start,end,limit}),
    ticker:(symbol)=>pub("/v5/market/tickers",{category:"linear",symbol}),
    order:body=>signed("POST","/v5/order/create",{category:"linear",...body}),
    orderStatus:(symbol,orderId)=>signed("GET","/v5/order/realtime",{category:"linear",symbol,orderId,limit:1}),
    setLeverage:(symbol,leverage)=>signed("POST","/v5/position/set-leverage",{category:"linear",symbol,buyLeverage:String(leverage),sellLeverage:String(leverage)}),
    tradingStop:(body)=>signed("POST","/v5/position/trading-stop",{category:"linear",...body}),
    cancelAll:(symbol)=>signed("POST","/v5/order/cancel-all",{category:"linear",symbol}),
    public:pub,signed
  };
}
export function normalizeBybitFilter(x={}){const lot=x.lotSizeFilter||{},price=x.priceFilter||{};return {symbol:x.symbol,status:x.status,contractType:x.contractType,settleCoin:x.settleCoin,minQty:Number(lot.minOrderQty||0),maxQty:Number(lot.maxOrderQty||0),qtyStep:Number(lot.qtyStep||0),minNotional:Number(lot.minNotionalValue||5),tickSize:Number(price.tickSize||0)};}
export function floorStep(v,step){if(!(step>0))return Number(v);return Math.floor((Number(v)+1e-12)/step)*step;}
export function roundTick(v,tick){if(!(tick>0))return Number(v);return Math.round(Number(v)/tick)*tick;}
