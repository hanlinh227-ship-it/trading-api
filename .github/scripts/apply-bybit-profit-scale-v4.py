from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
CW=ROOT/'cloudflare-worker'

def read(path): return path.read_text(encoding='utf-8')
def write(path,text): path.write_text(text,encoding='utf-8')
def once(text,old,new,label):
    n=text.count(old)
    if n!=1: raise SystemExit(f'{label}: expected 1 anchor, found {n}')
    return text.replace(old,new,1)
def rex(text,pat,repl,label,flags=0):
    out,n=re.subn(pat,repl,text,count=1,flags=flags)
    if n!=1: raise SystemExit(f'{label}: expected 1 regex match, found {n}')
    return out

# 1) Global config: planned NET profit ladder, later/wider runner protection,
# and explicit rule that short-horizon reverse momentum alone cannot exit/compress.
p=CW/'bybit-auto-config.js'; s=read(p)
s=once(s,'// BYBIT-MULTI-STATEFLOW-3.0 configuration.','// BYBIT-MULTI-STATEFLOW-4.0 PROFIT-SCALE configuration.','config version')
s=once(s,"    minPlannedNetProfitUsd:.06,\n    minPlannedNetProfitPct:.15,\n    profitLockR:.52,\n    trailStartR:1.18,\n    trailRange5Pct:.16,\n    trailPricePct:.00130,\n    netProfitLockBufferMult:1.08,",
"    minPlannedNetProfitUsd:1.00,\n    minPlannedNetProfitPct:.15,\n    profitFloorLadder:[\n      {equityUsd:0,minNetUsd:1.00},{equityUsd:75,minNetUsd:1.25},{equityUsd:150,minNetUsd:1.75},\n      {equityUsd:250,minNetUsd:2.50},{equityUsd:500,minNetUsd:4.00},{equityUsd:1000,minNetUsd:7.00},\n      {equityUsd:2500,minNetUsd:15.00},{equityUsd:5000,minNetUsd:30.00},{equityUsd:10000,minNetUsd:50.00}\n    ],\n    profitFloorBufferMult:1.05,\n    requireNetFloorAfterFees:true,\n    profitLockR:.70,\n    trailStartR:1.55,\n    trailRange5Pct:.20,\n    trailPricePct:.00160,\n    netProfitLockBufferMult:1.10,",'config profit ladder')
s=once(s,"      probeBaseTargetR:1.85,\n      confirmBaseTargetR:2.20,\n      fullBaseTargetR:2.70,\n      minTargetR:1.30,\n      maxTargetR:4.80,\n      strongExtensionR:.65,\n      weakCompressionR:.18,",
"      probeBaseTargetR:2.00,\n      confirmBaseTargetR:2.45,\n      fullBaseTargetR:3.00,\n      minTargetR:1.45,\n      maxTargetR:5.50,\n      strongExtensionR:.75,\n      weakCompressionR:.12,",'config target envelope')
s=once(s,"    profitableMarketExit:false,\n    highVolShockAdverseExit:true,",
"    profitableMarketExit:false,\n    profitHarvestExit:true,\n    profitHarvestMinEvidence:3,\n    profitHarvestConfirmEvents:3,\n    profitHarvestPeakGivebackR:.45,\n    shortMomentumAloneCanExit:false,\n    shortMomentumAloneCanCompressTp:false,\n    highVolShockAdverseExit:true,",'config harvest controls')
s=once(s,'portfolioCorrelationGuard:true,peakGivebackProtection:true','portfolioCorrelationGuard:true,peakGivebackProtection:true,profitScaleLadder:true,thesisAwareProfitHarvest:true','config features')
write(p,s)

# 2) Per-symbol setup targets: scalp means meaningful target first, while each coin still keeps its own runner cap.
p=CW/'bybit-symbol-strategy.js'; s=read(p)
s=once(s,"base=tier==='PROBE'?1.65:tier==='FULL'?2.45:2.05","base=tier==='PROBE'?1.80:tier==='FULL'?2.85:2.30",'strategy target tier')
s=s.replace("BYBIT_SYMBOL_COGNITION_V1_PROFILED_STATEFLOW","BYBIT_SYMBOL_COGNITION_V2_PROFIT_SCALE_STATEFLOW")
write(p,s)

