from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
CFG=ROOT/'cloudflare-worker/bybit-auto-config.js'
ENGINE=ROOT/'cloudflare-worker/bybit-symbol-engine.js'
RISK=ROOT/'cloudflare-worker/bybit-btc-risk-engine.js'
CTRL=ROOT/'cloudflare-worker/bybit-multi-asset-controller.js'
RUNTIME=ROOT/'cloudflare-worker/bybit-runtime-contract.js'
PERF=ROOT/'cloudflare-worker/bybit-performance-governor.js'


def rep(text, old, new, label, count=1):
    if old not in text:
        raise SystemExit(f'MISSING_MARKER:{label}')
    return text.replace(old,new,count)

perf = r'''import {normalizeBybitSymbol,isCoreTradeSymbol} from './bybit-coin-profiles.js';

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
  const strength=String(candidate.strength||'NORMAL'),tier=String(candidate.entryTier||'CONFIRM'),quality=num(candidate.quality),edge=num(candidate.edgeScore),rr=num(candidate.netRR),aligned=candidate.localCounterTrend!==true||candidate.reversalValidated===true,exceptional=strength==='A_PLUS'&&tier==='FULL'&&quality>=.38&&edge>=.075&&rr>=2.20&&aligned;
  let block=null;
  if(dd>=10&&strength==='NORMAL')block='RECOVERY_MODE_REQUIRES_STRONG_EDGE';
  if(num(g24.trades)>=4&&num(g24.expectancy)<-.04&&num(g24.consecutiveLosses)>=3&&!exceptional)block='GLOBAL_NEGATIVE_EXPECTANCY_GUARD';
  if(num(s72.trades)>=3&&num(s72.expectancy)<-.035&&!exceptional)block='SYMBOL_NEGATIVE_EXPECTANCY_QUARANTINE';
  if(num(s72.consecutiveLosses)>=2&&!exceptional)block='SYMBOL_LOSS_STREAK_REQUALIFICATION_REQUIRED';
  let riskMult=1;
  if(dd>=15)riskMult*=.55;else if(dd>=10)riskMult*=.70;else if(dd>=6)riskMult*=.84;
  if(num(g24.trades)>=3&&num(g24.expectancy)<0)riskMult*=.82;
  if(num(s72.trades)>=2&&num(s72.expectancy)<0)riskMult*=.68;
  else if(num(s72.trades)>=2&&num(s72.expectancy)>0&&num(s72.profitFactor)>=1.25)riskMult*=1.00;
  if(num(s72.consecutiveLosses)>=1)riskMult*=.82;
  if(!isCoreTradeSymbol(symbol)&&num(s72.trades)===0)riskMult*=.70;
  if(strength==='NORMAL')riskMult*=.90;
  riskMult=clamp(riskMult,.40,1.00);
  return {symbol,block,riskMult:Number(riskMult.toFixed(3)),exceptional,drawdownPct:Number(dd.toFixed(3)),global24:g24,global72:g72,symbol24:s24,symbol72:s72,authority:'REALIZED_NET_EXPECTANCY_CAPITAL_PRESERVATION'};
}

export const BYBIT_PERFORMANCE_GOVERNOR_VERSION='BYBIT_PERFORMANCE_GOVERNOR_V1_REALIZED_NET_EXPECTANCY';
'''
PERF.write_text(perf)

