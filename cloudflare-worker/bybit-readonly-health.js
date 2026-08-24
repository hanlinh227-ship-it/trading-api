import {bybitV5} from "./bybit-v5-client.js";
import {bybitCredentials,bybitExecutionMode} from "./bybit-auto-config.js";

const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
const on=v=>String(v||"").toLowerCase()==="true";
export async function handleBybitReadonlyHealth(req,env){
  const u=new URL(req.url);if(u.pathname!=="/bybit/health")return null;if(req.method!=="GET")return json({ok:false,reason:"METHOD_NOT_ALLOWED"},405);
  const creds=bybitCredentials(env),mode=bybitExecutionMode(env),api=bybitV5(env),liveAck=on(env.BYBIT_AUTO_LIVE_ACK),scheduled=on(env.BYBIT_AUTO_ENABLED),runtimeRevision=String(env.RUNTIME_REVISION||"UNKNOWN");
  const privateTransport=api.privateTransport||"UNKNOWN";
  if(!(creds.apiKey&&creds.apiSecret))return json({ok:false,readOnly:true,authenticated:false,exchange:"BYBIT",mode,runtimeRevision,privateTransport,execution:{liveAck,scheduled,ready:false},reason:"BYBIT_CREDENTIALS_MISSING",credentialsPresent:false,credentialSource:creds.source},503);
  try{
    const [wallet,positions,orders,time]=await Promise.all([api.wallet(),api.positions(),api.openOrders(),api.serverTime()]);
    const acct=wallet?.result?.list?.[0]||{},coin=(acct.coin||[]).find(x=>x.coin==="USDT")||{},pos=(positions?.result?.list||[]).filter(x=>Number(x.size||0)>0),open=(orders?.result?.list||[]).filter(x=>!["Filled","Cancelled","Rejected","Deactivated"].includes(String(x.orderStatus)));
    const ready=mode==="LIVE"&&liveAck&&scheduled;
    return json({ok:true,readOnly:true,authenticated:true,exchange:"BYBIT",mode,runtimeRevision,privateTransport,credentialSource:creds.source,execution:{liveAck,scheduled,ready},account:{totalEquity:Number(acct.totalEquity||coin.equity||0),walletBalance:Number(acct.totalWalletBalance||coin.walletBalance||0),availableBalance:Number(acct.totalAvailableBalance||coin.availableToWithdraw||0)},positions:{openCount:pos.length,items:pos.slice(0,20).map(x=>({symbol:x.symbol,side:x.side,size:Number(x.size),avgPrice:Number(x.avgPrice),markPrice:Number(x.markPrice),unrealisedPnl:Number(x.unrealisedPnl),leverage:Number(x.leverage)}))},openOrdersCount:open.length,serverTime:time?.time||null,checkedAt:new Date().toISOString(),guarantees:["THIS_HEALTH_REQUEST_DOES_NOT_SUBMIT_ORDERS","THIS_HEALTH_REQUEST_DOES_NOT_CHANGE_LEVERAGE","THIS_HEALTH_REQUEST_DOES_NOT_CANCEL"]});
  }catch(e){const b=e?.bybit||{};return json({ok:false,readOnly:true,authenticated:false,exchange:"BYBIT",mode,runtimeRevision,privateTransport,execution:{liveAck,scheduled,ready:false},credentialSource:creds.source,reason:"BYBIT_READONLY_HEALTH_FAILED",bybit:{path:b.path||null,httpStatus:b.httpStatus??null,retCode:b.retCode??null,retMsg:b.retMsg||String(e?.message||e).slice(0,300),transport:b.transport||privateTransport,base:b.base||null,attemptedBases:b.attemptedBases||[]},checkedAt:new Date().toISOString()},502);}
}