# 3) Symbol engine: enforce a NET profit floor after fees without breaking risk caps.
p=CW/'bybit-symbol-engine.js'; s=read(p)
s=s.replace('BYBIT-MULTI-ASSET-ENGINE-3.0-PROFILED','BYBIT-MULTI-ASSET-ENGINE-4.0-PROFIT-HARVEST')
old="function plannedProfitFloor(cfg,capitalUsd,setup={}){const base=Math.max(Math.max(0,num(cfg?.scalp?.minPlannedNetProfitUsd)||.06),Math.max(0,num(capitalUsd))*Math.max(0,num(cfg?.scalp?.minPlannedNetProfitPct)||.15)/100),tier=String(setup?.entryTier||'CONFIRM'),mult=tier==='PROBE'?.70:tier==='CONFIRM'?.85:1;return base*mult;}"
new="""function plannedProfitFloor(cfg,capitalUsd,setup={}){const capital=Math.max(0,num(capitalUsd)),rows=[...(cfg?.scalp?.profitFloorLadder||[])].sort((a,b)=>num(a.equityUsd)-num(b.equityUsd));let ladder=Math.max(1,num(cfg?.scalp?.minPlannedNetProfitUsd)||1);for(const x of rows)if(capital>=num(x.equityUsd))ladder=Math.max(ladder,num(x.minNetUsd));const pct=capital*Math.max(0,num(cfg?.scalp?.minPlannedNetProfitPct)||0)/100;return Math.max(1,ladder,pct);}
function expandSetupToProfitFloor(setup={},sized={},floorUsd=1,cfg={}){const entry=num(setup.entry),sl=num(setup.sl),qty=Math.abs(num(sized.qty)),d=Math.abs(entry-sl),cost=Math.max(0,num(sized.costReserveUsd));if(!(entry>0&&d>0&&qty>0))return {ok:false,reason:'PROFIT_FLOOR_GEOMETRY_INVALID'};const buffer=Math.max(1,num(cfg?.scalp?.profitFloorBufferMult)||1.05),requiredNetUsd=Math.max(1,num(floorUsd))*buffer,requiredGross=requiredNetUsd+cost,requiredDist=requiredGross/qty,requiredR=requiredDist/d,currentR=Math.abs(num(setup.tp)-entry)/d,apMax=Math.max(1,num(cfg?.scalp?.adaptiveProtection?.maxTargetR)||5.5),profileMax=Math.max(1,num(setup?.coinProfile?.runnerMaxR)||apMax),maxRunnerR=Math.min(apMax,profileMax),targetR=Math.max(currentR,requiredR);if(targetR>maxRunnerR+1e-9)return {ok:false,reason:'PROFIT_FLOOR_REQUIRES_EXCESSIVE_RUNNER',requiredNetUsd,requiredR,maxRunnerR};const tp=String(setup.side)==='Buy'?entry+d*targetR:entry-d*targetR;return {ok:true,requiredNetUsd,requiredR,targetR,maxRunnerR,setup:{...setup,tp,rr:targetR,profitFloorAdjusted:targetR>currentR+1e-9,profitFloorUsd:floorUsd,requiredNetProfitUsd:requiredNetUsd}};}"""
s=once(s,old,new,'engine profit floor helper')
s=once(s,'  const setup=picked.setup,preRisk=','  let setup={...picked.setup};const preRisk=','engine mutable setup')
pat=r"  const capitalUsd=num\(preRisk\.capital\?\.capitalBaseUsd\)\|\|equity,plannedGrossProfitUsd=.*?\n  const risk=btcRiskDecision"
repl="""  const capitalUsd=num(preRisk.capital?.capitalBaseUsd)||equity,minPlannedNetProfitUsd=plannedProfitFloor(cfg,capitalUsd,setup),floorPlan=expandSetupToProfitFloor(setup,sized,minPlannedNetProfitUsd,cfg);if(!floorPlan.ok){state.lastRiskReject={at:iso(),reason:'PLANNED_NET_PROFIT_FLOOR_NOT_FEASIBLE_WITHIN_RUNNER',plannedNetProfitUsd:0,minPlannedNetProfitUsd,requiredNetProfitUsd:floorPlan.requiredNetUsd||null,requiredR:floorPlan.requiredR||null,maxRunnerR:floorPlan.maxRunnerR||null,entryTier:setup.entryTier};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:'PLANNED_NET_PROFIT_FLOOR_NOT_FEASIBLE_WITHIN_RUNNER',plannedProfit:{netUsd:0,minNetUsd:minPlannedNetProfitUsd,requiredNetUsd:floorPlan.requiredNetUsd||null,requiredR:floorPlan.requiredR||null,maxRunnerR:floorPlan.maxRunnerR||null},risk:preRisk,size:sized,market,scan,lifecycles:managed.events,state,plan:clusterPlan(state,pos,setup)};}setup=floorPlan.setup;const plannedGrossProfitUsd=Math.abs(num(setup.tp)-num(setup.entry))*sized.qty,plannedNetProfitUsd=Math.max(0,plannedGrossProfitUsd-num(sized.costReserveUsd));if(plannedNetProfitUsd+1e-9<floorPlan.requiredNetUsd){state.lastRiskReject={at:iso(),reason:'PLANNED_NET_PROFIT_BELOW_SCALE_FLOOR',plannedNetProfitUsd,minPlannedNetProfitUsd,requiredNetProfitUsd:floorPlan.requiredNetUsd,entryTier:setup.entryTier};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:'PLANNED_NET_PROFIT_BELOW_SCALE_FLOOR',plannedProfit:{grossUsd:plannedGrossProfitUsd,netUsd:plannedNetProfitUsd,minNetUsd:minPlannedNetProfitUsd,requiredNetUsd:floorPlan.requiredNetUsd},risk:preRisk,size:sized,market,scan,lifecycles:managed.events,state,plan:clusterPlan(state,pos,setup)};}
  const risk=btcRiskDecision"""