# Config: smaller-account capital preservation + earlier winner harvest.
c=CFG.read_text()
repls=[
("minPlannedNetProfitUsd:1.05,","minPlannedNetProfitUsd:.25,\n    preferredRunnerNetProfitUsd:1.05,",'min_profit'),
("minPlannedNetProfitPct:.35,","minPlannedNetProfitPct:.35,",'min_profit_pct'),
("{equityUsd:0,minNetUsd:1.05},{equityUsd:50,minNetUsd:1.25},{equityUsd:75,minNetUsd:1.50},\n      {equityUsd:100,minNetUsd:1.80},{equityUsd:150,minNetUsd:2.30},{equityUsd:250,minNetUsd:3.25},\n      {equityUsd:500,minNetUsd:5.50},{equityUsd:1000,minNetUsd:10.00},{equityUsd:2500,minNetUsd:22.00},\n      {equityUsd:5000,minNetUsd:45.00},{equityUsd:10000,minNetUsd:80.00}","{equityUsd:0,minNetUsd:.25},{equityUsd:50,minNetUsd:.35},{equityUsd:75,minNetUsd:.50},\n      {equityUsd:100,minNetUsd:.70},{equityUsd:150,minNetUsd:1.00},{equityUsd:250,minNetUsd:1.50},\n      {equityUsd:500,minNetUsd:3.00},{equityUsd:1000,minNetUsd:6.00},{equityUsd:2500,minNetUsd:14.00},\n      {equityUsd:5000,minNetUsd:30.00},{equityUsd:10000,minNetUsd:60.00}",'profit_ladder'),
("profitPeakRetentionPct:.68,","profitPeakRetentionPct:.78,",'peak_retention'),
("profitLockR:.72,","profitLockR:.55,",'profit_lock'),
("trailStartR:1.55,","trailStartR:1.10,",'trail_start'),
("peakGivebackActivationR:1.45,","peakGivebackActivationR:.85,",'peak_activation'),
("peakGivebackR:.82,","peakGivebackR:.45,",'peak_giveback'),
("baseEntryRiskPct:1.05,strongEntryRiskPct:1.35,aPlusEntryRiskPct:1.60,absoluteSingleEntryRiskPct:1.60,","baseEntryRiskPct:.70,strongEntryRiskPct:.95,aPlusEntryRiskPct:1.20,absoluteSingleEntryRiskPct:1.25,",'entry_risk'),
("maxActiveRiskPct:7.5,temporaryAPlusActiveRiskPct:9.5,maxPortfolioMarginPct:78,maxMarginPerPositionPct:78,minFreeReservePct:12,","maxActiveRiskPct:4.2,temporaryAPlusActiveRiskPct:5.0,maxPortfolioMarginPct:60,maxMarginPerPositionPct:55,minFreeReservePct:20,",'portfolio_risk'),
("dailyTarget:false,maxSameDirectionPositions:3,riskRecycleAfterProtection:true,","dailyTarget:false,maxSameDirectionPositions:2,riskRecycleAfterProtection:true,",'same_dir'),
("drawdownGovernor:[{ddPct:4,multiplier:.90},{ddPct:7,multiplier:.72},{ddPct:10,multiplier:.52},{ddPct:15,multiplier:.28},{ddPct:20,multiplier:0}]","drawdownGovernor:[{ddPct:2,multiplier:.88},{ddPct:4,multiplier:.75},{ddPct:7,multiplier:.60},{ddPct:10,multiplier:.45},{ddPct:15,multiplier:.25},{ddPct:20,multiplier:0}]",'dd_governor'),
("profitHarvestMinEvidence:4,","profitHarvestMinEvidence:3,\n    earlyHarvestMinNetUsd:.18,\n    earlyHarvestMinPeakR:.55,\n    earlyHarvestMinEvidence:2,\n    earlyHarvestConfirmEvents:2,\n    earlyHarvestGivebackR:.25,",'early_harvest'),
("profitHarvestConfirmEvents:4,","profitHarvestConfirmEvents:2,",'harvest_confirm'),
("profitHarvestPeakGivebackR:.70,","profitHarvestPeakGivebackR:.35,",'harvest_giveback'),
("decelerationLockMinR:1.05,","decelerationLockMinR:.55,",'decel_min'),
("decelerationPeakMinR:1.40,","decelerationPeakMinR:.80,",'decel_peak')
]
for old,new,label in repls:c=rep(c,old,new,label)
CFG.write_text(c)

# Risk engine accepts a realized-performance risk multiplier.
r=RISK.read_text()
r=rep(r,"externalActiveRiskUsd=0,externalMarginUsd=0}){","externalActiveRiskUsd=0,externalMarginUsd=0,performanceRiskMult=1}){",'risk_signature')
r=rep(r,"basePct=Math.min(absolutePct,riskPctForStrength(cfg,String(setup?.strength||'NORMAL'))*tierFactor),riskPct=Math.min(absolutePct,basePct*scale.riskMult)*dd.multiplier,candidateRiskUsd=capital.capitalBaseUsd*riskPct/100","basePct=Math.min(absolutePct,riskPctForStrength(cfg,String(setup?.strength||'NORMAL'))*tierFactor),perfMult=clamp(num(performanceRiskMult)||1,.40,1),riskPct=Math.min(absolutePct,basePct*scale.riskMult)*dd.multiplier*perfMult,candidateRiskUsd=capital.capitalBaseUsd*riskPct/100",'risk_perf_mult')
r=rep(r,"return {ok:true,riskPct,candidateRiskUsd","return {ok:true,riskPct,performanceRiskMult:perfMult,candidateRiskUsd",'risk_return')
RISK.write_text(r)

