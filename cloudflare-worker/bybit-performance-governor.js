import {normalizeBybitSymbol,isCoreTradeSymbol} from './bybit-coin-profiles.js';

const KEY='bybit:performance:governor:v1';
const CACHE_MS=45_000;
const LOOKBACK_MS=72*60*60*1000;
const DAY_MS=24*60*60*1000;
const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
async function get(env,k,d={}){try{return await env.TRADING_STATE?.get(k,{type:'json'})??d}catch{return d}}
async function put(env,k,x){try{if(env.TRADING_STATE)await env.TRADING_STATE.put(k,JSON.stringify(x))}catch{}}

function summarize(rows=[]){
  const sorted=[...rows].sort((a,b)=>num(b.updatedTime||b.createdTime)-num(a.updatedTime||a.createdTime));
  const pnl=sorted.map(x=>num(x.closedPnl)); // Bybit Closed PnL is already after trading fees/funding.
  const wins=pnl.filter(x=>x>0),losses=pnl.filter(x=>x<0),netPnl=pnl.reduce((s,x)=>s+x,0),fees=sorted.reduce((s,x)=>s+Math.abs(num(x.openFee))+Math.abs(num(x.closeFee)),0);
  let consecutiveLosses=0,consecutiveWins=0;for(const x of pnl){if(x<0)consecutiveLosses++;else break;}for(const x of pnl){if(x>0)consecutiveWins++;else break;}
  const winSum=wins.reduce((s,x)=>s+x,0),lossSum=Math.abs(losses.reduce((s,x)=>s+x,0));
  return {trades:pnl.length,wins:wins.length,losses:losses.length,netPnl:Number(netPnl.toFixed(6)),fees:Number(fees.toFixed(6)),expectancy:pnl.length?Number((netPnl/pnl.length).toFixed(6)):0,winRate:pnl.length?Number((wins.length/pnl.length).toFixed(4)):0,avgWin:wins.length?Number((winSum/wins.length).toFixed(6)):0,avgLoss:losses.length?Number((lossSum/losses.length).toFixed(6)):0,profitFactor:lossSum>0?Number((winSum/lossSum).toFixed(3)):(winSum>0?99:0),consecutiveLosses,consecutiveWins,lastClosedAt:sorted[0]?num(sorted[0].updatedTime||sorted[0].createdTime):null,lastNetPnl:sorted[0]?num(sorted[0].closedPnl):null};
}

async function fetchRows(api,start,end){
  const out=[];let cursor='';
  for(let page=0;page<4;page++){
    const r=await api.closedPnl(start,end,cursor),list=r?.result?.list||[];out.push(...list);
    const next=String(r?.result?.nextPageCursor||'');if(!next||next===cursor)break;cursor=next;
  }
  const seen=new Set();return out.filter(x=>{const k=String(x.orderId||'')+'|'+String(x.updatedTime||x.createdTime||'')+'|'+String(x.symbol||'');if(seen.has(k))return false;seen.add(k);return true;});
}

export async function buildBybitPerformanceGovernor(env,api,{equityUsd=0,highWaterUsd=0}={}){
  const now=Date.now(),cached=await get(env,KEY,{});if(num(cached.at)>0&&now-num(cached.at)<CACHE_MS)return cached;
  let rows=[];try{rows=await fetchRows(api,now-LOOKBACK_MS,now)}catch(e){if(cached?.summary)return {...cached,stale:true,error:String(e?.message||e).slice(0,220)};return {at:now,stale:true,error:String(e?.message||e).slice(0,220),summary:{},symbols:{}}}
  const rows24=rows.filter(x=>now-num(x.updatedTime||x.createdTime)<=DAY_MS),by=new Map();for(const x of rows){const s=normalizeBybitSymbol(x.symbol||'');if(!s)continue;if(!by.has(s))by.set(s,[]);by.get(s).push(x)}
  const symbols={};for(const [s,xs] of by){symbols[s]={h72:summarize(xs),h24:summarize(xs.filter(x=>now-num(x.updatedTime||x.createdTime)<=DAY_MS))};}
  const equity=Math.max(0,num(equityUsd)),high=Math.max(equity,num(highWaterUsd)||equity),drawdownPct=high>0?(high-equity)/high*100:0;
  const out={at:now,stale:false,source:'BYBIT_CLOSED_PNL_NET_AFTER_FEES_FUNDING',lookbackHours:72,summary:{h72:summarize(rows),h24:summarize(rows24),equityUsd:equity,highWaterUsd:high,drawdownPct:Number(drawdownPct.toFixed(3))},symbols};await put(env,KEY,out);return out;
}

