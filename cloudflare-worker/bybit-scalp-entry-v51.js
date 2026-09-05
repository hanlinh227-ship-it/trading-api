import {normalizeBybitSymbol} from './bybit-coin-profiles.js';

const num=v=>Number.isFinite(Number(v))?Number(v):0;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const sideSign=side=>side==='Buy'?1:-1;

function qualityScore(s={},p={}){
  const w=s.trades?.window15s||{},trades=num(w.trades),notional=num(w.totalNotional||s.trades?.notional15s);
  const minTurnover=Math.max(500000,num(p.minTurnoverUsd)||25000000),notionalTarget=clamp(minTurnover/5760*2.2,8000,75000);
  const fresh=String(s.microstructureSource)==='VPS_BYBIT_WS'&&s?.quality?.freshBook===true&&s?.quality?.freshTrades===true?1:0;
  return clamp(.33*clamp(trades/32,0,1)+.42*clamp(notional/notionalTarget,0,1)+.25*fresh,0,1);
}

function sideMetrics(side,s={},p={}){
  const k=sideSign(side),t=s.trades||{},u=s.ultraFast||{},b=s.book||{},pulse=s.marketPulse||{};
  const p1=k*num(t.window1s?.priceChangeBps??t.priceChange1sBps),p3=k*num(t.window3s?.priceChangeBps??t.priceChange3sBps),p5=k*num(t.window5s?.priceChangeBps??t.priceChange5sBps);
  const f1=k*num(t.window1s?.imbalance),f3=k*num(t.window3s?.imbalance),f5=k*num(t.window5s?.imbalance),f15=k*num(t.window15s?.imbalance??t.aggressorImbalance),f60=k*num(t.window60s?.imbalance);
  const acc=k*num(u.flowAcceleration),pressure=k*num(u.pressureScore),impulse=k*num(u.impulseScore),book2=k*num(b.imbalance2),book5=k*num(b.imbalance5??b.imbalance),micro=k*num(b.micropriceEdgeBps),pulseScore=k*num(pulse.score);
  const q=qualityScore(s,p),priceVotes=[p1>0,p3>0,p5>0].filter(Boolean).length,flowVotes=[f3>.04,f5>.05,f15>.04,acc>.025,pressure>.04,impulse>.045,book2>-.02,micro>-.06].filter(Boolean).length;
  const velocityBpsPerSec=Math.max(.04,.30*Math.max(0,p1)+.35*Math.max(0,p3)/3+.35*Math.max(0,p5)/5+clamp(num(u.speedScore),0,1)*.18);
  const flowCore=.20*f3+.27*f5+.38*f15+.15*f60,bookCore=.68*clamp(book2,-1,1)+.32*clamp(micro/.25,-1,1);
  const adverse=clamp(.34*Math.max(0,-f15)+.18*Math.max(0,-f60)+.20*Math.max(0,-book2)+.14*Math.max(0,-micro/.25)+.14*Math.max(0,-p3/4),0,.65);
  return {k,q,p1,p3,p5,f1,f3,f5,f15,f60,acc,pressure,impulse,book2,book5,micro,pulseScore,pulseConfidence:num(pulse.confidence),pulseAgreement:num(pulse.agreement),priceVotes,flowVotes,velocityBpsPerSec,flowCore,bookCore,adverse,oiDelta:num(s.openInterest?.deltaPct),direction5:k*num(s.direction5),direction15:k*num(s.direction15),direction60:k*num(s.direction60),bias:k*num(s.structure15?.bias)};
}

function rangePosition(s={}){const e=num(s.price),lo=num(s.range5?.lo),hi=num(s.range5?.hi),w=hi-lo;return e>0&&lo>0&&w>0?clamp((e-lo)/w,0,1):null;}
function regimeSide(r=''){const x=String(r).toUpperCase();if(x==='TREND_UP'||x==='BREAKOUT_UP')return 'Buy';if(x==='TREND_DOWN'||x==='BREAKOUT_DOWN')return 'Sell';return null;}
function oppositeStrongRegime(side,s={}){const rs=regimeSide(s.regime);return !!rs&&rs!==side;}

function hitProbability(m={},lane='',bonus=0){
  const price=clamp((Math.max(0,m.p3)/3+Math.max(0,m.p5)/5)/2.4,0,1),flow=clamp((Math.max(0,m.f3)+Math.max(0,m.f5)+Math.max(0,m.f15)+.5*Math.max(0,m.f60))/.55,0,1),book=clamp((m.book2+.18)/.48,0,1)*.65+clamp((m.micro+.08)/.28,0,1)*.35,pulse=clamp((m.pulseScore+.10)/.35,0,1);
  const laneBias=lane==='LIQUIDITY_SWEEP_RECLAIM'?.085:lane==='BREAKOUT_RETEST_CONTINUATION'?.075:.065;
  return clamp(.24+.20*m.q+.18*price+.18*flow+.10*book+.05*pulse+laneBias+bonus-.26*m.adverse,0,1);
}