# Engine: make the profit floor realistic at small capital, pass perf risk, harvest decaying winners before $1.
e=ENGINE.read_text()
e=rep(e,"hard=Math.max(1,num(cfg?.scalp?.minPlannedNetProfitUsd)||1)","hard=Math.max(.12,num(cfg?.scalp?.minPlannedNetProfitUsd)||.25)",'engine_floor_hard')
e=rep(e,"return Math.max(1,ladder,pct)*profileMult;","return Math.max(hard,ladder,pct)*profileMult;",'engine_floor_return')
e=rep(e,"requiredNetUsd=Math.max(1,num(floorUsd))*buffer","requiredNetUsd=Math.max(.12,num(floorUsd))*buffer",'engine_floor_expand')
e=rep(e,"externalMarginUsd:num(portfolioContext?.externalMarginUsd)});","externalMarginUsd:num(portfolioContext?.externalMarginUsd),performanceRiskMult:num(portfolioContext?.performanceRiskMult)||1});",'pre_risk_perf',1)
e=rep(e,"externalMarginUsd:num(portfolioContext?.externalMarginUsd)});","externalMarginUsd:num(portfolioContext?.externalMarginUsd),performanceRiskMult:num(portfolioContext?.performanceRiskMult)||1});",'final_risk_perf',1)
e=rep(e,"scaleRiskMult:num(risk.scale?.riskMult),reason:setup.reason","scaleRiskMult:num(risk.scale?.riskMult),performanceRiskMult:num(risk.performanceRiskMult)||1,reason:setup.reason",'tranche_perf')
e=rep(e,"scaleRiskMult:num(risk.scale?.riskMult),costReserveUsd","scaleRiskMult:num(risk.scale?.riskMult),performanceRiskMult:num(risk.performanceRiskMult)||1,costReserveUsd",'plan_perf')
pattern=r"  const harvestMinEvidence=.*?const harvestReady=cfg\?\.positionControl\?\.profitHarvestExit!==false&&profitReady&&edgeExhausted&&state\.profitHarvestWeakCount>=harvestConfirm&&\(peakGivebackNow>=harvestGiveback\|\|stability\.hard\);\n"
m=re.search(pattern,e,re.S)
if not m:raise SystemExit('MISSING_MARKER:harvest_logic')
new_harvest="""  const harvestMinEvidence=Math.max(3,Math.round((num(cfg?.positionControl?.profitHarvestMinEvidence)||3)*reverseExitEvidenceMult)),harvestConfirm=Math.max(2,Math.round((num(cfg?.positionControl?.profitHarvestConfirmEvents)||2)*reverseExitEvidenceMult)),harvestHoldMult=clamp(num(latest?.coinProfile?.holdMult)||1,.75,1.50),profitGivebackMult=clamp(num(latest?.coinProfile?.profitGivebackMult)||1,.85,1.30),harvestGiveback=Math.max(.20,num(cfg?.positionControl?.profitHarvestPeakGivebackR)||.35)*harvestHoldMult*profitGivebackMult,peakGivebackNow=Math.max(0,num(state.positionPeakR)-r),shortOnly=stability.fastAgainst&&!stability.structureAgainst&&!stability.mediumAgainst&&stability.evidenceCount<harvestMinEvidence,multiStageDeterioration=!shortOnly&&stability.evidenceCount>=harvestMinEvidence&&(stability.structureAgainst||stability.mediumAgainst)&&(stability.bookAgainst||stability.pulseAgainst||stability.fastAgainst||stability.shockAgainst),edgeAlive=supportNow>.04&&!stability.structureAgainst&&!stability.mediumAgainst,edgeExhausted=profitReady&&multiStageDeterioration&&supportNow<-.04;state.profitHarvestWeakCount=edgeExhausted?num(state.profitHarvestWeakCount)+1:Math.max(0,num(state.profitHarvestWeakCount)-(edgeAlive?2:1));const floorHarvestReady=cfg?.positionControl?.profitHarvestExit!==false&&profitReady&&edgeExhausted&&state.profitHarvestWeakCount>=harvestConfirm&&(peakGivebackNow>=harvestGiveback||stability.hard),earlyMinNetUsd=Math.max(.12,num(cfg?.positionControl?.earlyHarvestMinNetUsd)||.18),earlyMinPeakR=Math.max(.30,num(cfg?.positionControl?.earlyHarvestMinPeakR)||.55),earlyMinEvidence=Math.max(2,Math.round(num(cfg?.positionControl?.earlyHarvestMinEvidence)||2)),earlyConfirm=Math.max(1,Math.round(num(cfg?.positionControl?.earlyHarvestConfirmEvents)||2)),earlyGiveback=Math.max(.15,num(cfg?.positionControl?.earlyHarvestGivebackR)||.25),earlyProfitReady=netLiveProfitUsd>=earlyMinNetUsd&&state.positionPeakR>=earlyMinPeakR,earlyDeterioration=earlyProfitReady&&stability.evidenceCount>=earlyMinEvidence&&supportNow<-.03&&(stability.mediumAgainst||stability.structureAgainst||stability.hard||(stability.fastAgainst&&(stability.bookAgainst||stability.pulseAgainst))),earlyWeakCount=earlyDeterioration?num(state.earlyProfitHarvestWeakCount)+1:Math.max(0,num(state.earlyProfitHarvestWeakCount)-(edgeAlive?2:1));state.earlyProfitHarvestWeakCount=earlyWeakCount;const earlyHarvestReady=cfg?.positionControl?.profitHarvestExit!==false&&earlyDeterioration&&earlyWeakCount>=earlyConfirm&&(peakGivebackNow>=earlyGiveback||stability.hard),harvestReady=floorHarvestReady||earlyHarvestReady;\n"""
e=e[:m.start()]+new_harvest+e[m.end():]
e=rep(e,"harvestGivebackR:harvestGiveback,shortMomentumAloneCanExit:false","harvestGivebackR:harvestGiveback,earlyMinNetUsd,earlyMinPeakR,earlyProfitReady,earlyDeterioration,earlyHarvestWeakCount:earlyWeakCount,earlyHarvestReady,shortMomentumAloneCanExit:false",'harvest_telemetry')
e=rep(e,"state.profitHarvestWeakCount=0;state.positionPeakR=0;","state.profitHarvestWeakCount=0;state.earlyProfitHarvestWeakCount=0;state.positionPeakR=0;",'harvest_reset',1)
e=rep(e,"state.profitHarvestWeakCount=0;state.positionPeakR=0;","state.profitHarvestWeakCount=0;state.earlyProfitHarvestWeakCount=0;state.positionPeakR=0;",'loss_reset',1)
e=e.replace('BYBIT-MULTI-ASSET-ENGINE-4.4.0-ANTI-SWEEP-DYNAMIC-SCALP','BYBIT-MULTI-ASSET-ENGINE-4.5.0-EXPECTANCY-CAPITAL-PRESERVATION')
ENGINE.write_text(e)

