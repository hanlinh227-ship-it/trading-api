import {binanceUsdm} from "./binance-usdm-client.js";

function json(body,status=200){return new Response(JSON.stringify(body,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});}
function envBool(v){return String(v||"").toLowerCase()==="true";}
function safeNum(v){const n=Number(v);return Number.isFinite(n)?n:null;}

export async function handleBinanceReadonlyHealth(req,env){
  let url;
  try{url=new URL(req.url);}catch{return null;}
  if(url.pathname!=="/binance/health")return null;
  if(req.method!=="GET")return json({ok:false,reason:"METHOD_NOT_ALLOWED",allowed:["GET"]},405);

  const base=String(env.BINANCE_FUTURES_BASE_URL||"https://fapi.binance.com").replace(/\/$/,"");
  const live=envBool(env.BINANCE_AUTO_LIVE),liveAck=envBool(env.BINANCE_AUTO_LIVE_ACK),testnet=envBool(env.BINANCE_AUTO_TESTNET);
  const apiKeyPresent=!!env.BINANCE_FUTURES_API_KEY;
  const apiSecretPresent=!!env.BINANCE_FUTURES_API_SECRET;
  const credentialsPresent=apiKeyPresent&&apiSecretPresent;
  const credentialBindings={apiKeyPresent,apiSecretPresent};

  if(!credentialsPresent)return json({ok:false,readOnly:true,reason:"BINANCE_FUTURES_CREDENTIALS_MISSING",base,mode:{live,liveAck,testnet},credentialBindings},503);

  const api=binanceUsdm(env);
  try{
    const [account,positions,orders,book]=await Promise.all([
      api.account(),
      api.positions(),
      api.openOrders(),
      api.bookTicker("BTCUSDT")
    ]);
    const openPositions=(positions||[]).filter(x=>Math.abs(Number(x.positionAmt||0))>0).map(x=>({
      symbol:x.symbol,
      positionAmt:safeNum(x.positionAmt),
      entryPrice:safeNum(x.entryPrice),
      markPrice:safeNum(x.markPrice),
      unrealizedProfit:safeNum(x.unRealizedProfit??x.unrealizedProfit),
      leverage:safeNum(x.leverage),
      marginType:x.marginType
    }));
    return json({
      ok:true,
      readOnly:true,
      authenticated:true,
      base,
      mode:{live,liveAck,testnet},
      credentialBindings,
      account:{
        totalWalletBalance:safeNum(account?.totalWalletBalance),
        totalMarginBalance:safeNum(account?.totalMarginBalance),
        availableBalance:safeNum(account?.availableBalance),
        totalUnrealizedProfit:safeNum(account?.totalUnrealizedProfit)
      },
      positions:{openCount:openPositions.length,items:openPositions.slice(0,20)},
      openOrdersCount:Array.isArray(orders)?orders.length:null,
      btcusdt:{bid:safeNum(book?.bidPrice),ask:safeNum(book?.askPrice)},
      checkedAt:new Date().toISOString(),
      guarantees:["NO_ORDER_SUBMISSION","NO_LEVERAGE_CHANGE","NO_MARGIN_CHANGE","NO_CANCEL"]
    });
  }catch(e){
    return json({ok:false,readOnly:true,authenticated:false,base,mode:{live,liveAck,testnet},credentialBindings,reason:"BINANCE_READONLY_HEALTH_FAILED",error:String(e?.message||e),checkedAt:new Date().toISOString()},502);
  }
}
