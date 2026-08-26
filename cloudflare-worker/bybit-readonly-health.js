import {bybitV5} from "./bybit-v5-client.js";
import {bybitCredentials,bybitExecutionMode} from "./bybit-auto-config.js";
import {BYBIT_RUNTIME_CONTRACT,BYBIT_AUTO_VERSION,BYBIT_PRIVATE_TRANSPORT,BYBIT_MARKET_TRANSPORT} from "./bybit-runtime-contract.js";

const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
const on=v=>String(v||"").toLowerCase()==="true";
export async function handleBybitReadonlyHealth(req,env){
  const u=new URL(req.url);if(u.pathname!=="/bybit/health")return null;if(req.method!=="GET")return json({ok:false,reason:"METHOD_NOT_ALLOWED"},405);
  const creds=bybitCredentials(env),mode=bybitExecutionMode(env),api=bybitV5(env),liveAck=on(env.BYBIT_AUTO_LIVE_ACK),scheduled=on(env.BYBIT_AUTO_ENABLED),runtimeRevision=String(env.RUNTIME_REVISION||"UNKNOWN");
  const privateTransport=api.privateTransport||"UNKNOWN",marketTransport=api.marketTransport||"UNKNOWN",contractAligned=privateTransport===BYBIT_PRIVATE_TRANSPORT&&marketTransport===BYBIT_MARKET_TRANSPORT&&api.runtimeContract===BYBIT_RUNTIME_CONTRACT.version;
  const contract={...BYBIT_RUNTIME_CONTRACT,aligned:contractAligned,clientContract:api.runtimeContract||null};
  if(!(creds.apiKey&&creds.apiSecret))return json({ok:false,readOnly:true,authenticated:false,exchange:"BYBIT",version:BYBIT_AUTO_VERSION,mode,runtimeRevision,runtimeContract:contract,privateTransport,marketTransport,execution:{liveAck,scheduled,ready:false},reason:"BYBIT_CREDENTIALS_MISSING",credentialsPresent:false,credentialSource:creds.source},503);
  try{
    // Readiness verifies authenticated account access, exact VPS market-data path and the
    // canonical runtime contract used by every Bybit-facing server component.
    if(!contractAligned)throw new Error("BYBIT_RUNTIME_CONTRACT_MISMATCH");
    const [wallet,positions,orders,serverTime]=await Promise.all([api.wallet(),api.positions(),api.openOrders(),api.serverTime()]);
    const acct=wallet?.result?.list?.[0]||{},coin=(acct.coin||[]).find(x=>x.coin==="USDT")||{},pos=(positions?.result?.list||[]).filter(x=>Number(x.size||0)>0),open=(orders?.result?.list||[]).filter(x=>!["Filled","Cancelled","Rejected","Deactivated"].includes(String(x.orderStatus)));
    const serverTimeMs=Number(serverTime?.time||serverTime?.result?.timeSecond)*((serverTime?.result?.timeSecond&&!serverTime?.time)?1000:1);
    if(!Number.isFinite(serverTimeMs)||serverTimeMs<=0)throw new Error("BYBIT_MARKET_TIME_INVALID");
    const ready=mode==="LIVE"&&liveAck&&scheduled&&contractAligned;
    return json({ok:true,readOnly:true,authenticated:true,exchange:"BYBIT",version:BYBIT_AUTO_VERSION,mode,runtimeRevision,runtimeContract:contract,privateTransport,marketTransport,credentialSource:creds.source,execution:{liveAck,scheduled,ready},account:{totalEquity:Number(acct.totalEquity||coin.equity||0),walletBalance:Number(acct.totalWalletBalance||coin.walletBalance||0),availableBalance:Number(acct.totalAvailableBalance||coin.availableToWithdraw||0)},positions:{openCount:pos.length,items:pos.slice(0,20).map(x=>({symbol:x.symbol,side:x.side,size:Number(x.size),avgPrice:Number(x.avgPrice),markPrice:Number(x.markPrice),unrealisedPnl:Number(x.unrealisedPnl),leverage:Number(x.leverage)}))},openOrdersCount:open.length,healthTransportVerified:privateTransport,marketTransportVerified:marketTransport,serverTime:{ms:serverTimeMs,transport:marketTransport},checkedAt:new Date().toISOString(),guarantees:["THIS_HEALTH_REQUEST_DOES_NOT_SUBMIT_ORDERS","THIS_HEALTH_REQUEST_DOES_NOT_CHANGE_LEVERAGE","THIS_HEALTH_REQUEST_DOES_NOT_CANCEL","HEALTH_USES_AUTHENTICATED_VPS_PRIVATE_TRANSPORT","HEALTH_USES_VPS_MARKET_TRANSPORT","HEALTH_REQUIRES_CANONICAL_RUNTIME_CONTRACT"]});
  }catch(e){const b=e?.bybit||{};return json({ok:false,readOnly:true,authenticated:false,exchange:"BYBIT",version:BYBIT_AUTO_VERSION,mode,runtimeRevision,runtimeContract:contract,privateTransport,marketTransport,execution:{liveAck,scheduled,ready:false},credentialSource:creds.source,reason:String(e?.message||"")==="BYBIT_RUNTIME_CONTRACT_MISMATCH"?"BYBIT_RUNTIME_CONTRACT_MISMATCH":"BYBIT_READONLY_HEALTH_FAILED",bybit:{path:b.path||null,httpStatus:b.httpStatus??null,retCode:b.retCode??null,retMsg:b.retMsg||String(e?.message||e).slice(0,300),transport:b.transport||null,base:b.base||null,attemptedBases:b.attemptedBases||[]},checkedAt:new Date().toISOString()},502);}
}