# Controller: realized PnL governor participates in admission and risk scaling.
ctrl=CTRL.read_text()
ctrl=rep(ctrl,"import {buildBybitDynamicUniverse,updateBybitPromotionEvidence} from './bybit-dynamic-universe.js';","import {buildBybitDynamicUniverse,updateBybitPromotionEvidence} from './bybit-dynamic-universe.js';\nimport {buildBybitPerformanceGovernor,bybitPerformanceDecision} from './bybit-performance-governor.js';",'perf_import')
ctrl=rep(ctrl,"capacityCapital=Math.max(.01,Math.min(equity,num(balance?.state?.continuousCapitalUsd)||equity)),universeState=await buildBybitDynamicUniverse(env,api);","capacityCapital=Math.max(.01,Math.min(equity,num(balance?.state?.continuousCapitalUsd)||equity)),universeState=await buildBybitDynamicUniverse(env,api),performanceState=await buildBybitPerformanceGovernor(env,api,{equityUsd:equity,highWaterUsd:num(balance?.state?.highWaterUsd)});",'perf_state')
old="const symbol=candidate.symbol,portfolioBlock=entryBlockFor({symbol,positions,equity:capacityCapital,newEntryDone:false,ranked}),directionBlock=marketDirectionBlock(candidate,breadth),block=portfolioBlock||directionBlock;const decision={...candidate,marketBreadthSide:breadth.side,marketBreadthAgreement:breadth.agreement,finalBlock:block||null,action:block?'BLOCKED':'FRESH_RECHECK'};candidateDecisions.push(decision);if(block)continue;const ctx=portfolioContext(positions,symbol,balance),r=await runBybitSymbolEngine(env,{symbol,entryBlockReason:null,portfolioContext:ctx});"
new="const symbol=candidate.symbol,portfolioBlock=entryBlockFor({symbol,positions,equity:capacityCapital,newEntryDone:false,ranked}),directionBlock=marketDirectionBlock(candidate,breadth),performanceDecision=bybitPerformanceDecision(performanceState,candidate,equity,num(balance?.state?.highWaterUsd)),block=portfolioBlock||directionBlock||performanceDecision.block;const decision={...candidate,marketBreadthSide:breadth.side,marketBreadthAgreement:breadth.agreement,performanceRiskMult:performanceDecision.riskMult,performanceBlock:performanceDecision.block,performanceSymbol72:performanceDecision.symbol72,finalBlock:block||null,action:block?'BLOCKED':'FRESH_RECHECK'};candidateDecisions.push(decision);if(block)continue;const ctx={...portfolioContext(positions,symbol,balance),performanceRiskMult:performanceDecision.riskMult},r=await runBybitSymbolEngine(env,{symbol,entryBlockReason:null,portfolioContext:ctx});"
ctrl=rep(ctrl,old,new,'controller_perf_admission')
ctrl=rep(ctrl,"candidateDecisions:candidateDecisions.slice(0,8),replacementPolicy","candidateDecisions:candidateDecisions.slice(0,8),performanceGovernor:{authority:'REALIZED_NET_EXPECTANCY_CAPITAL_PRESERVATION',stale:!!performanceState.stale,summary:performanceState.summary,symbols:Object.fromEntries(Object.entries(performanceState.symbols||{}).slice(0,40))},replacementPolicy",'controller_perf_telemetry')
ctrl=ctrl.replace("BYBIT_MULTI_ASSET_CONTROLLER_V4_DYNAMIC_UNIVERSE_CONTINUOUS_SLOTS","BYBIT_MULTI_ASSET_CONTROLLER_V5_EXPECTANCY_CAPITAL_PRESERVATION")
CTRL.write_text(ctrl)

