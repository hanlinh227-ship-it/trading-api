import {binanceUsdm} from "./binance-usdm-client.js";

const EXCLUDE_BASES=new Set(["USDC","FDUSD","TUSD","USDP","DAI","BUSD"]);
const n=v=>Number(v);
const good=x=>Number.isFinite(x)&&x>0;

export async function buildBinanceLiquidUniverse(env,{minCount=50,minQuoteVolumeUsd=5_000_000,maxSpreadBps=12}={}){
  const api=binanceUsdm(env);
  const [info,tickers,books]=await Promise.all([api.exchangeInfo(),api.ticker24h(),api.bookTicker()]);
  const tMap=new Map((Array.isArray(tickers)?tickers:[tickers]).map(x=>[x.symbol,x]));
  const bMap=new Map((Array.isArray(books)?books:[books]).map(x=>[x.symbol,x]));
  const rows=[];
  for(const s of info?.symbols||[]){
    if(s.status!=="TRADING"||s.contractType!=="PERPETUAL"||s.quoteAsset!=="USDT")continue;
    if(EXCLUDE_BASES.has(String(s.baseAsset||"").toUpperCase()))continue;
    const t=tMap.get(s.symbol),b=bMap.get(s.symbol),bid=n(b?.bidPrice),ask=n(b?.askPrice),mid=(bid+ask)/2,quoteVolume=n(t?.quoteVolume),trades=n(t?.count),spreadBps=good(mid)?(ask-bid)/mid*10000:Infinity;
    if(!good(bid)||!good(ask)||ask<=bid||!good(quoteVolume)||quoteVolume<minQuoteVolumeUsd||spreadBps>maxSpreadBps)continue;
    rows.push({symbol:s.symbol,baseAsset:s.baseAsset,quoteVolume,spreadBps,trades:Number.isFinite(trades)?trades:0});
  }
  rows.sort((a,b)=>b.quoteVolume-a.quoteVolume||a.spreadBps-b.spreadBps||b.trades-a.trades);
  return {ok:rows.length>=minCount,requestedMin:minCount,eligible:rows.length,count:rows.length,symbols:rows.map(x=>x.symbol),metrics:rows,reason:rows.length>=minCount?"OK":"INSUFFICIENT_LIQUID_UNIVERSE"};
}