s=rex(s,pat,repl,'engine entry floor expansion',re.S)

# Replace adaptive target planner. Reverse 1s/3s noise is diagnostic only; TP compression requires thesis-level multi-stage degradation.
pat=r"function adaptiveTargetPlan\(side,latest,mark,market,stability,cfg,d,tick,r\)\{.*?\}\nasync function manageCluster"
repl="""function adaptiveTargetPlan(side,latest,mark,market,stability,cfg,d,tick,r){const ap=cfg?.scalp?.adaptiveProtection||{},tier=String(latest?.entryTier||'CONFIRM'),cp=latest?.coinProfile||{},targetMult=clamp(num(cp.targetMult)||1,.75,1.35),base=(tier==='PROBE'?num(ap.probeBaseTargetR)||2.00:tier==='FULL'?num(ap.fullBaseTargetR)||3.00:num(ap.confirmBaseTargetR)||2.45)*targetMult,minR=Math.max(.8,num(ap.minTargetR)||1.45),maxR=Math.min(Math.max(minR,num(ap.maxTargetR)||5.50),Math.max(minR,num(cp.runnerMaxR)||num(ap.maxTargetR)||5.50)),support=positionSupport(side,market),strong=Math.max(0,support),weak=Math.max(0,-support),extend=Math.max(0,num(ap.strongExtensionR)||.75),compress=Math.max(0,num(ap.weakCompressionR)||.12),degradeConfirmed=stability.evidenceCount>=3&&(stability.structureAgainst||stability.mediumAgainst)&&(stability.bookAgainst||stability.pulseAgainst||stability.fastAgainst||stability.shockAgainst),weakApplied=degradeConfirmed?weak:0;let targetR=clamp(base+strong*extend-weakApplied*compress,minR,maxR);const entry=num(latest?.entry),gap=Math.max(tick*8,d*Math.max(.06,num(ap.minLiveGapR)||.20));let target=side==='Buy'?entry+d*targetR:entry-d*targetR;if(side==='Buy')target=Math.max(target,mark+gap);else target=Math.min(target,mark-gap);return {target:roundTick(target,tick),targetR,support,supportPct:Math.round(clamp(50+support*50,0,100)),baseTargetR:base,minR,maxR,degradeConfirmed,shortMomentumAloneCanCompressTp:false};}
async function manageCluster"""
s=rex(s,pat,repl,'engine adaptive target',re.S)

# Compute live NET profit floor before trailing; pre-floor trailing is disabled so a valid scalp is not mechanically strangled before its intended payout.
anchor="decelerationPeakMinR)||.65);\n  state.positionPeakR="
insert="""decelerationPeakMinR)||.65);
  const capitalBaseForFloor=Math.max(0,num(latest.capitalBaseUsd)||num(state.lastCapitalBaseUsd)),profitFloorUsd=plannedProfitFloor(cfg,capitalBaseForFloor,latest),positionQty=Math.abs(num(position.size)||num(latest.qty)),liveCostReserve=Math.max(Math.max(0,num(latest.costReserveUsd)),mark*positionQty*costBps/10000),grossLiveProfitUsd=Math.max(0,favour*positionQty),netLiveProfitUsd=Math.max(0,grossLiveProfitUsd-liveCostReserve),profitReady=netLiveProfitUsd+1e-9>=profitFloorUsd;
  state.positionPeakR="""
