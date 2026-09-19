import {loadTop100MarketCapUniverse,top100Map} from './bybit-market-cap-universe.js';
import {BYBIT_TRADE_UNIVERSE,coinProfileForSymbol,normalizeBybitSymbol,isCoreTradeSymbol} from './bybit-coin-profiles.js';
import {fetchBybitUniverseTickers} from './bybit-btc-microstructure-client.js';

const META_KEY='bybit:dynamic:universe:meta:v2:crypto-only';
const META_TTL_MS=15*60*1000;
const LAST_GOOD_KEY='bybit:dynamic:universe:last-good:v1';
const LAST_GOOD_MAX_MS=30*60*1000;
const PROMOTION_KEY='bybit:dynamic:promotion:evidence:v1';
const PROMOTION_EVIDENCE_TTL_MS=35*60*1000;
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const excludedBases=new Set(['USDT','USDC','USDE','DAI','FDUSD','TUSD','USDD','PYUSD']);
const NON_CRYPTO_SYMBOL_TYPES=new Set(['stock','forex','etf','commodity','xstocks']);

async function get(env,key,d={}){try{return await env.TRADING_STATE?.get(key,{type:'json'})??d}catch{return d}}
async function put(env,key,x){try{if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(x))}catch{}}

function validLinearSymbol(symbol=''){
  const s=normalizeBybitSymbol(symbol),base=s.endsWith('USDT')?s.slice(0,-4):'';
  return /^[A-Z0-9]{2,28}USDT$/.test(s)&&base&&!excludedBases.has(base);
}
function isCryptoSymbolType(v=''){const t=String(v||'').trim().toLowerCase();return !NON_CRYPTO_SYMBOL_TYPES.has(t);}

async function loadInstrumentMeta(env,api){
  const now=Date.now(),cached=await get(env,META_KEY,{});
  if(Array.isArray(cached.rows)&&now-num(cached.at)<META_TTL_MS)return cached;
  const rows=[];let cursor='';
  try{
    for(let page=0;page<4;page++){
      const r=await api.instruments(cursor),list=r?.result?.list||[];
      for(const x of list){
        const symbol=normalizeBybitSymbol(x.symbol||'');if(!validLinearSymbol(symbol))continue;
        rows.push({symbol,status:String(x.status||''),contractType:String(x.contractType||''),settleCoin:String(x.settleCoin||''),quoteCoin:String(x.quoteCoin||''),baseCoin:String(x.baseCoin||''),symbolType:String(x.symbolType||''),launchTime:num(x.launchTime),maxLeverage:num(x.leverageFilter?.maxLeverage),minLeverage:num(x.leverageFilter?.minLeverage),leverageStep:num(x.leverageFilter?.leverageStep)});
      }
      const next=String(r?.result?.nextPageCursor||'');if(!next||next===cursor)break;cursor=next;
    }
  }catch(e){
    if(Array.isArray(cached.rows)&&cached.rows.length)return {...cached,stale:true,error:String(e?.message||e).slice(0,220)};
    return {at:now,rows:[],error:String(e?.message||e).slice(0,220)};
  }
  const out={at:now,rows,source:'BYBIT_INSTRUMENTS_INFO',cryptoOnly:true};await put(env,META_KEY,out);return out;
}