function geometry(side,s={},p={},lane='',level=0,tier='CONFIRM',hit=.68){
  const e=Math.max(0,num(s.price)),spreadBps=Math.max(0,num(s.book?.spreadBps)),spreadPx=e*spreadBps/10000,r5=Math.max(0,num(s.range5?.width));
  const minD=Math.max(e*.00055,spreadPx*3.0,r5*.055),maxD=Math.max(minD,Math.min(e*.00170,Math.max(r5*.18,e*.00090)));
  const noise=Math.max(spreadPx*2.5,e*.00035,r5*.04),st=s.structure15||{};
  let rawD=minD;
  if(lane==='LIQUIDITY_SWEEP_RECLAIM'&&level>0)rawD=side==='Buy'?e-(level-noise*.65):(level+noise*.65)-e;
  else if(lane==='BREAKOUT_RETEST_CONTINUATION'&&level>0)rawD=side==='Buy'?e-(level-noise*.55):(level+noise*.55)-e;
  else {const anchor=side==='Buy'?num(st.recentLow):num(st.recentHigh);if(anchor>0)rawD=Math.abs(e-anchor)+noise*.30;}
  const d=clamp(Math.abs(rawD),minD,maxD),sl=side==='Buy'?e-d:e+d,stopBps=e>0?d/e*10000:999;
  let rr=lane==='BREAKOUT_RETEST_CONTINUATION'?1.65:lane==='LIQUIDITY_SWEEP_RECLAIM'?1.55:1.50;if(tier==='FULL')rr+=.14;if(hit>=.80)rr+=.08;
  const rangeBps=e>0?r5/e*10000:0,observed5=Math.abs(num(s.trades?.priceChange5sBps??s.trades?.window5s?.priceChangeBps)),speed=num(s.ultraFast?.speedScore),reachableGrossBps=Math.max(12,observed5*3.0,rangeBps*.20,speed*32),reachR=stopBps>0?reachableGrossBps/stopBps:0;
  rr=clamp(Math.min(rr,reachR||rr),1.25,1.90);if(reachR>0&&reachR<1.25)return {ok:false,reason:'V51_TARGET_NOT_REACHABLE_FAST_ENOUGH',stopBps,reachableGrossBps,reachR};
  const tp=side==='Buy'?e+d*rr:e-d*rr;return {ok:true,entry:e,sl,tp,rr,stopDistance:d,stopBps,reachableGrossBps,scalpOnly:true};
}

function costAndTime(side,g={},s={},m={}){
  const e=Math.max(1,num(g.entry)),grossTargetBps=Math.abs(num(g.tp)-num(g.entry))/e*10000,c=s.executionCost||{},base=Math.max(0,num(c.baseRoundTripCostBps)||11),rate=num(c.fundingRate??s.fundingRate),funding=c.fundingWithinExpectedHold&&((side==='Buy'&&rate>0)||(side==='Sell'&&rate<0))?Math.abs(rate)*10000:0,totalCostBps=base+funding,netTargetBps=grossTargetBps-totalCostBps,netRewardRisk=g.stopBps>0?netTargetBps/g.stopBps:0,expectedTimeToTargetSec=grossTargetBps/Math.max(.04,m.velocityBpsPerSec),expectedNetBpsPerMinute=netTargetBps/Math.max(.50,expectedTimeToTargetSec/60),minNetBps=Math.max(7.0,totalCostBps*.64);
  return {ok:netTargetBps>=minNetBps&&netRewardRisk>=.72&&expectedTimeToTargetSec<=420,grossTargetBps,totalCostBps,netTargetBps,netRewardRisk,minNetBps,expectedTimeToTargetSec,expectedNetBpsPerMinute};
}

