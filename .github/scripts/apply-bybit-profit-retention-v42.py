from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CF=ROOT/'cloudflare-worker'

def patch(path, replacements):
    text=path.read_text(encoding='utf-8')
    double_reset="state.profitHarvestWeakCount=0;state.positionPeakR=0;state.aggregateStop=0;state.currentPositionMarginUsd=0;"
    for old,new in replacements:
        expected=2 if old==double_reset else 1
        count=text.count(old)
        if count!=expected:
            raise SystemExit(f'{path}: expected exactly {expected} match(es), got {count}: {old[:120]}')
        text=text.replace(old,new,expected)
    path.write_text(text,encoding='utf-8')

config=CF/'bybit-auto-config.js'
patch(config,[
("// BYBIT-MULTI-STATEFLOW-4.1 PROFIT-SCALE configuration.","// BYBIT-MULTI-STATEFLOW-4.2 PROFIT-RETENTION configuration."),
("authority:'PROFIT_FIRST_HOLD_WHILE_EDGE_PERSISTS',","authority:'PROFIT_FLOOR_RETENTION_EDGE_PERSISTENCE',"),
("""    profitFloorLadder:[
      {equityUsd:0,minNetUsd:1.00},{equityUsd:75,minNetUsd:1.25},{equityUsd:150,minNetUsd:1.75},
      {equityUsd:250,minNetUsd:2.50},{equityUsd:500,minNetUsd:4.00},{equityUsd:1000,minNetUsd:7.00},
      {equityUsd:2500,minNetUsd:15.00},{equityUsd:5000,minNetUsd:30.00},{equityUsd:10000,minNetUsd:50.00}
    ],
    profitFloorBufferMult:1.05,
    requireNetFloorAfterFees:true,
""","""    profitFloorLadder:[
      {equityUsd:0,minNetUsd:1.45},{equityUsd:50,minNetUsd:1.60},{equityUsd:75,minNetUsd:1.80},
      {equityUsd:100,minNetUsd:2.10},{equityUsd:150,minNetUsd:2.60},{equityUsd:250,minNetUsd:3.60},
      {equityUsd:500,minNetUsd:6.00},{equityUsd:1000,minNetUsd:11.00},{equityUsd:2500,minNetUsd:25.00},
      {equityUsd:5000,minNetUsd:50.00},{equityUsd:10000,minNetUsd:90.00}
    ],
    profitFloorBufferMult:1.05,
    requireNetFloorAfterFees:true,
    profitFloorProtectAfterHit:true,
    profitFloorRetentionPct:.82,
"""),
("    shortMomentumAloneCanExit:false,\n    shortMomentumAloneCanCompressTp:false,","    shortMomentumAloneCanExit:false,\n    shortMomentumAloneCanCompressTp:false,\n    profitHarvestRequiresMultiStageInvalidation:true,"),
("    netProfitFloorAfterFees:true,holdWhileEdgePersists:true,multiStageExitEvidence:true","    netProfitFloorAfterFees:true,holdWhileEdgePersists:true,multiStageExitEvidence:true,perSymbolProfitFloor:true,profitFloorRetention:true,priceBasedProfitProtection:true")
])

runtime=CF/'bybit-runtime-contract.js'
patch(runtime,[
("BYBIT_MULTI_ASSET_RUNTIME_V14_PROFIT_SCALE_HARVEST","BYBIT_MULTI_ASSET_RUNTIME_V15_PROFIT_RETENTION_RUNNER"),
("BYBIT-MULTI-STATEFLOW-4.0","BYBIT-MULTI-STATEFLOW-4.2"),
("scalpAuthority:'SCALE_LADDER_NET_PROFIT_THESIS_AWARE_RUNNER'","scalpAuthority:'SCALE_LADDER_NET_PROFIT_RETENTION_THESIS_AWARE_RUNNER'"),
("plannedNetProfitFloorStartsAtOneUsd:true,profitFloorScalesWithEquity:true,nativeTpAlways:true","plannedNetProfitFloorStartsAtOneUsd:true,profitFloorScalesWithEquity:true,perSymbolProfitFloorMultiplier:true,profitFloorRetentionAfterHit:true,shortMomentumAloneCanExit:false,profitHarvestRequiresMultiStageInvalidation:true,nativeTpAlways:true")
])