# Runtime contract.
rt=RUNTIME.read_text()
rt=rep(rt,"BYBIT_MULTI_ASSET_RUNTIME_V22_DUAL_LANE_DISCOVERY_PROMOTION","BYBIT_MULTI_ASSET_RUNTIME_V23_REALIZED_EXPECTANCY_CAPITAL_PRESERVATION",'runtime_version')
rt=rep(rt,"BYBIT-MULTI-STATEFLOW-4.4.2","BYBIT-MULTI-STATEFLOW-4.5.0",'auto_version')
rt=rep(rt,"plannedNetProfitFloorStartsAtOneUsd:true","plannedNetProfitFloorStartsAtOneUsd:false,preferredRunnerNetProfitStartsAtOneUsd:true",'runtime_profit_floor')
rt=rep(rt,"strictContrarianException:true,longRunCoreFreeze:true","strictContrarianException:true,realizedPnlPerformanceGovernor:true,perSymbolExpectancyGate:true,lossStreakRequalification:true,performanceAdaptiveRisk:true,smallProfitEarlyHarvest:true,capitalPreservationRecoveryMode:true,longRunCoreFreeze:true",'runtime_perf_flags')
RUNTIME.write_text(rt)

print('BYBIT_V450_EXPECTANCY_RECOVERY_APPLIED')