s=once(s,anchor,insert,'engine live profit metrics')
s=once(s,'if(r>=trailR){','if(r>=trailR&&profitReady){','engine defer trailing until floor')
s=once(s,'desiredTarget=adaptive?.target||currentTarget,targetMoveFloor=',"rawDesiredTarget=adaptive?.target||currentTarget,floorGrossUsd=profitFloorUsd+liveCostReserve,floorDistance=positionQty>0?floorGrossUsd/positionQty:0,floorTarget=side==='Buy'?num(latest.entry)+floorDistance:num(latest.entry)-floorDistance,enforceFloorTarget=!latest.reconciledExternalPosition,desiredTarget=!profitReady&&enforceFloorTarget?extendTarget(side,rawDesiredTarget,floorTarget):rawDesiredTarget,targetMoveFloor=",'engine floor-aware dynamic target')

# Replace the close-decision tail with separate LOSS CUT and PROFIT HARVEST authorities.
pat=r"  const softConfirm=Math\.max\(2,Math\.round\(num\(cfg\?\.positionControl\?\.softConfirmEvents\)\|\|4\)\).*?return \{state,events,position,cut:false\};\}"
repl="""  const softConfirm=Math.max(2,Math.round(num(cfg?.positionControl?.softConfirmEvents)||4)),hardConfirm=Math.max(2,Math.round(num(cfg?.positionControl?.hardConfirmEvents)||2)),minEvidence=Math.max(2,Math.round(num(cfg?.positionControl?.minExitEvidence)||3)),supportNow=positionSupport(side,market),recovering=supportNow>.08&&!stability.structureAgainst&&!stability.mediumAgainst,hardAdverse=Math.max(.10,num(cfg?.positionControl?.hardAdverseRForCut)||.18),softAdverse=Math.max(hardAdverse+.05,num(cfg?.positionControl?.softAdverseRForCut)||.35),adverseDamage=Math.max(0,-r);state.invalidationCount=stability.soft?num(state.invalidationCount)+1:Math.max(0,num(state.invalidationCount)-(recovering?2:1));state.hardInvalidationCount=stability.hard?num(state.hardInvalidationCount)+1:Math.max(0,num(state.hardInvalidationCount)-1);const hardReady=stability.hard&&stability.evidenceCount>=minEvidence&&state.hardInvalidationCount>=hardConfirm&&adverseDamage>=hardAdverse,softReady=stability.soft&&stability.evidenceCount>=Math.max(2,minEvidence-1)&&state.invalidationCount>=softConfirm&&adverseDamage>=softAdverse,profitable=r>0,allowProfitableExit=cfg?.positionControl?.profitableMarketExit===true;
  const harvestMinEvidence=Math.max(3,Math.round(num(cfg?.positionControl?.profitHarvestMinEvidence)||3)),harvestConfirm=Math.max(2,Math.round(num(cfg?.positionControl?.profitHarvestConfirmEvents)||3)),holdMult=clamp(num(latest?.coinProfile?.holdMult)||1,.75,1.50),harvestGiveback=Math.max(.25,num(cfg?.positionControl?.profitHarvestPeakGivebackR)||.45)*holdMult,peakGivebackNow=Math.max(0,num(state.positionPeakR)-r),shortOnly=stability.fastAgainst&&!stability.structureAgainst&&!stability.mediumAgainst&&stability.evidenceCount<harvestMinEvidence,multiStageDeterioration=!shortOnly&&stability.evidenceCount>=harvestMinEvidence&&(stability.structureAgainst||stability.mediumAgainst)&&(stability.bookAgainst||stability.pulseAgainst||stability.fastAgainst||stability.shockAgainst),edgeAlive=supportNow>.04&&!stability.structureAgainst&&!stability.mediumAgainst,edgeExhausted=profitReady&&multiStageDeterioration&&supportNow<-.04;state.profitHarvestWeakCount=edgeExhausted?num(state.profitHarvestWeakCount)+1:Math.max(0,num(state.profitHarvestWeakCount)-(edgeAlive?2:1));const harvestReady=cfg?.positionControl?.profitHarvestExit!==false&&profitReady&&edgeExhausted&&state.profitHarvestWeakCount>=harvestConfirm&&(peakGivebackNow>=harvestGiveback||stability.hard);
  state.holdLogicVersion='MULTI_STAGE_PROFIT_HARVEST_HOLD_V2';state.lastPositionStability={at:iso(),side,...stability,supportNow,confirmCount:state.invalidationCount,hardConfirmCount:state.hardInvalidationCount,requiredConfirmEvents:softConfirm,requiredHardConfirmEvents:hardConfirm,minExitEvidence:minEvidence,hardReady,softReady,adverseDamageR:adverseDamage,hardAdverseRForCut:hardAdverse,softAdverseRForCut:softAdverse,entryTier:tier,peakR:state.positionPeakR,profitFloorUsd,netLiveProfitUsd,profitReady,edgeAlive,edgeExhausted,harvestWeakCount:state.profitHarvestWeakCount,harvestConfirmEvents:harvestConfirm,peakGivebackR:peakGivebackNow,harvestGivebackR:harvestGiveback,shortMomentumAloneCanExit:false,decision:harvestReady?'HARVEST':(hardReady||softReady)&&(allowProfitableExit||!profitable)?'CUT':'HOLD'};
  if(harvestReady&&liveMode(env)==='LIVE'){const out=await api.order({symbol:SYMBOL,side:side==='Buy'?'Sell':'Buy',orderType:'Market',qty:String(position.size),reduceOnly:true,positionIdx:0});state=closeAllTranches(state,{closeReason:'PROFIT_HARVEST_EDGE_EXHAUSTED'});state.invalidationCount=0;state.hardInvalidationCount=0;state.profitHarvestWeakCount=0;state.positionPeakR=0;state.aggregateStop=0;state.currentPositionMarginUsd=0;state.currentPositionLeverage=0;state.lastCutAt=iso();state.lastExitThesis={at:state.lastCutAt,reason:'PROFIT_HARVEST_EDGE_EXHAUSTED',side,markPrice:mark,stability,netLiveProfitUsd,profitFloorUsd,reentryPolicy:'FRESH_THESIS_ONLY',recoveryMartingale:false,holdLogicVersion:state.holdLogicVersion};events.push({symbol:SYMBOL,cutExecuted:true,verdict:'CUT',reason:'PROFIT_HARVEST_EDGE_EXHAUSTED',orderId:out?.result?.orderId,markPrice:mark,r,netLiveProfitUsd,profitFloorUsd,stabilityScore:stability.score,evidenceCount:stability.evidenceCount,profitHarvest:true,reentryPolicy:'FRESH_THESIS_ONLY'});return {state,events,position:null,cut:true};}
  const lossExitNow=cfg?.positionControl?.instabilityExit!==false&&(allowProfitableExit||!profitable)&&(hardReady||softReady);if(lossExitNow&&liveMode(env)==='LIVE'){const reason=hardReady?'MARKET_INSTABILITY_HARD_EXIT':'STRUCTURE_FLOW_INSTABILITY_EXIT',hardCountBefore=state.hardInvalidationCount,softCountBefore=state.invalidationCount,out=await api.order({symbol:SYMBOL,side:side==='Buy'?'Sell':'Buy',orderType:'Market',qty:String(position.size),reduceOnly:true,positionIdx:0});state=closeAllTranches(state,{closeReason:reason});state.invalidationCount=0;state.hardInvalidationCount=0;state.profitHarvestWeakCount=0;state.positionPeakR=0;state.aggregateStop=0;state.currentPositionMarginUsd=0;state.currentPositionLeverage=0;state.lastCutAt=iso();state.lastExitThesis={at:state.lastCutAt,reason,side,markPrice:mark,stability,reentryPolicy:'FRESH_THESIS_ONLY',recoveryMartingale:false,holdLogicVersion:state.holdLogicVersion};events.push({symbol:SYMBOL,cutExecuted:true,verdict:'CUT',reason,orderId:out?.result?.orderId,markPrice:mark,r,stabilityScore:stability.score,evidenceCount:stability.evidenceCount,hardConfirmCount:hardCountBefore,softConfirmCount:softCountBefore,reentryPolicy:'FRESH_THESIS_ONLY'});return {state,events,position:null,cut:true};}return {state,events,position,cut:false};}"""
