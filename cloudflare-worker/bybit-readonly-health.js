import {bybitV5} from "./bybit-v5-client.js";
import {bybitCredentials,bybitExecutionMode} from "./bybit-auto-config.js";
import {BYBIT_RUNTIME_CONTRACT,BYBIT_AUTO_VERSION} from "./bybit-runtime-contract.js";
import {BYBIT_AI_LEGION_VERSION,bybitAiLegionPolicy,getBybitAiLegionState} from "./bybit-ai-legion.js";
import {btcMicrostructureHealth} from "./bybit-btc-microstructure-client.js";

const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
const on=v=>String(v||"").toLowerCase()==="true";
const authFailure=e=>[10003,10004,10005,10007].includes(Number(e?.bybit?.retCode))||[401].includes(Number(e?.bybit?.httpStatus));

export async function handleBybitReadonlyHealth(req,env){
  const u=new URL(req.url);
  if(u.pathname!=="/bybit/health")return null;
  if(req.method!=="GET")return json({ok:false,reason:"METHOD_NOT_ALLOWED"},405);

  const creds=bybitCredentials(env),mode=bybitExecutionMode(env),api=bybitV5(env),liveAck=on(env.BYBIT_BTC_LIVE_ACK),enabled=on(env.BYBIT_AUTO_ENABLED),demo=on(env.BYBIT_AUTO_DEMO),runtimeRevision=String(env.RUNTIME_REVISION||"UNKNOWN"),aiPolicy=bybitAiLegionPolicy(env,mode),aiState=await getBybitAiLegionState(env);
  const privateTransport=api.privateTransport||"UNKNOWN",marketTransport=api.marketTransport||"UNKNOWN",expectedPrivateTransport=demo?"CLOUDFLARE_BYBIT_DEMO_DIRECT":"CLOUDFLARE_BYBIT_PRIVATE_DIRECT",expectedMarketTransport="CLOUDFLARE_BYBIT_PUBLIC_DIRECT",contractAligned=privateTransport===expectedPrivateTransport&&marketTransport===expectedMarketTransport&&api.runtimeContract===BYBIT_RUNTIME_CONTRACT.version;
  const microstructure=await btcMicrostructureHealth(env).catch(error=>({ok:false,connected:false,lastError:String(error?.message||error).slice(0,180)}));
  const contract={...BYBIT_RUNTIME_CONTRACT,aligned:contractAligned,clientContract:api.runtimeContract||null,environment:demo?"DEMO":"LIVE",expectedPrivateTransport,expectedMarketTransport,cloudMarketStream:microstructure};
  const execution={liveAck,enabled,scheduled:false,eventDriven:true,ready:false,decisionAuthority:"CLOUD_BYBIT_WS_STATE_CHANGE",entryTriggerAuthority:"CLOUD_BYBIT_WS_SIGNIFICANT_STATE_CHANGE",aiLegion:{version:BYBIT_AI_LEGION_VERSION,policy:aiPolicy,status:aiState?.status||"NO_SNAPSHOT",approved:aiState?.approved===true,reason:aiState?.reason||null,executionAction:aiState?.executionAction||"HOLD",updatedAt:aiState?.updatedAt||null}};

  if(!(creds.apiKey&&creds.apiSecret))return json({ok:false,readOnly:true,authenticated:false,exchange:"BYBIT",version:BYBIT_AUTO_VERSION,mode,environment:demo?"DEMO":"LIVE",demo,runtimeRevision,runtimeContract:contract,privateTransport,marketTransport,apiBase:api.bases?.[0]||null,execution,reason:"BYBIT_CREDENTIALS_MISSING",credentialsPresent:false,credentialSource:creds.source,blockers:["BYBIT_CREDENTIALS_MISSING"]},503);

  if(!contractAligned)return json({ok:false,readOnly:true,authenticated:null,exchange:"BYBIT",version:BYBIT_AUTO_VERSION,mode,environment:demo?"DEMO":"LIVE",demo,runtimeRevision,runtimeContract:contract,privateTransport,marketTransport,apiBase:api.bases?.[0]||null,execution,reason:"BYBIT_RUNTIME_CONTRACT_MISMATCH",credentialSource:creds.source,blockers:["BYBIT_RUNTIME_CONTRACT_MISMATCH"]},503);

  try{
    const [wallet,positions,orders]=await Promise.all([api.wallet(),api.positions(),api.openOrders()]);
    const acct=wallet?.result?.list?.[0]||{},coin=(acct.coin||[]).find(x=>x.coin==="USDT")||{},pos=(positions?.result?.list||[]).filter(x=>Number(x.size||0)>0),open=(orders?.result?.list||[]).filter(x=>!["Filled","Cancelled","Rejected","Deactivated"].includes(String(x.orderStatus)));
    let serverTimeMs=Date.now(),serverTimeTransport="EDGE_CLOCK",marketClockOk=false,marketClockError=null;
    try{
      const serverTime=await api.serverTime();
      const parsed=Number(serverTime?.time||serverTime?.result?.timeSecond)*((serverTime?.result?.timeSecond&&!serverTime?.time)?1000:1);
      if(Number.isFinite(parsed)&&parsed>0){serverTimeMs=parsed;serverTimeTransport=serverTime?.fallback?"EDGE_CLOCK":marketTransport;marketClockOk=!serverTime?.fallback;marketClockError=serverTime?.upstreamError||null;}
    }catch(error){marketClockError=String(error?.message||error).slice(0,180);}

    const blockers=[];
    if(!enabled)blockers.push("BYBIT_ENGINE_DISABLED");
    if(!microstructure?.connected)blockers.push("CLOUD_MARKET_STREAM_NOT_CONNECTED");
    if(mode==="BLOCKED")blockers.push("DEMO_LIVE_MODE_CONFLICT");
    if(mode==="LIVE"&&!liveAck)blockers.push("LIVE_ACK_MISSING");
    if(mode==="LIVE"&&aiPolicy.liveActivationRequired&&!aiPolicy.liveActivationPresent)blockers.push("AI_LEGION_LIVE_ACK_MISSING");
    if(!aiPolicy.modelMeshEnabled)blockers.push("MODEL_MESH_EXECUTION_DISABLED");
    execution.ready=blockers.length===0&&(mode==="LIVE"||mode==="DEMO");

    return json({ok:true,readOnly:true,authenticated:true,exchange:"BYBIT",version:BYBIT_AUTO_VERSION,mode,environment:demo?"DEMO":"LIVE",demo,runtimeRevision,runtimeContract:contract,privateTransport,marketTransport,apiBase:api.bases?.[0]||null,publicBases:api.publicBases||[],credentialSource:creds.source,execution,blockers,marketData:{websocketConnected:microstructure?.connected===true,messageAgeMs:microstructure?.messageAgeMs??null,publicRestClockOk:marketClockOk,clockDegraded:!marketClockOk,clockError:marketClockError},account:{totalEquity:Number(acct.totalEquity||coin.equity||0),walletBalance:Number(acct.totalWalletBalance||coin.walletBalance||0),availableBalance:Number(acct.totalAvailableBalance||coin.availableToWithdraw||0)},positions:{openCount:pos.length,items:pos.slice(0,20).map(x=>({symbol:x.symbol,side:x.side,size:Number(x.size),avgPrice:Number(x.avgPrice),markPrice:Number(x.markPrice),stopLoss:Number(x.stopLoss||0),takeProfit:Number(x.takeProfit||0),unrealisedPnl:Number(x.unrealisedPnl),leverage:Number(x.leverage)}))},openOrdersCount:open.length,healthTransportVerified:privateTransport,marketTransportVerified:marketTransport,serverTime:{ms:serverTimeMs,transport:serverTimeTransport},checkedAt:new Date().toISOString(),guarantees:["HEALTH_PRIVATE_READS_ARE_CRITICAL","PUBLIC_REST_CLOCK_FAILURE_DOES_NOT_CRASH_HEALTH","CLOUD_WS_IS_PRIMARY_MARKET_TRIGGER","ONE_AI_EXECUTION_COMMANDER_ACTIVE","OTHER_AI_AGENTS_RESEARCH_ONLY","SIGNED_WRITES_REQUIRE_STATEFLOW_RISK_GATE","NO_CRON_EXECUTION_AUTHORITY"]});
  }catch(e){
    const b=e?.bybit||{},auth=authFailure(e)?false:null;
    return json({ok:false,readOnly:true,authenticated:auth,exchange:"BYBIT",version:BYBIT_AUTO_VERSION,mode,environment:demo?"DEMO":"LIVE",demo,runtimeRevision,runtimeContract:contract,privateTransport,marketTransport,apiBase:api.bases?.[0]||null,execution,credentialSource:creds.source,reason:"BYBIT_PRIVATE_READ_UNAVAILABLE",blockers:["BYBIT_PRIVATE_READ_UNAVAILABLE"],bybit:{path:b.path||null,httpStatus:b.httpStatus??null,retCode:b.retCode??null,retMsg:b.retMsg||String(e?.message||e).slice(0,300),transport:b.transport||null,base:b.base||null,attemptedBases:b.attemptedBases||[]},checkedAt:new Date().toISOString()},503);
  }
}