function rowFromTicker(x={},meta={},cap=null,now=Date.now()){
  const symbol=normalizeBybitSymbol(x.symbol||''),bid=num(x.bid1Price),ask=num(x.ask1Price),last=num(x.lastPrice),mid=bid>0&&ask>0?(bid+ask)/2:last,spreadBps=mid>0&&ask>=bid?(ask-bid)/mid*10000:999,turnover=num(x.turnover24h),change=num(x.price24hPcnt),oiValue=num(x.openInterestValue),launch=num(meta.launchTime),ageDays=launch>0?Math.max(0,(now-launch)/86400000):null,core=isCoreTradeSymbol(symbol),profile=coinProfileForSymbol(symbol),metaKnown=core||Boolean(meta.status&&meta.contractType&&meta.settleCoin),symbolType=String(meta.symbolType||''),cryptoType=isCryptoSymbolType(symbolType),trading=String(meta.status||'').toUpperCase()==='TRADING',perpetual=/PERPETUAL/i.test(String(meta.contractType||'')),settled=String(meta.settleCoin||'').toUpperCase()==='USDT';
  const capRank=num(cap?.rank),marketCapUsd=num(cap?.marketCapUsd),capVolume24hUsd=num(cap?.volume24hUsd),marketCapTop100=capRank>0&&capRank<=100&&marketCapUsd>=250_000_000;
  const antiSweepLiquidity=clamp(Math.log10(Math.max(1,turnover))/9,0,1),antiSweepOi=clamp(Math.log10(Math.max(1,oiValue))/8.5,0,1),antiSweepSpread=clamp(1-spreadBps/10,0,1),antiSweepAge=ageDays===null?0:clamp(ageDays/180,0,1),antiSweepScore=.34*antiSweepLiquidity+.26*antiSweepOi+.28*antiSweepSpread+.12*antiSweepAge;
  let classification='WATCH_THIN',eligible=false,reason='LIQUIDITY_OR_SPREAD_BELOW_DYNAMIC_SCALP_GATE';
  if(!validLinearSymbol(symbol)){classification='DO_NOT_TRADE';reason='INVALID_LINEAR_USDT_SYMBOL';}
  else if(!core&&!metaKnown){classification='WATCH_READY';reason='INSTRUMENT_METADATA_REQUIRED_FOR_DYNAMIC_RISK';}
  else if(!core&&!cryptoType){classification='DO_NOT_TRADE';reason='NON_CRYPTO_LINEAR_PRODUCT_'+String(symbolType||'UNKNOWN').toUpperCase();}
  else if(!core&&(!trading||!perpetual||!settled)){classification='DO_NOT_TRADE';reason='INSTRUMENT_NOT_ACTIVE_USDT_LINEAR_PERPETUAL';}
  else if(!marketCapTop100){classification='WATCH_CAP';reason=capRank>100?'OUTSIDE_TOP100_MARKET_CAP':'MARKET_CAP_DATA_OR_FLOOR_NOT_MET';}
  else if(ageDays!==null&&ageDays<30){classification='WATCH_NEW';reason='LISTING_TOO_NEW_FOR_ANTI_SWEEP_EXECUTION';}
  else if(!(bid>0&&ask>0&&last>0)){classification='WATCH_EXECUTION_UNSAFE';reason='NO_EXECUTABLE_TWO_SIDED_MARKET';}
  else if(turnover<10_000_000||spreadBps>10||oiValue<3_000_000){classification='WATCH_EXECUTION_UNSAFE';reason=turnover<10_000_000?'TURNOVER_BELOW_TOP100_EXECUTION_FLOOR':spreadBps>10?'SPREAD_ABOVE_TOP100_EXECUTION_FLOOR':'OPEN_INTEREST_BELOW_TOP100_EXECUTION_FLOOR';}
  else if(antiSweepScore<.62){classification='WATCH_SWEEP_RISK';reason='ANTI_SWEEP_LIQUIDITY_SCORE_BELOW_FLOOR';}
  else {classification=core?'TRADE_CORE':'TRADE_TOP100';eligible=true;reason=null;}
  const liqScore=clamp(Math.log10(Math.max(10,turnover))/10,0,1),oiScore=clamp(Math.log10(Math.max(10,oiValue))/10,0,1),spreadScore=clamp(1-spreadBps/10,0,1),moveScore=clamp(Math.abs(change)*12,0,1),coreBonus=core?.08:0,score=.36*liqScore+.20*oiScore+.25*spreadScore+.19*moveScore+coreBonus;
  return {symbol,last,bid,ask,turnover,change,oiValue,spreadBps,ageDays,status:meta.status||null,symbolType,maxLeverage:num(meta.maxLeverage)||null,profile,style:profile?.style||'BALANCED',core,metaKnown,cryptoType,marketCapRank:capRank||null,marketCapUsd:marketCapUsd||null,capVolume24hUsd:capVolume24hUsd||null,marketCapTop100,antiSweepScore:Number(antiSweepScore.toFixed(4)),classification,eligible,reason,score};
}