export function bybitPerformanceDecision(state={},candidate={},equityUsd=0,highWaterUsd=0){
  const symbol=normalizeBybitSymbol(candidate.symbol||''),g72=state?.summary?.h72||{},g24=state?.summary?.h24||{},s72=state?.symbols?.[symbol]?.h72||{},s24=state?.symbols?.[symbol]?.h24||{},equity=Math.max(.01,num(equityUsd)),high=Math.max(equity,num(highWaterUsd)||num(state?.summary?.highWaterUsd)||equity),dd=high>0?(high-equity)/high*100:0;
  const strength=String(candidate.strength||'NORMAL'),tier=String(candidate.entryTier||'CONFIRM'),quality=num(candidate.quality),edge=num(candidate.edgeScore),rr=num(candidate.netRR),aligned=candidate.localCounterTrend!==true||candidate.reversalValidated===true,exceptional=strength==='A_PLUS'&&tier==='FULL'&&quality>=.58&&edge>=.16&&rr>=.80&&aligned;
  let block=null;
  if(dd>=10&&strength==='NORMAL')block='RECOVERY_MODE_REQUIRES_STRONG_EDGE';
  if(num(g24.trades)>=8&&((num(g24.expectancy)<=0&&num(g24.profitFactor)<1.02)||num(g24.profitFactor)<.90)&&!exceptional)block='GLOBAL_POSITIVE_EDGE_REQUALIFICATION';
  if(num(g72.trades)>=12&&num(g72.expectancy)<=0&&num(g72.profitFactor)<1.03&&!exceptional)block='GLOBAL_72H_POSITIVE_EDGE_REQUALIFICATION';
  if(num(s72.trades)>=6&&(num(s72.expectancy)<=0||num(s72.profitFactor)<1.00)&&!exceptional)block='SYMBOL_POSITIVE_EDGE_QUARANTINE';
  if(num(s72.consecutiveLosses)>=2&&!exceptional)block='SYMBOL_LOSS_STREAK_REQUALIFICATION_REQUIRED';
  let riskMult=1;
  if(dd>=15)riskMult*=.55;else if(dd>=10)riskMult*=.70;else if(dd>=6)riskMult*=.84;
  if(num(g24.trades)>=6&&(num(g24.expectancy)<=0||num(g24.profitFactor)<1.02))riskMult*=.72;
  if(num(s72.trades)>=4&&(num(s72.expectancy)<=0||num(s72.profitFactor)<1.00))riskMult*=.55;
  else if(num(s72.trades)>=6&&num(s72.expectancy)>0&&num(s72.profitFactor)>=1.20)riskMult*=1.00;
  if(num(s72.consecutiveLosses)>=1)riskMult*=.82;
  if(!isCoreTradeSymbol(symbol)&&num(s72.trades)===0)riskMult*=.70;
  if(strength==='NORMAL')riskMult*=.90;
  riskMult=clamp(riskMult,.25,1.00);
  return {symbol,block,riskMult:Number(riskMult.toFixed(3)),exceptional,drawdownPct:Number(dd.toFixed(3)),global24:g24,global72:g72,symbol24:s24,symbol72:s72,authority:'REALIZED_NET_POSITIVE_EDGE_SCALP_QUALITY_V2'};
}

export const BYBIT_PERFORMANCE_GOVERNOR_VERSION='BYBIT_PERFORMANCE_GOVERNOR_V2_POSITIVE_EDGE_SCALP_QUALITY';