s=rex(s,pat,repl,'engine harvest/loss close tail',re.S)
write(p,s)

# 4) Runtime contract advertises the actual profit-scale/harvest semantics.
p=CW/'bybit-runtime-contract.js'; s=read(p)
s=s.replace("BYBIT_MULTI_ASSET_RUNTIME_V13_PROFILED_STATEFLOW","BYBIT_MULTI_ASSET_RUNTIME_V14_PROFIT_SCALE_HARVEST")
s=s.replace("BYBIT-MULTI-STATEFLOW-3.0","BYBIT-MULTI-STATEFLOW-4.0")
s=s.replace("scalpAuthority:'REGIME_AND_PROFILE_ADAPTIVE_NET_EDGE'","scalpAuthority:'SCALE_LADDER_NET_PROFIT_THESIS_AWARE_RUNNER'")
s=s.replace("plannedNetProfitFloor:true,nativeTpAlways:true","plannedNetProfitFloor:true,plannedNetProfitFloorStartsAtOneUsd:true,profitFloorScalesWithEquity:true,nativeTpAlways:true")
s=s.replace("positionExitAuthority:'MULTI_STAGE_STRUCTURE_FLOW_STABILITY_EXIT'","positionExitAuthority:'LOSS_THESIS_INVALIDATION_PLUS_PROFIT_HARVEST_EDGE_EXHAUSTION'")
write(p,s)

