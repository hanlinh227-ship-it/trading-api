import {getBybitLearningState,setShadowChallenger} from "./bybit-learning-engine.js";

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const round=(x,n=3)=>Number(Number(x).toFixed(n));
const now=()=>Date.now();

function providerWeights(providers={}){
  const out={};for(const [name,s] of Object.entries(providers)){const acc=Number(s?.directionalAccuracy);out[name]=Number.isFinite(acc)?round(clamp(.75+acc*.5,.75,1.25),3):1;}return out;
}
function strategySignals(byStrategy={}){
  const rows=[];for(const [strategy,s] of Object.entries(byStrategy)){const trades=Number(s?.trades||0),avgNetR=Number(s?.avgNetR),netWinRate=Number(s?.netWinRate??s?.winRate);if(trades<5||!Number.isFinite(avgNetR)||!Number.isFinite(netWinRate))continue;rows.push({strategy,trades,avgNetR:round(avgNetR),netWinRate:round(netWinRate)});}return rows.sort((a,b)=>a.avgNetR-b.avgNetR);
}
export async function buildBybitShadowChallenger(env){
  const learning=await getBybitLearningState(env),s=learning.summary||{},sample=Number(s.sampleSize||0);
  if(sample<20)return {ok:true,created:false,reason:"INSUFFICIENT_CLOSED_SAMPLE",required:20,sampleSize:sample};
  const netWinRate=Number(s.netWinRate??s.winRate),avgNetR=Number(s.avgNetR),providerWeight=providerWeights(s.providers||{}),signals=strategySignals(s.byStrategy||{});
  let minScoreDelta=0,postAiDriftBpsDelta=0;
  if(Number.isFinite(avgNetR)&&avgNetR<0)minScoreDelta=2;else if(Number.isFinite(avgNetR)&&avgNetR>.35&&Number.isFinite(netWinRate)&&netWinRate>.58)minScoreDelta=-1;
  if(Number.isFinite(netWinRate)&&netWinRate<.45)postAiDriftBpsDelta=-2;else if(Number.isFinite(netWinRate)&&netWinRate>.62&&Number.isFinite(avgNetR)&&avgNetR>.3)postAiDriftBpsDelta=1;
  const weakStrategies=signals.filter(x=>x.avgNetR<0&&x.trades>=8).map(x=>x.strategy).slice(0,6),strongStrategies=signals.filter(x=>x.avgNetR>.3&&x.trades>=8).map(x=>x.strategy).slice(-6);
  const challenger={
    version:`BYBIT-CHALLENGER-${new Date().toISOString().replace(/[-:.TZ]/g,"").slice(0,14)}`,
    source:"LEARNING_V2_NET_PNL_BOUNDED",
    dataIntegrityVersion:learning.dataIntegrityVersion||s.dataIntegrityVersion||"BYBIT_LEARNING_NET_PNL_V2",
    evidence:{sampleSize:sample,netWinRate:round(netWinRate),avgNetR:round(avgNetR),sumNetR:round(Number(s.sumNetR||0)),weakStrategies,strongStrategies},
    proposed:{minScoreDelta:clamp(minScoreDelta,-2,3),postAiDriftBpsDelta:clamp(postAiDriftBpsDelta,-3,2),providerWeight},
    invariants:{maxOpenPositions:"UNCHANGED",riskLadder:"UNCHANGED",dailyStop:"UNCHANGED",slProtection:"UNCHANGED",liveAutoPromote:false},
    createdAt:now()
  };
  await setShadowChallenger(env,challenger);return {ok:true,created:true,challenger};
}
