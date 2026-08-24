function json(body,status=200){return new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});}
function envBool(v){return String(v||"").toLowerCase()==="true";}

export async function handleBinanceReadonlyHealth(req,env){
  let url;
  try{url=new URL(req.url);}catch{return null;}
  if(url.pathname!=="/binance/health")return null;
  if(req.method!=="GET")return json({ok:false,reason:"METHOD_NOT_ALLOWED",allowed:["GET"]},405);

  const live=envBool(env.BINANCE_AUTO_LIVE),liveAck=envBool(env.BINANCE_AUTO_LIVE_ACK),testnet=envBool(env.BINANCE_AUTO_TESTNET);
  const bridgeSecretPresent=!!env.BINANCE_BRIDGE_SECRET;
  const vpcPresent=!!env.AI_BRIDGE&&typeof env.AI_BRIDGE.fetch==="function";

  if(!bridgeSecretPresent)return json({ok:false,readOnly:true,authenticated:false,via:"VPS_BRIDGE",reason:"BINANCE_BRIDGE_SECRET_MISSING",mode:{live,liveAck,testnet},bridge:{vpcPresent,bridgeSecretPresent}},503);
  if(!vpcPresent)return json({ok:false,readOnly:true,authenticated:false,via:"VPS_BRIDGE",reason:"BINANCE_VPC_BINDING_MISSING",mode:{live,liveAck,testnet},bridge:{vpcPresent,bridgeSecretPresent}},503);

  try{
    const r=await env.AI_BRIDGE.fetch(new Request("http://127.0.0.1:8790/binance/health",{
      method:"GET",
      headers:{"authorization":"Bearer "+String(env.BINANCE_BRIDGE_SECRET),"accept":"application/json"}
    }));
    const text=await r.text();
    let payload={};
    try{payload=text?JSON.parse(text):{};}catch{payload={ok:false,reason:"BINANCE_VPS_BRIDGE_NON_JSON"};}
    const normalized={
      ...payload,
      ok:payload?.ok===true,
      authenticated:payload?.authenticated===true,
      via:"VPS_BRIDGE",
      workerMode:{live,liveAck,testnet},
      bridge:{vpcPresent:true,bridgeSecretPresent:true,httpStatus:r.status,responseOk:r.ok},
      bridgeDiagnostics:{
        reason:payload?.reason??null,
        upstreamStatus:payload?.upstreamStatus??null,
        binanceCode:payload?.binanceCode??null,
        binanceMessage:payload?.binanceMessage??null
      },
      workerCheckedAt:new Date().toISOString()
    };
    return json(normalized,r.ok?200:(r.status||502));
  }catch(e){
    return json({ok:false,readOnly:true,authenticated:false,via:"VPS_BRIDGE",mode:{live,liveAck,testnet},bridge:{vpcPresent:true,bridgeSecretPresent:true},reason:"BINANCE_VPS_BRIDGE_FETCH_FAILED",error:String(e?.message||e),checkedAt:new Date().toISOString()},502);
  }
}
