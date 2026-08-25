import {forexAutoConfig} from "./forex-auto-config.js";
const store=e=>e.TRADING_STATE||null;
const get=async(e,k)=>{try{return await store(e)?.get(k,{type:"json"})||null}catch{return null}};
const put=async(e,k,v)=>{if(store(e))await store(e).put(k,JSON.stringify(v));};
const clamp=(x,a,b)=>Math.max(a,Math.min(b,Number(x)||0));
const sk=(terminalId,symbol)=>`forex:learn:${String(terminalId).slice(0,80)}:${String(symbol).toUpperCase()}`;
const tk=(terminalId,ticket)=>`forex:learn:trade:${String(terminalId).slice(0,80)}:${String(ticket)}`;
export async function getForexLearningContext(env,terminalId,candidate){
 const cfg=forexAutoConfig(env),s=await get(env,sk(terminalId,candidate?.symbol)),min=cfg.learning?.minClosedSamples||12,recent=Array.isArray(s?.recentR)?s.recentR:[],recentAvg=recent.length?recent.reduce((a,b)=>a+Number(b||0),0)/recent.length:0,degraded=recent.length>=(cfg.learning?.degradationMinSamples||6)&&recentAvg<=Number(cfg.learning?.degradationAvgR||-.35);
 if(!s||Number(s.closed||0)<min)return {active:false,samples:Number(s?.closed||0),scoreDelta:degraded?-3:0,riskMultiplier:degraded?Number(cfg.learning?.degradationRiskMultiplier||.7):1,expectancyR:Number(s?.avgR||0),winRate:Number(s?.winRate||0),recentAvgR:recentAvg,degraded};
 const avgR=Number(s.avgR||0),wr=Number(s.winRate||0);let scoreDelta=0,riskMultiplier=1;
 if(avgR>=.35&&wr>=.52){scoreDelta=3;riskMultiplier=1.05;}else if(avgR>=.15){scoreDelta=1;riskMultiplier=1;}else if(avgR<0){scoreDelta=-4;riskMultiplier=.75;}else {scoreDelta=-1;riskMultiplier=.9;}
 if(degraded){scoreDelta=Math.min(scoreDelta,-3);riskMultiplier=Math.min(riskMultiplier,Number(cfg.learning?.degradationRiskMultiplier||.7));}
 return {active:true,samples:Number(s.closed||0),scoreDelta:clamp(scoreDelta,-5,5),riskMultiplier:clamp(riskMultiplier,.7,1.05),expectancyR:avgR,winRate:wr,recentAvgR:recentAvg,degraded,lastUpdated:s.updatedAt||null};
}
export async function recordForexEntry(env,terminalId,{ticket,symbol,side,setup="TREND_PULLBACK",regime="TREND",riskUsd=0,entry=0,sl=0,tp=0,score=0,rr=0}={}){if(!ticket)return;await put(env,tk(terminalId,ticket),{ticket,symbol,side,setup,regime,riskUsd:Number(riskUsd||0),entry:Number(entry||0),sl:Number(sl||0),tp:Number(tp||0),score:Number(score||0),rr:Number(rr||0),openedAt:new Date().toISOString()});}
export async function recordForexOutcome(env,terminalId,{ticket,pnl=0,mfeR=null,maeR=null,exitReason="UNKNOWN",slippageR=null}={}){
 if(!ticket)return {ok:false,reason:"TICKET_REQUIRED"};const tr=await get(env,tk(terminalId,ticket));if(!tr)return {ok:false,reason:"ENTRY_MEMORY_NOT_FOUND"};
 const cfg=forexAutoConfig(env),risk=Math.max(.01,Number(tr.riskUsd||0)),r=Number(pnl||0)/risk,key=sk(terminalId,tr.symbol),s=await get(env,key)||{symbol:tr.symbol,closed:0,wins:0,losses:0,sumR:0,sumMfeR:0,sumMaeR:0,mfeSamples:0,maeSamples:0,bySetup:{},recentR:[]};
 s.closed++;if(r>0)s.wins++;else s.losses++;s.sumR=Number(s.sumR||0)+r;s.avgR=s.sumR/s.closed;s.winRate=s.wins/s.closed;s.recentR=[...(Array.isArray(s.recentR)?s.recentR:[]),r].slice(-(cfg.learning?.recentWindow||8));
 if(Number.isFinite(Number(mfeR))){s.sumMfeR=Number(s.sumMfeR||0)+Number(mfeR);s.mfeSamples++;s.avgMfeR=s.sumMfeR/s.mfeSamples;}
 if(Number.isFinite(Number(maeR))){s.sumMaeR=Number(s.sumMaeR||0)+Number(maeR);s.maeSamples++;s.avgMaeR=s.sumMaeR/s.maeSamples;}
 const setup=String(tr.setup||"TREND_PULLBACK"),q=s.bySetup[setup]||{closed:0,wins:0,sumR:0,recentR:[]};q.closed++;if(r>0)q.wins++;q.sumR+=r;q.avgR=q.sumR/q.closed;q.winRate=q.wins/q.closed;q.recentR=[...(q.recentR||[]),r].slice(-(cfg.learning?.recentWindow||8));s.bySetup[setup]=q;s.lastTrade={ticket,r,pnl:Number(pnl||0),mfeR:Number.isFinite(Number(mfeR))?Number(mfeR):null,maeR:Number.isFinite(Number(maeR))?Number(maeR):null,slippageR:Number.isFinite(Number(slippageR))?Number(slippageR):null,exitReason,closedAt:new Date().toISOString()};s.updatedAt=new Date().toISOString();await put(env,key,s);return {ok:true,r,stats:s};
}
export async function getForexLearningSummary(env,terminalId,symbol){return await get(env,sk(terminalId,symbol))||null;}