engine=CF/'bybit-symbol-engine.js'
patch(engine,[
("function plannedProfitFloor(cfg,capitalUsd,setup={}){const capital=Math.max(0,num(capitalUsd)),rows=[...(cfg?.scalp?.profitFloorLadder||[])].sort((a,b)=>num(a.equityUsd)-num(b.equityUsd));let ladder=Math.max(1,num(cfg?.scalp?.minPlannedNetProfitUsd)||1);for(const x of rows)if(capital>=num(x.equityUsd))ladder=Math.max(ladder,num(x.minNetUsd));const pct=capital*Math.max(0,num(cfg?.scalp?.minPlannedNetProfitPct)||0)/100;return Math.max(1,ladder,pct);}",
"function plannedProfitFloor(cfg,capitalUsd,setup={}){const capital=Math.max(0,num(capitalUsd)),rows=[...(cfg?.scalp?.profitFloorLadder||[])].sort((a,b)=>num(a.equityUsd)-num(b.equityUsd));let ladder=Math.max(1,num(cfg?.scalp?.minPlannedNetProfitUsd)||1);for(const x of rows)if(capital>=num(x.equityUsd))ladder=Math.max(ladder,num(x.minNetUsd));const pct=capital*Math.max(0,num(cfg?.scalp?.minPlannedNetProfitPct)||0)/100,profileMult=clamp(num(setup?.coinProfile?.minNetProfitMult)||1,.90,1.25);return Math.max(1,ladder,pct)*profileMult;}"),
("  state.positionPeakR=Math.max(num(state.positionPeakR),r);const cp=latest?.coinProfile||{},holdMult=clamp(num(cp.holdMult)||1,.75,1.50),peakGiveback=Math.max(.35,num(cfg?.scalp?.adaptiveProtection?.peakGivebackR)||.65)*holdMult,peakActivation=Math.max(.8,num(cfg?.scalp?.adaptiveProtection?.peakGivebackActivationR)||1.10);let desired=currentStop,phase=null;if((r>=lockR||decelerating||(stability.hard&&r>=.30))&&canNetLock){",
"  state.positionPeakR=Math.max(num(state.positionPeakR),r);if(profitReady){state.profitFloorHit=true;state.profitFloorHitAt=state.profitFloorHitAt||iso();state.profitFloorPeakNetUsd=Math.max(num(state.profitFloorPeakNetUsd),netLiveProfitUsd);}else if(r<=0){state.profitFloorHit=false;state.profitFloorHitAt=null;state.profitFloorPeakNetUsd=0;}const cp=latest?.coinProfile||{},holdMult=clamp(num(cp.holdMult)||1,.75,1.50),peakGiveback=Math.max(.35,num(cfg?.scalp?.adaptiveProtection?.peakGivebackR)||.65)*holdMult,peakActivation=Math.max(.8,num(cfg?.scalp?.adaptiveProtection?.peakGivebackActivationR)||1.10);let desired=currentStop,phase=null;const retentionPct=clamp(num(cfg?.scalp?.profitFloorRetentionPct)||.82,.55,.95),retainedNetUsd=profitFloorUsd*retentionPct,retainedDistance=positionQty>0?(retainedNetUsd+liveCostReserve)/positionQty:0,retainedGap=Math.max(filters.tickSize*5,d*.08),rawRetentionStop=side==='Buy'?num(latest.entry)+retainedDistance:num(latest.entry)-retainedDistance,retentionStop=side==='Buy'?Math.min(rawRetentionStop,mark-retainedGap):Math.max(rawRetentionStop,mark+retainedGap);if(cfg?.scalp?.profitFloorProtectAfterHit!==false&&state.profitFloorHit&&canNetLock&&retainedDistance>0){desired=tighten(side,desired,retentionStop);phase='PROFIT_FLOOR_RETENTION_LOCK';}if((r>=lockR||decelerating||(stability.hard&&r>=.30))&&canNetLock){"),
("  const softConfirm=Math.max(2,Math.round(num(cfg?.positionControl?.softConfirmEvents)||4)),hardConfirm=Math.max(2,Math.round(num(cfg?.positionControl?.hardConfirmEvents)||2)),minEvidence=Math.max(2,Math.round(num(cfg?.positionControl?.minExitEvidence)||3)),supportNow=positionSupport(side,market),recovering=supportNow>.08&&!stability.structureAgainst&&!stability.mediumAgainst,hardAdverse=Math.max(.10,num(cfg?.positionControl?.hardAdverseRForCut)||.18),softAdverse=Math.max(hardAdverse+.05,num(cfg?.positionControl?.softAdverseRForCut)||.35),adverseDamage=Math.max(0,-r);",
"  const reverseExitEvidenceMult=clamp(num(latest?.coinProfile?.reverseExitEvidenceMult)||1,.90,1.30),softConfirm=Math.max(2,Math.ceil((num(cfg?.positionControl?.softConfirmEvents)||4)*reverseExitEvidenceMult)),hardConfirm=Math.max(2,Math.ceil((num(cfg?.positionControl?.hardConfirmEvents)||2)*reverseExitEvidenceMult)),minEvidence=Math.max(2,Math.ceil((num(cfg?.positionControl?.minExitEvidence)||3)*reverseExitEvidenceMult)),supportNow=positionSupport(side,market),recovering=supportNow>.08&&!stability.structureAgainst&&!stability.mediumAgainst,hardAdverse=Math.max(.10,num(cfg?.positionControl?.hardAdverseRForCut)||.18),softAdverse=Math.max(hardAdverse+.05,num(cfg?.positionControl?.softAdverseRForCut)||.35),adverseDamage=Math.max(0,-r);"),
("  const harvestMinEvidence=Math.max(3,Math.round(num(cfg?.positionControl?.profitHarvestMinEvidence)||3)),harvestConfirm=Math.max(2,Math.round(num(cfg?.positionControl?.profitHarvestConfirmEvents)||3)),holdMult=clamp(num(latest?.coinProfile?.holdMult)||1,.75,1.50),harvestGiveback=Math.max(.25,num(cfg?.positionControl?.profitHarvestPeakGivebackR)||.45)*holdMult,peakGivebackNow=Math.max(0,num(state.positionPeakR)-r),shortOnly=stability.fastAgainst&&!stability.structureAgainst&&!stability.mediumAgainst&&stability.evidenceCount<harvestMinEvidence,multiStageDeterioration=!shortOnly&&stability.evidenceCount>=harvestMinEvidence&&(stability.structureAgainst||stability.mediumAgainst)&&(stability.bookAgainst||stability.pulseAgainst||stability.fastAgainst||stability.shockAgainst),edgeAlive=supportNow>.04&&!stability.structureAgainst&&!stability.mediumAgainst,edgeExhausted=profitReady&&multiStageDeterioration&&supportNow<-.04;",
"  const harvestMinEvidence=Math.max(3,Math.ceil((num(cfg?.positionControl?.profitHarvestMinEvidence)||3)*reverseExitEvidenceMult)),harvestConfirm=Math.max(2,Math.ceil((num(cfg?.positionControl?.profitHarvestConfirmEvents)||3)*reverseExitEvidenceMult)),harvestHoldMult=clamp(num(latest?.coinProfile?.holdMult)||1,.75,1.50),profitGivebackMult=clamp(num(latest?.coinProfile?.profitGivebackMult)||1,.85,1.30),harvestGiveback=Math.max(.25,num(cfg?.positionControl?.profitHarvestPeakGivebackR)||.45)*harvestHoldMult*profitGivebackMult,peakGivebackNow=Math.max(0,num(state.positionPeakR)-r),shortOnly=stability.fastAgainst&&!stability.structureAgainst&&!stability.mediumAgainst&&stability.evidenceCount<harvestMinEvidence,multiStageDeterioration=!shortOnly&&stability.evidenceCount>=harvestMinEvidence&&(stability.structureAgainst||stability.mediumAgainst)&&(stability.bookAgainst||stability.pulseAgainst||stability.fastAgainst||stability.shockAgainst),edgeAlive=supportNow>.04&&!stability.structureAgainst&&!stability.mediumAgainst,edgeExhausted=profitReady&&multiStageDeterioration&&supportNow<-.04;"),
("state.holdLogicVersion='MULTI_STAGE_PROFIT_HARVEST_HOLD_V2';state.lastPositionStability={at:iso(),side,...stability,supportNow,confirmCount:state.invalidationCount,hardConfirmCount:state.hardInvalidationCount,requiredConfirmEvents:softConfirm,requiredHardConfirmEvents:hardConfirm,minExitEvidence:minEvidence,hardReady,softReady,adverseDamageR:adverseDamage,hardAdverseRForCut:hardAdverse,softAdverseRForCut:softAdverse,entryTier:tier,peakR:state.positionPeakR,profitFloorUsd,netLiveProfitUsd,profitReady,edgeAlive,edgeExhausted,harvestWeakCount:state.profitHarvestWeakCount,harvestConfirmEvents:harvestConfirm,peakGivebackR:peakGivebackNow,harvestGivebackR:harvestGiveback,shortMomentumAloneCanExit:false,decision:",
"state.holdLogicVersion='MULTI_STAGE_PROFIT_RETENTION_HOLD_V3';state.lastPositionStability={at:iso(),side,...stability,supportNow,confirmCount:state.invalidationCount,hardConfirmCount:state.hardInvalidationCount,requiredConfirmEvents:softConfirm,requiredHardConfirmEvents:hardConfirm,minExitEvidence:minEvidence,hardReady,softReady,adverseDamageR:adverseDamage,hardAdverseRForCut:hardAdverse,softAdverseRForCut:softAdverse,entryTier:tier,peakR:state.positionPeakR,profitFloorUsd,netLiveProfitUsd,profitReady,profitFloorHit:!!state.profitFloorHit,profitFloorRetentionPct:retentionPct,perSymbolMinNetProfitMult:num(latest?.coinProfile?.minNetProfitMult)||1,reverseExitEvidenceMult,profitGivebackMult,edgeAlive,edgeExhausted,harvestWeakCount:state.profitHarvestWeakCount,harvestConfirmEvents:harvestConfirm,peakGivebackR:peakGivebackNow,harvestGivebackR:harvestGiveback,shortMomentumAloneCanExit:false,decision:"),
("state.profitHarvestWeakCount=0;state.positionPeakR=0;state.aggregateStop=0;state.currentPositionMarginUsd=0;","state.profitHarvestWeakCount=0;state.positionPeakR=0;state.profitFloorHit=false;state.profitFloorHitAt=null;state.profitFloorPeakNetUsd=0;state.aggregateStop=0;state.currentPositionMarginUsd=0;"),
("BYBIT-MULTI-ASSET-ENGINE-4.0-PROFIT-HARVEST","BYBIT-MULTI-ASSET-ENGINE-4.2-PROFIT-RETENTION")
])