function promotionPotential(row={}){const turnoverScore=clamp(num(row.turnover)/40_000_000,0,1),spreadScore=clamp(1-num(row.spreadBps)/9,0,1),oiScore=clamp(num(row.oiValue)/20_000_000,0,1),moveScore=clamp(Math.abs(num(row.change))/.02,0,1);return .34*turnoverScore+.30*spreadScore+.22*oiScore+.14*moveScore;}
function promotionSummary(ev={},row={},now=Date.now()){const hist=(Array.isArray(ev.history)?ev.history:[]).filter(x=>now-num(x.at)<=6*60*60*1000),good=hist.filter(x=>x.good).length,fresh=hist.filter(x=>x.fresh).length,goodRatio=hist.length?good/hist.length:0,freshRatio=hist.length?fresh/hist.length:0,lastGoodAt=Math.max(0,...hist.filter(x=>x.good).map(x=>num(x.at))),recent=now-num(ev.lastAt)<=PROMOTION_EVIDENCE_TTL_MS,currentMarketOk=row.classification==='WATCH_READY'&&num(row.turnover)>=12_000_000&&num(row.spreadBps)<=9.0&&num(row.oiValue)>=4_000_000&&promotionPotential(row)>=.58,qualified=recent&&currentMarketOk&&hist.length>=3&&good>=2&&goodRatio>=.67&&fresh>=3&&freshRatio>=.75&&now-lastGoodAt<=15*60*1000;return {qualified,observations:hist.length,good,fresh,goodRatio:Number(goodRatio.toFixed(3)),freshRatio:Number(freshRatio.toFixed(3)),lastAt:num(ev.lastAt)||null,lastGoodAt:lastGoodAt||null,potential:Number(promotionPotential(row).toFixed(4))};}
function applyPromotion(row={},ev={},now=Date.now()){const promotion=promotionSummary(ev,row,now);if(row.marketCapTop100!==true)return {...row,promotion:{...promotion,qualified:false}};if(promotion.qualified)return {...row,classification:'TRADE_PROMOTED',eligible:true,reason:null,promotion};return {...row,promotion};}
export async function updateBybitPromotionEvidence(env,observations=[]){const now=Date.now(),bucket=Math.floor(now/(5*60*1000)),state=await get(env,PROMOTION_KEY,{symbols:{}}),symbols={...(state.symbols||{})};for(const o of observations){const symbol=normalizeBybitSymbol(o.symbol||'');if(!validLinearSymbol(symbol))continue;const prev=symbols[symbol]||{},history=(Array.isArray(prev.history)?prev.history:[]).filter(x=>now-num(x.at)<=6*60*60*1000&&num(x.bucket)!==bucket),fresh=o.fresh===true,setupOk=o.setupOk===true,quality=num(o.quality),edge=num(o.edgeScore),netRR=num(o.netRR),directionOk=o.localCounterTrend!==true||o.reversalValidated===true,good=fresh&&setupOk&&directionOk&&quality>=.30&&edge>=.055&&netRR>=1.35;history.push({bucket,at:now,fresh,good,setupOk,quality:Number(quality.toFixed(4)),edge:Number(edge.toFixed(4)),netRR:Number(netRR.toFixed(3))});symbols[symbol]={lastAt:now,history:history.slice(-12)};}const out={at:now,symbols};await put(env,PROMOTION_KEY,out);return out;}