function finishCandidate(lane,side,s,p,m,meta={}){
  const prelimHit=hitProbability(m,lane,num(meta.hitBonus)),tierPre=m.q>=.62&&m.priceVotes===3&&m.flowVotes>=6?'FULL':'CONFIRM',g=geometry(side,s,p,lane,num(meta.level),tierPre,prelimHit);if(!g.ok)return g;
  const cost=costAndTime(side,g,s,m);if(!cost.ok)return {ok:false,reason:cost.expectedTimeToTargetSec>420?'V51_TIME_TO_TARGET_TOO_SLOW':'V51_EDGE_INSUFFICIENT_AFTER_COSTS',cost};
  const hit=hitProbability(m,lane,num(meta.hitBonus)+(cost.expectedTimeToTargetSec<=180?.025:0)),maePenalty=clamp(m.adverse+Math.max(0,num(s.book?.spreadBps)-2)/40,0,.60);
  if(hit<.68)return {ok:false,reason:'V51_HIT_PROBABILITY_BELOW_QUALITY_FLOOR',diagnostic:{hitProbability:hit,maePenalty}};
  const tier=hit>=.76&&m.q>=.60&&m.priceVotes===3&&m.flowVotes>=6&&maePenalty<=.18?'FULL':'CONFIRM',strength=tier==='FULL'&&hit>=.80&&cost.expectedTimeToTargetSec<=240?'A_PLUS':'STRONG',scalpScore=hit*cost.expectedNetBpsPerMinute*(1-maePenalty),localCounterTrend=oppositeStrongRegime(side,s),reversalValidated=!localCounterTrend||lane==='LIQUIDITY_SWEEP_RECLAIM'&&hit>=.78&&m.q>=.58&&m.priceVotes===3;
  if(localCounterTrend&&!reversalValidated)return {ok:false,reason:'V51_COUNTERTREND_NOT_STRONGLY_RECLAIMED'};
  return {ok:true,setup:{symbol:normalizeBybitSymbol(s.symbol),side,setup:`V51_${lane}`,strength,entryTier:tier,riskScale:(tier==='FULL'?1:.86)*clamp(num(p.riskMult)||.70,.25,1.10),regime:s.regime,entry:g.entry,sl:g.sl,tp:g.tp,rr:g.rr,stopDistance:g.stopDistance,scalpOnly:true,cost:{...cost,stopBps:g.stopBps},executionIntent:lane==='BREAKOUT_RETEST_CONTINUATION'&&strength==='A_PLUS'?'URGENT_MARKET':'IOC_CAPPED',reason:['V51_THREE_LANE_MICROSTRUCTURE','SHORT_HORIZON_PRICE_FOLLOW_THROUGH','ORDERBOOK_CONFIRM','TIME_TO_TARGET_GATE','MAE_AWARE','NET_AFTER_COSTS'],coinProfile:p,evidence:{lane,quality:m.q,score:hit,hitProbability:hit,expectedTimeToTargetSec:Number(cost.expectedTimeToTargetSec.toFixed(2)),expectedNetBpsPerMinute:Number(cost.expectedNetBpsPerMinute.toFixed(3)),maePenalty:Number(maePenalty.toFixed(4)),scalpScore:Number(scalpScore.toFixed(4)),priceVotes:m.priceVotes,flowVotes:m.flowVotes,p1:m.p1,p3:m.p3,p5:m.p5,flow3:m.f3,flow5:m.f5,flow15:m.f15,flow60:m.f60,book2:m.book2,micro:m.micro,pressure:m.pressure,impulse:m.impulse,acceleration:m.acc,pulse:m.pulseScore,oiDelta:m.oiDelta,velocityBpsPerSec:Number(m.velocityBpsPerSec.toFixed(4)),localCounterTrend,reversalValidated,marketContrarianQualified:localCounterTrend&&reversalValidated&&hit>=.82,source:s.microstructureSource,...meta},createdAt:Date.now(),marketStateAt:s.at}};
}

function sweepLane(side,s,p){
  const sw=s.sweep5||{},needed=side==='Buy'?sw.downSweep:sw.upSweep;if(!needed)return null;const m=sideMetrics(side,s,p),pos=rangePosition(s),edgeOk=pos===null?true:(side==='Buy'?pos<=.46:pos>=.54);
  if(!edgeOk||m.q<.52||m.priceVotes<2||m.p3<=.15||m.p5<=.25||m.f3<=.08||m.f5<=.08||m.f15<=.045||m.f60<=-.18||m.book2<=-.03||m.micro<=-.07||!(m.acc>.025||m.impulse>.055||m.pressure>.055))return null;
  const level=side==='Buy'?num(sw.priorLow):num(sw.priorHigh);return finishCandidate('LIQUIDITY_SWEEP_RECLAIM',side,s,p,m,{level,rangePosition:pos,hitBonus:.025});
}

