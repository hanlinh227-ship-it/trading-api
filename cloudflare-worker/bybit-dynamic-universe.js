import {BYBIT_TRADE_UNIVERSE,coinProfileForSymbol,normalizeBybitSymbol,isCoreTradeSymbol} from './bybit-coin-profiles.js';

const META_KEY='bybit:dynamic:universe:meta:v2:crypto-only';
const META_TTL_MS=15*60*1000;
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

function rowFromTicker(x={},meta={},now=Date.now()){
  const symbol=normalizeBybitSymbol(x.symbol||''),bid=num(x.bid1Price),ask=num(x.ask1Price),last=num(x.lastPrice),mid=bid>0&&ask>0?(bid+ask)/2:last,spreadBps=mid>0&&ask>=bid?(ask-bid)/mid*10000:999,turnover=num(x.turnover24h),change=num(x.price24hPcnt),oiValue=num(x.openInterestValue),launch=num(meta.launchTime),ageDays=launch>0?Math.max(0,(now-launch)/86400000):null,core=isCoreTradeSymbol(symbol),profile=coinProfileForSymbol(symbol),metaKnown=core||Boolean(meta.status&&meta.contractType&&meta.settleCoin),symbolType=String(meta.symbolType||''),cryptoType=isCryptoSymbolType(symbolType),trading=String(meta.status||'').toUpperCase()==='TRADING',perpetual=/PERPETUAL/i.test(String(meta.contractType||'')),settled=String(meta.settleCoin||'').toUpperCase()==='USDT';
  let classification='WATCH_THIN',eligible=false,reason='LIQUIDITY_OR_SPREAD_BELOW_DYNAMIC_SCALP_GATE';
  if(!validLinearSymbol(symbol)){classification='DO_NOT_TRADE';reason='INVALID_LINEAR_USDT_SYMBOL';}
  else if(!core&&!metaKnown){classification='WATCH_READY';reason='INSTRUMENT_METADATA_REQUIRED_FOR_DYNAMIC_RISK';}
  else if(!core&&!cryptoType){classification='DO_NOT_TRADE';reason='NON_CRYPTO_LINEAR_PRODUCT_'+String(symbolType||'UNKNOWN').toUpperCase();}
  else if(!core&&(!trading||!perpetual||!settled)){classification='DO_NOT_TRADE';reason='INSTRUMENT_NOT_ACTIVE_USDT_LINEAR_PERPETUAL';}
  else if(ageDays!==null&&ageDays<3){classification='WATCH_NEW';reason='NEW_LISTING_OBSERVATION_LT_3D';}
  else if(ageDays!==null&&ageDays<14){classification='WATCH_NEW';reason='NEW_LISTING_OBSERVATION_LT_14D';}
  else if(core&&turnover>=Math.max(8_000_000,num(profile?.minTurnoverUsd)*.35)&&spreadBps<=Math.max(3.5,num(profile?.maxSpreadBps))){classification='TRADE_CORE';eligible=true;reason=null;}
  else if(turnover>=150_000_000&&spreadBps<=3.5){classification='TRADE_STABLE';eligible=true;reason=null;}
  else if(turnover>=40_000_000&&spreadBps<=6.5&&(Math.abs(change)>=.008||oiValue>=20_000_000)){classification='TRADE_SCALP_FAST';eligible=true;reason=null;}
  else if(turnover>=75_000_000&&spreadBps<=5.5){classification='TRADE_STABLE';eligible=true;reason=null;}
  else if(turnover<12_000_000||spreadBps>10){classification='WATCH_THIN';reason=turnover<12_000_000?'TURNOVER_TOO_LOW':'SPREAD_TOO_WIDE';}
  else {classification='WATCH_READY';reason='OBSERVE_UNTIL_EDGE_AND_EXECUTION_QUALITY_IMPROVE';}
  const liqScore=clamp(Math.log10(Math.max(10,turnover))/10,0,1),oiScore=clamp(Math.log10(Math.max(10,oiValue))/10,0,1),spreadScore=clamp(1-spreadBps/10,0,1),moveScore=clamp(Math.abs(change)*12,0,1),coreBonus=core?.08:0,score=.36*liqScore+.20*oiScore+.25*spreadScore+.19*moveScore+coreBonus;
  return {symbol,last,bid,ask,turnover,change,oiValue,spreadBps,ageDays,status:meta.status||null,symbolType,maxLeverage:num(meta.maxLeverage)||null,profile,style:profile?.style||'BALANCED',core,metaKnown,cryptoType,classification,eligible,reason,score};
}

export async function buildBybitDynamicUniverse(env,api){
  const now=Date.now(),[tickers,metaState]=await Promise.all([api.tickers(),loadInstrumentMeta(env,api)]),metaMap=new Map((metaState.rows||[]).map(x=>[normalizeBybitSymbol(x.symbol),x])),rows=(tickers?.result?.list||[]).filter(x=>validLinearSymbol(x.symbol)).map(x=>rowFromTicker(x,metaMap.get(normalizeBybitSymbol(x.symbol))||{},now)).sort((a,b)=>Number(b.eligible)-Number(a.eligible)||b.score-a.score||b.turnover-a.turnover),trade=rows.filter(x=>x.eligible),watchNew=rows.filter(x=>x.classification==='WATCH_NEW'),watchOnly=rows.filter(x=>!x.eligible&&x.classification!=='WATCH_NEW'&&x.classification!=='DO_NOT_TRADE'),blocked=rows.filter(x=>x.classification==='DO_NOT_TRADE'),counts={};for(const r of rows)counts[r.classification]=(counts[r.classification]||0)+1;
  return {authority:'BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V2',at:now,cryptoOnly:true,coreSymbols:BYBIT_TRADE_UNIVERSE,tradeSymbols:trade.map(x=>x.symbol),ranked:rows,watchNew,watchOnly,blocked,summary:{authority:'BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V2',cryptoOnly:true,totalLinearUsdt:rows.length,tradeableNow:trade.length,watchNew:watchNew.length,watchOnly:watchOnly.length,doNotTrade:blocked.length,counts,topTrade:trade.slice(0,20).map(x=>({symbol:x.symbol,class:x.classification,score:Number(x.score.toFixed(4)),spreadBps:Number(x.spreadBps.toFixed(3)),turnover24h:x.turnover,maxLeverage:x.maxLeverage,style:x.style,symbolType:x.symbolType})),newListings:watchNew.slice(0,20).map(x=>({symbol:x.symbol,ageDays:x.ageDays===null?null:Number(x.ageDays.toFixed(2)),turnover24h:x.turnover,spreadBps:Number(x.spreadBps.toFixed(3)),reason:x.reason,symbolType:x.symbolType})),watch:watchOnly.slice(0,20).map(x=>({symbol:x.symbol,class:x.classification,reason:x.reason,turnover24h:x.turnover,spreadBps:Number(x.spreadBps.toFixed(3)),symbolType:x.symbolType})),blockedNonCrypto:blocked.filter(x=>String(x.reason||'').startsWith('NON_CRYPTO_LINEAR_PRODUCT_')).slice(0,30).map(x=>({symbol:x.symbol,symbolType:x.symbolType,reason:x.reason})),metaFresh:!metaState.stale,metaAt:metaState.at||null}};
}

export const BYBIT_DYNAMIC_UNIVERSE_VERSION='BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V2';