validator=CF/'validate-btc-hyperscale.mjs'
patch(validator,[
("assert.ok(p.runnerMaxR>=2.5);assert.ok(p.minTurnoverUsd>0);","assert.ok(p.runnerMaxR>=2.5);assert.ok(p.minTurnoverUsd>0);assert.ok(p.minNetProfitMult>=.9);assert.ok(p.profitGivebackMult>=.85);assert.ok(p.reverseExitEvidenceMult>=.9);"),
("assert.equal(cfg.positionControl.shortMomentumAloneCanCompressTp,false);assert.ok(cfg.scalp.trailStartR>=1.4);","assert.equal(cfg.positionControl.shortMomentumAloneCanCompressTp,false);assert.equal(cfg.positionControl.profitHarvestRequiresMultiStageInvalidation,true);assert.equal(cfg.scalp.profitFloorProtectAfterHit,true);assert.ok(cfg.scalp.profitFloorRetentionPct>=.75);assert.ok(cfg.scalp.trailStartR>=1.4);"),
("'PEAK_GIVEBACK_LOCK','expandSetupToProfitFloor','PROFIT_HARVEST_EDGE_EXHAUSTED','MULTI_STAGE_PROFIT_HARVEST_HOLD_V2','BYBIT-MULTI-ASSET-ENGINE-4.0-PROFIT-HARVEST'","'PEAK_GIVEBACK_LOCK','PROFIT_FLOOR_RETENTION_LOCK','expandSetupToProfitFloor','PROFIT_HARVEST_EDGE_EXHAUSTED','MULTI_STAGE_PROFIT_RETENTION_HOLD_V3','BYBIT-MULTI-ASSET-ENGINE-4.2-PROFIT-RETENTION'"),
("'BYBIT_MULTI_ASSET_RUNTIME_V14_PROFIT_SCALE_HARVEST','multiAsset:true','PER_SYMBOL_COGNITION_STATE_FIRST'","'BYBIT_MULTI_ASSET_RUNTIME_V15_PROFIT_RETENTION_RUNNER','multiAsset:true','PER_SYMBOL_COGNITION_STATE_FIRST','profitFloorRetentionAfterHit:true','shortMomentumAloneCanExit:false'"),
("version:'BYBIT-MULTI-STATEFLOW-4.0'","version:'BYBIT-MULTI-STATEFLOW-4.2'"),
("profitHarvest:true,shortMomentumAloneExit:false","profitHarvest:true,profitFloorRetention:true,perSymbolProfitFloor:true,shortMomentumAloneExit:false")
])

print('BYBIT_V42_PATCH_APPLIED=1')