# 5) Validator: retain risk safeguards and explicitly test new semantics.
p=CW/'validate-btc-hyperscale.mjs'; s=read(p)
s=s.replace("BYBIT-MULTI-ASSET-ENGINE-3.0-PROFILED","BYBIT-MULTI-ASSET-ENGINE-4.0-PROFIT-HARVEST")
s=s.replace("BYBIT_MULTI_ASSET_RUNTIME_V13_PROFILED_STATEFLOW","BYBIT_MULTI_ASSET_RUNTIME_V14_PROFIT_SCALE_HARVEST")
s=s.replace("BYBIT_SYMBOL_COGNITION_V1_PROFILED_STATEFLOW","BYBIT_SYMBOL_COGNITION_V2_PROFIT_SCALE_STATEFLOW")
s=s.replace("version:'BYBIT-MULTI-STATEFLOW-3.0'","version:'BYBIT-MULTI-STATEFLOW-4.0'")
needle="const quant=sizeBtcSetup"
extra="""const ladder=cfg.scalp.profitFloorLadder;assert.ok(Array.isArray(ladder)&&ladder.length>=5);assert.ok(cfg.scalp.minPlannedNetProfitUsd>=1);assert.ok(ladder[0].minNetUsd>=1);for(let i=1;i<ladder.length;i++){assert.ok(ladder[i].equityUsd>ladder[i-1].equityUsd);assert.ok(ladder[i].minNetUsd>=ladder[i-1].minNetUsd);}assert.equal(cfg.scalp.requireNetFloorAfterFees,true);assert.equal(cfg.positionControl.profitableMarketExit,false);assert.equal(cfg.positionControl.profitHarvestExit,true);assert.equal(cfg.positionControl.shortMomentumAloneCanExit,false);assert.equal(cfg.positionControl.shortMomentumAloneCanCompressTp,false);assert.ok(cfg.scalp.trailStartR>=1.4);assert.ok(cfg.risk.absoluteSingleEntryRiskPct<=1.6);
const quant=sizeBtcSetup"""
s=once(s,needle,extra,'validator ladder asserts')
s=once(s,"for(const x of ['createSymbolEngine','portfolioContext','externalActiveRiskUsd','PEAK_GIVEBACK_LOCK','BYBIT-MULTI-ASSET-ENGINE-4.0-PROFIT-HARVEST'])", "for(const x of ['createSymbolEngine','portfolioContext','externalActiveRiskUsd','PEAK_GIVEBACK_LOCK','expandSetupToProfitFloor','PROFIT_HARVEST_EDGE_EXHAUSTED','MULTI_STAGE_PROFIT_HARVEST_HOLD_V2','BYBIT-MULTI-ASSET-ENGINE-4.0-PROFIT-HARVEST'])",'validator engine strings')
s=s.replace('peakGiveback:true}', 'peakGiveback:true,profitFloorStartsAtOneUsd:true,profitHarvest:true,shortMomentumAloneExit:false}')
write(p,s)

print('BYBIT_PROFIT_SCALE_V4_PATCH=APPLIED')