export async function buildBybitDynamicUniverse(env,api){
  const now=Date.now(),cached=await get(env,LAST_GOOD_KEY,{});
  const [tickersResult,wsTickersResult,metaResult,promotionResult,capResult]=await Promise.allSettled([
    api.tickers(),
    fetchBybitUniverseTickers(env),
    loadInstrumentMeta(env,api),
    get(env,PROMOTION_KEY,{symbols:{}}),
    loadTop100MarketCapUniverse(env)
  ]);
  const tickers=tickersResult.status==='fulfilled'?tickersResult.value:null;
  const wsTickerState=wsTickersResult.status==='fulfilled'?wsTickersResult.value:null;
  const metaState=metaResult.status==='fulfilled'?metaResult.value:{at:now,rows:[],stale:true,error:String(metaResult.reason?.message||metaResult.reason||'META_UNAVAILABLE').slice(0,220)};
  const promotionState=promotionResult.status==='fulfilled'?promotionResult.value:{symbols:{}};
  const capState=capResult.status==='fulfilled'?capResult.value:{at:now,source:'COINGECKO_MARKET_CAP_TOP100',rows:[],stale:true,failClosed:true,error:String(capResult.reason?.message||capResult.reason||'MARKET_CAP_UNAVAILABLE').slice(0,220)};
  const restTickerList=tickers?.result?.list||[],wsTickerList=Array.isArray(wsTickerState?.rows)?wsTickerState.rows:[],tickerFallbackUsed=restTickerList.length===0&&wsTickerList.length>0,tickerList=restTickerList.length?restTickerList:wsTickerList,tickerSource=restTickerList.length?'BYBIT_PUBLIC_REST':'CLOUDFLARE_BYBIT_WS_TICKERS';

  if(!Array.isArray(tickerList)||tickerList.length===0){
    const tickerError=String(tickersResult.status==='rejected'?(tickersResult.reason?.message||tickersResult.reason):'BYBIT_TICKERS_EMPTY').slice(0,220);
    if(Array.isArray(cached.ranked)&&cached.ranked.length&&now-num(cached.at)<=LAST_GOOD_MAX_MS){
      return {...cached,at:now,sourceAt:cached.at,stale:true,executionSafe:false,tradeSymbols:[],tickerSource:'UNAVAILABLE',tickerFallbackUsed:false,tickerCoverageCount:0,tickerError,summary:{...(cached.summary||{}),degraded:true,executionSafe:false,staleReason:'BYBIT_PUBLIC_TICKERS_UNAVAILABLE',tickerSource:'UNAVAILABLE',tickerFallbackUsed:false,tickerCoverageCount:0,tickerError}};
    }
    return {authority:'BYBIT_TOP100_MARKET_CAP_ANTI_SWEEP_UNIVERSE_V1',marketCapSource:capState.source,marketCapAt:capState.at,marketCapStale:true,at:now,cryptoOnly:true,coreSymbols:BYBIT_TRADE_UNIVERSE,tradeSymbols:[],ranked:[],watchNew:[],watchOnly:[],promotionCandidates:[],blocked:[],stale:true,executionSafe:false,tickerSource:'UNAVAILABLE',tickerFallbackUsed:false,tickerCoverageCount:0,tickerError,summary:{authority:'BYBIT_TOP100_MARKET_CAP_ANTI_SWEEP_UNIVERSE_V1',cryptoOnly:true,totalLinearUsdt:0,tradeableNow:0,promotedNow:0,promotionCandidates:0,watchNew:0,watchOnly:0,doNotTrade:0,counts:{},topTrade:[],promotionQueue:[],newListings:[],watch:[],blockedNonCrypto:[],metaFresh:false,metaAt:metaState.at||null,degraded:true,executionSafe:false,staleReason:'BYBIT_PUBLIC_TICKERS_UNAVAILABLE',tickerSource:'UNAVAILABLE',tickerFallbackUsed:false,tickerCoverageCount:0,tickerError}};
  }

  const metaMap=new Map((metaState.rows||[]).map(x=>[normalizeBybitSymbol(x.symbol),x])),capMap=top100Map(capState),rawRows=tickerList.filter(x=>validLinearSymbol(x.symbol)).map(x=>{const symbol=normalizeBybitSymbol(x.symbol),base=symbol.endsWith('USDT')?symbol.slice(0,-4):'';return rowFromTicker(x,metaMap.get(symbol)||{},capMap.get(base)||null,now)}),rows=rawRows.map(x=>applyPromotion(x,promotionState.symbols?.[x.symbol]||{},now)).sort((a,b)=>Number(b.eligible)-Number(a.eligible)||(num(a.marketCapRank)||999)-(num(b.marketCapRank)||999)||b.score-a.score||b.turnover-a.turnover),trade=rows.filter(x=>x.eligible).slice(0,100),watchNew=rows.filter(x=>x.classification==='WATCH_NEW'),watchOnly=rows.filter(x=>!x.eligible&&x.classification!=='WATCH_NEW'&&x.classification!=='DO_NOT_TRADE'),promotionCandidates=watchOnly.filter(x=>x.classification==='WATCH_READY').filter(x=>x.turnover>=4_000_000&&x.spreadBps<=11.5&&promotionPotential(x)>=.40).sort((a,b)=>b.promotion.potential-a.promotion.potential||b.score-a.score),blocked=rows.filter(x=>x.classification==='DO_NOT_TRADE'),counts={};for(const r of rows)counts[r.classification]=(counts[r.classification]||0)+1;
  const capUsable=Array.isArray(capState.rows)&&capState.rows.length>=50&&capState.failClosed!==true,executionSafe=trade.length>0&&capUsable,restError=tickersResult.status==='rejected'?String(tickersResult.reason?.message||tickersResult.reason).slice(0,220):null;
  const out={authority:'BYBIT_TOP100_MARKET_CAP_ANTI_SWEEP_UNIVERSE_V1',marketCapSource:capState.source,marketCapAt:capState.at,marketCapStale:capState.stale===true,at:now,cryptoOnly:true,coreSymbols:BYBIT_TRADE_UNIVERSE,tradeSymbols:executionSafe?trade.map(x=>x.symbol):[],ranked:rows,watchNew,watchOnly,promotionCandidates,blocked,stale:false,executionSafe,tickerSource,tickerFallbackUsed,tickerCoverageCount:tickerList.length,fallbackCoreOnly:tickerFallbackUsed,tickerRestError:restError,summary:{authority:'BYBIT_TOP100_MARKET_CAP_ANTI_SWEEP_UNIVERSE_V1',cryptoOnly:true,totalLinearUsdt:rows.length,tradeableNow:executionSafe?trade.length:0,promotedNow:trade.filter(x=>x.classification==='TRADE_PROMOTED').length,promotionCandidates:promotionCandidates.length,watchNew:watchNew.length,watchOnly:watchOnly.length,doNotTrade:blocked.length,counts,topTrade:trade.slice(0,20).map(x=>({symbol:x.symbol,class:x.classification,score:Number(x.score.toFixed(4)),promotion:x.promotion,spreadBps:Number(x.spreadBps.toFixed(3)),turnover24h:x.turnover,maxLeverage:x.maxLeverage,style:x.style,symbolType:x.symbolType})),promotionQueue:promotionCandidates.slice(0,30).map(x=>({symbol:x.symbol,class:x.classification,potential:x.promotion?.potential??null,observations:x.promotion?.observations??0,goodRatio:x.promotion?.goodRatio??0,freshRatio:x.promotion?.freshRatio??0,turnover24h:x.turnover,spreadBps:Number(x.spreadBps.toFixed(3)),reason:x.reason})),newListings:watchNew.slice(0,20).map(x=>({symbol:x.symbol,ageDays:x.ageDays===null?null:Number(x.ageDays.toFixed(2)),turnover24h:x.turnover,spreadBps:Number(x.spreadBps.toFixed(3)),reason:x.reason,symbolType:x.symbolType})),watch:watchOnly.slice(0,20).map(x=>({symbol:x.symbol,class:x.classification,reason:x.reason,potential:x.promotion?.potential??null,turnover24h:x.turnover,spreadBps:Number(x.spreadBps.toFixed(3)),symbolType:x.symbolType})),blockedNonCrypto:blocked.filter(x=>String(x.reason||'').startsWith('NON_CRYPTO_LINEAR_PRODUCT_')).slice(0,30).map(x=>({symbol:x.symbol,symbolType:x.symbolType,reason:x.reason})),metaFresh:!metaState.stale,metaAt:metaState.at||null,degraded:!executionSafe,executionSafe,tickerSource,tickerFallbackUsed,tickerCoverageCount:tickerList.length,fallbackCoreOnly:tickerFallbackUsed,marketCapError:capState.error||null,metaError:metaState.error||null,tickerRestError:restError}};
  if(executionSafe)await put(env,LAST_GOOD_KEY,out);
  return out;
}

export const BYBIT_DYNAMIC_UNIVERSE_VERSION='BYBIT_TOP100_MARKET_CAP_ANTI_SWEEP_UNIVERSE_V1';