function breakoutRetestLane(side,s,p){
  const m=sideMetrics(side,s,p),st=s.structure15||{},break5=side==='Buy'?!!s.structure5?.breakUp:!!s.structure5?.breakDown,break15=side==='Buy'?!!st.breakUp:!!st.breakDown,regimeOk=String(s.regime)===`BREAKOUT_${side==='Buy'?'UP':'DOWN'}`,level=side==='Buy'?num(st.priorHigh):num(st.priorLow),e=num(s.price);if(!(level>0&&(regimeOk||break5||break15)))return null;
  const extensionBps=m.k*(e-level)/Math.max(1,e)*10000,rangeBps=e>0?num(s.range5?.width)/e*10000:0,maxExtension=clamp(rangeBps*.22,6,18);if(extensionBps<-.8||extensionBps>maxExtension)return null;
  if(m.q<.54||m.priceVotes<2||m.p3<=.20||m.p5<=.40||m.f3<=.07||m.f5<=.08||m.f15<=.07||m.f60<=-.04||m.oiDelta<-.10||m.book2<=-.02||m.micro<=-.06||!(m.pressure>.05||m.impulse>.06||m.acc>.035))return null;
  return finishCandidate('BREAKOUT_RETEST_CONTINUATION',side,s,p,m,{level,extensionBps:Number(extensionBps.toFixed(3)),maxExtensionBps:Number(maxExtension.toFixed(3)),hitBonus:.02});
}

function trendPullbackLane(side,s,p){
  const wanted=side==='Buy'?'TREND_UP':'TREND_DOWN';if(String(s.regime)!==wanted)return null;const m=sideMetrics(side,s,p),pos=rangePosition(s),pullbackZone=pos!==null&&(side==='Buy'?(pos>=.38&&pos<=.78):(pos>=.22&&pos<=.62)),oppositeBreak=side==='Buy'?!!s.structure5?.breakDown:!!s.structure5?.breakUp;
  if(!pullbackZone||oppositeBreak||m.bias<=0||m.direction15<=.04||m.q<.50||m.priceVotes<2||m.p3<=.15||m.p5<=.30||m.f3<=.075||m.f5<=.085||m.f15<=.06||m.f60<=-.025||m.book2<=-.03||m.micro<=-.07||!(m.acc>.035||m.impulse>.06||m.pressure>.055))return null;
  return finishCandidate('TREND_PULLBACK_REACCELERATION',side,s,p,m,{rangePosition:pos,hitBonus:.015});
}

export function selectScalpEntryV51(s={},p={}){
  const symbol=normalizeBybitSymbol(s.symbol||'BTCUSDT'),q=s.quality||{},fresh=String(s.microstructureSource)==='VPS_BYBIT_WS'&&q.freshBook===true&&q.freshTrades===true&&q.spreadOk!==false;
  if(!fresh)return {ok:false,reason:'V51_FRESH_WS_REQUIRED',symbol};
  if(['TRANSITION','HIGH_VOL_SHOCK'].includes(String(s.regime||'')))return {ok:false,reason:'V51_REGIME_NO_NEW_RISK',symbol,regime:s.regime};
  const spread=num(s.book?.spreadBps),maxSpread=Math.min(10,Math.max(1,num(p.maxSpreadBps)||8));if(spread>maxSpread)return {ok:false,reason:'V51_SPREAD_TOO_WIDE',symbol,spreadBps:spread,maxSpreadBps:maxSpread};
  const candidates=[];for(const side of ['Buy','Sell']){for(const f of [sweepLane,breakoutRetestLane,trendPullbackLane]){const x=f(side,s,p);if(x?.ok)candidates.push(x);}}
  if(!candidates.length)return {ok:false,reason:'V51_NO_THREE_LANE_SCALP_ENTRY',symbol};
  candidates.sort((a,b)=>num(b.setup?.evidence?.scalpScore)-num(a.setup?.evidence?.scalpScore)||num(b.setup?.evidence?.hitProbability)-num(a.setup?.evidence?.hitProbability)||num(a.setup?.evidence?.expectedTimeToTargetSec)-num(b.setup?.evidence?.expectedTimeToTargetSec));
  const best=candidates[0];return {...best,alternatives:candidates.slice(1,3).map(x=>({side:x.setup.side,lane:x.setup.evidence.lane,scalpScore:x.setup.evidence.scalpScore,hitProbability:x.setup.evidence.hitProbability,expectedTimeToTargetSec:x.setup.evidence.expectedTimeToTargetSec}))};
}

export const BYBIT_SCALP_ENTRY_ENGINE_VERSION='BYBIT_SCALP_ENTRY_V51_THREE_LANE_TTT_MAE';
