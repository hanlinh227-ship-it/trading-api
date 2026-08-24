import {getBybitLearningState,setShadowChallenger} from "./bybit-learning-engine.js";

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const round=(x,n=3)=>Number(Number(x).toFixed(n));
const now=()=>Date.now();

function providerWeights(providers={}){
  const out={};for(const [name,s] of Object.entries(providers)){const acc=Number(s?.directionalAccuracy);out[name]=Number.isFinite(acc)?round(clamp(.75+acc*.5,.75,1.25),3):1;}return out;
}
function strategySignals(byStrategy={}){
  const rows=[];for(const [strategy,s] of Object.entries(byStrategy)){const trades=Number(s?.trades||0),avgR=Number(s?.avgR),winRate=Number(s?.winRate);if(trades<5||!Number.isFinite(avgR)||!Number.isFinite(winRate))continue;rows.push({strategy,trades,avgR:round(avgR),winRate:round(winRate)});}return rows.sort((a,b)=>a.avgR-b.avgR);
}
export async function buildBybitShadowChallenger(env){
  const learning=await getBybitLearningState(env),s=learning.summary||{},sample=Number(s.sampleSize||0);
  if(sample<20)return {ok:true,created:false,reason:"INSUFFICIENT_CLOSED_SAMPLE",required:20,sampleSize:sample};
  const winRate=Number(s.winRate),avgR=Number(s.avgR),providerWeight=providerWeights(s.providers||{}),signals=strategySignals(s.byStrategy||{});
  let minScoreDelta=0,postAiDriftBpsDelta=0;
  if(Number.isFinite(avgR)&&avgR<0)minScoreDelta=2;else if(Number.isFinite(avgR)&&avgR>.35&&Number.isFinite(winRate)&&winRate>.58)minScoreDelta=-1;
  if(Number.isFinite(winRate)&&winRate<.45)postAiDriftBpsDelta=-2;else if(Number.isFinite(winRate)&&winRate>.62&&Number.isFinite(avgR)&&avgR>.3)postAiDriftBpsDelta=1;
  const weakStrategies=signals.filter(x=>x.avgR<0&&x.trades>=8).map(x=>x.strategy).slice(0,6),strongStrategies=signals.filter(x=>x.avgR>.3&&x.trades>=8).map(x=>x.strategy).slice(-6);
  const challenger={
    version:`BYBIT-CHALLENGER-${new Date().toISOString().replace(/[-:.TZ]/g,"").slice(0,14)}`,
    source:"LEARNING_V1_BOUNDED",
    evidence:{sampleSize:sample,winRate:round(winRate),avgR:round(avgR),sumR:round(Number(s.sumR||0)),weakStrategies,strongStrategies},
    proposed:{minScoreDelta:clamp(minScoreDelta,-2,3),postAiDriftBpsDelta:clamp(postAiDriftBpsDelta,-3,2),providerWeight},
    invariants:{maxOpenPositions:"UNCHANGED",riskLadder:"UNCHANGED",dailyStop:"UNCHANGED",slProtection:"UNCHANGED",liveAutoPromote:false},
    createdAt:now()
  };
  await setShadowChallenger(env,challenger);return {ok:true,created:true,challenger};
}
