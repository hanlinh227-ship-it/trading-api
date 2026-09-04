from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CF=ROOT/'cloudflare-worker'
BRIDGE=ROOT/'bybit-live-bridge'/'bybit_live_bridge.py'

def patch(path,replacements):
    text=path.read_text(encoding='utf-8')
    for old,new,count in replacements:
        got=text.count(old)
        if got!=count:
            raise SystemExit(f'{path}: expected {count} match(es), got {got}: {old[:180]}')
        text=text.replace(old,new,count)
    path.write_text(text,encoding='utf-8')

# 1) Profit floor remains >$1 at small scale, but stops starving valid entries.
config=CF/'bybit-auto-config.js'
patch(config,[
("// BYBIT-MULTI-STATEFLOW-4.2 PROFIT-RETENTION configuration.","// BYBIT-MULTI-STATEFLOW-4.3 OBJECTIVE-PROFIT-EFFICIENCY configuration.",1),
("min:3,max:20,authority:'EQUITY_TAPERED_CLUSTER_LEVERAGE',holdConstantInsideOpenCluster:true,","min:3,max:20,authority:'EQUITY_TAPERED_CLUSTER_LEVERAGE',holdConstantInsideOpenCluster:true,profitFloorAdaptive:true,profitFloorMax:20,",1),
("authority:'PROFIT_FLOOR_RETENTION_EDGE_PERSISTENCE',","authority:'OBJECTIVE_PROFIT_FLOOR_EDGE_PERSISTENCE',",1),
("    // Existing engine applies tier multipliers .70/.85/1.00. 1.45 keeps every tier above ~$1 planned net after fee reserve.\n    minPlannedNetProfitUsd:1.45,","    // Hard entry floor is >$1 net at low scale. Larger profits come from runners, not by starving valid entries.\n    minPlannedNetProfitUsd:1.05,",1),
("""    profitFloorLadder:[
      {equityUsd:0,minNetUsd:1.45},{equityUsd:50,minNetUsd:1.60},{equityUsd:75,minNetUsd:1.80},
      {equityUsd:100,minNetUsd:2.10},{equityUsd:150,minNetUsd:2.60},{equityUsd:250,minNetUsd:3.60},
      {equityUsd:500,minNetUsd:6.00},{equityUsd:1000,minNetUsd:11.00},{equityUsd:2500,minNetUsd:25.00},
      {equityUsd:5000,minNetUsd:50.00},{equityUsd:10000,minNetUsd:90.00}
    ],
    profitFloorBufferMult:1.05,
""","""    profitFloorLadder:[
      {equityUsd:0,minNetUsd:1.05},{equityUsd:50,minNetUsd:1.25},{equityUsd:75,minNetUsd:1.50},
      {equityUsd:100,minNetUsd:1.80},{equityUsd:150,minNetUsd:2.30},{equityUsd:250,minNetUsd:3.25},
      {equityUsd:500,minNetUsd:5.50},{equityUsd:1000,minNetUsd:10.00},{equityUsd:2500,minNetUsd:22.00},
      {equityUsd:5000,minNetUsd:45.00},{equityUsd:10000,minNetUsd:80.00}
    ],
    profitFloorBufferMult:1.04,
""",1),
("    profitFloorRetentionPct:.82,","    profitFloorRetentionPct:.82,\n    profitPeakRetentionPct:.58,",1),
("    netProfitFloorAfterFees:true,holdWhileEdgePersists:true,multiStageExitEvidence:true,perSymbolProfitFloor:true,profitFloorRetention:true,priceBasedProfitProtection:true","    netProfitFloorAfterFees:true,holdWhileEdgePersists:true,multiStageExitEvidence:true,perSymbolProfitFloor:true,profitFloorRetention:true,priceBasedProfitProtection:true,profitFloorAdaptiveLeverage:true,profileNormalizedQuality:true,peakNetProfitRetention:true",1)
])

# 2) Normalize quality by each symbol's liquidity profile instead of a fixed $50k/15s target.
strategy=CF/'bybit-symbol-strategy.js'
patch(strategy,[
("function qualityScore(s={}){const w=s.trades?.window15s||{},trades=num(w.trades),notional=num(w.totalNotional||s.trades?.notional15s),fresh=s.quality?.wsFastPath?1:s.quality?.freshTrades?.72:.35;return clamp(.34*clamp(trades/28,0,1)+.36*clamp(notional/50000,0,1)+.30*fresh,0,1);}",
"function qualityScore(s={},p={}){const w=s.trades?.window15s||{},trades=num(w.trades),notional=num(w.totalNotional||s.trades?.notional15s),fresh=s.quality?.wsFastPath?1:s.quality?.freshTrades?.72:.35,minTurnover=Math.max(1,num(p.minTurnoverUsd)||25000000),notionalTarget=clamp(minTurnover/5760*1.8,5000,50000);return clamp(.34*clamp(trades/28,0,1)+.36*clamp(notional/notionalTarget,0,1)+.30*fresh,0,1);}",1),
("function specializedSetup(s={},p={}){const q=qualityScore(s),score=","function specializedSetup(s={},p={}){const q=qualityScore(s,p),score=",1)
])

# 3) More complete event-driven coverage without scanning all 18 on every tick.
profiles=CF/'bybit-coin-profiles.js'
patch(profiles,[
("authority:'MAJOR_CAP_LIQUIDITY_PROFILE_PORTFOLIO_V2_PROFIT_EFFICIENCY',","authority:'MAJOR_CAP_LIQUIDITY_PROFILE_PORTFOLIO_V3_OBJECTIVE_COVERAGE',",1),
("  deepScanCount:3,","  deepScanCount:6,",1)
])

# 4) Fix primary curl wakeups losing the symbol header; widen event drivers to the 10 most liquid profiles.
patch(BRIDGE,[
("EVENT_SYMBOLS=set(x.strip().upper() for x in os.environ.get('BYBIT_EVENT_SYMBOLS','BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,DOGEUSDT').split(',') if x.strip())",
"EVENT_SYMBOLS=set(x.strip().upper() for x in os.environ.get('BYBIT_EVENT_SYMBOLS','BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,DOGEUSDT,ADAUSDT,LINKUSDT,LTCUSDT,TRXUSDT').split(',') if x.strip())",1),
("            f'header = \"x-action-key: {secret}\"','header = \"x-btc-trigger: VPS_WS_EVENT\"',f'header = \"x-btc-trigger-reason: {reason}\"',",
"            f'header = \"x-action-key: {secret}\"','header = \"x-btc-trigger: VPS_WS_EVENT\"',f'header = \"x-bybit-symbol: {self._curl_q(self.symbol)}\"',f'header = \"x-btc-trigger-reason: {reason}\"',",1)
])

# 5) Hold winners, but remove accidental ceil-overstrictness; protect a share of peak NET profit by price, not short-momentum exits.
engine=CF/'bybit-symbol-engine.js'
patch(engine,[
("const retentionPct=clamp(num(cfg?.scalp?.profitFloorRetentionPct)||.82,.55,.95),retainedNetUsd=profitFloorUsd*retentionPct,retainedDistance=positionQty>0?(retainedNetUsd+liveCostReserve)/positionQty:0,",
"const retentionPct=clamp(num(cfg?.scalp?.profitFloorRetentionPct)||.82,.55,.95),peakRetentionPct=clamp(num(cfg?.scalp?.profitPeakRetentionPct)||.58,.35,.80),retainedNetUsd=Math.max(profitFloorUsd*retentionPct,num(state.profitFloorPeakNetUsd)*peakRetentionPct),retainedDistance=positionQty>0?(retainedNetUsd+liveCostReserve)/positionQty:0,",1),
("softConfirm=Math.max(2,Math.ceil((num(cfg?.positionControl?.softConfirmEvents)||4)*reverseExitEvidenceMult)),hardConfirm=Math.max(2,Math.ceil((num(cfg?.positionControl?.hardConfirmEvents)||2)*reverseExitEvidenceMult)),minEvidence=Math.max(2,Math.ceil((num(cfg?.positionControl?.minExitEvidence)||3)*reverseExitEvidenceMult))",
"softConfirm=Math.max(2,Math.round((num(cfg?.positionControl?.softConfirmEvents)||4)*reverseExitEvidenceMult)),hardConfirm=Math.max(2,Math.round((num(cfg?.positionControl?.hardConfirmEvents)||2)*reverseExitEvidenceMult)),minEvidence=Math.max(2,Math.round((num(cfg?.positionControl?.minExitEvidence)||3)*reverseExitEvidenceMult))",1),
("const harvestMinEvidence=Math.max(3,Math.ceil((num(cfg?.positionControl?.profitHarvestMinEvidence)||3)*reverseExitEvidenceMult)),harvestConfirm=Math.max(2,Math.ceil((num(cfg?.positionControl?.profitHarvestConfirmEvents)||3)*reverseExitEvidenceMult))",
"const harvestMinEvidence=Math.max(3,Math.round((num(cfg?.positionControl?.profitHarvestMinEvidence)||3)*reverseExitEvidenceMult)),harvestConfirm=Math.max(2,Math.round((num(cfg?.positionControl?.profitHarvestConfirmEvents)||3)*reverseExitEvidenceMult))",1),
("state.holdLogicVersion='MULTI_STAGE_PROFIT_RETENTION_HOLD_V3';","state.holdLogicVersion='MULTI_STAGE_PROFIT_RETENTION_HOLD_V4_OBJECTIVE';",1),
("profitFloorRetentionPct:retentionPct,perSymbolMinNetProfitMult:","profitFloorRetentionPct:retentionPct,profitPeakRetentionPct:peakRetentionPct,retainedNetUsd,perSymbolMinNetProfitMult:",1),
("BYBIT-MULTI-ASSET-ENGINE-4.2-PROFIT-RETENTION","BYBIT-MULTI-ASSET-ENGINE-4.3-OBJECTIVE-PROFIT-EFFICIENCY",3)
])

# Profit-floor-aware leverage search: leverage may rise to 20x to remove margin bottlenecks,
# but size/risk still remains inside the existing hard risk caps.
engine_text=engine.read_text(encoding='utf-8')
old="""  const leverage=leverageFor(cfg,setup,preRisk.capital?.capitalBaseUsd||equity,preRisk.multiplier,pos,market),sized=sizeBtcSetup({setup,riskUsd:preRisk.candidateRiskUsd,maxRiskUsd:preRisk.maxCandidateRiskUsd,filters,leverage,equityUsd:equity,capitalBaseUsd:preRisk.capital?.capitalBaseUsd,marginCapPct:preRisk.scale?.marginCapPct});if(!sized.ok){state.lastRiskReject={at:iso(),reason:sized.reason,entryTier:setup.entryTier};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:sized.reason,risk:preRisk,size:sized,market,scan,lifecycles:managed.events,state,plan:clusterPlan(state,pos,setup)};}
  const capitalUsd=num(preRisk.capital?.capitalBaseUsd)||equity,minPlannedNetProfitUsd=plannedProfitFloor(cfg,capitalUsd,setup),floorPlan=expandSetupToProfitFloor(setup,sized,minPlannedNetProfitUsd,cfg);if(!floorPlan.ok){state.lastRiskReject={at:iso(),reason:'PLANNED_NET_PROFIT_FLOOR_NOT_FEASIBLE_WITHIN_RUNNER',plannedNetProfitUsd:0,minPlannedNetProfitUsd,requiredNetProfitUsd:floorPlan.requiredNetUsd||null,requiredR:floorPlan.requiredR||null,maxRunnerR:floorPlan.maxRunnerR||null,entryTier:setup.entryTier};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:'PLANNED_NET_PROFIT_FLOOR_NOT_FEASIBLE_WITHIN_RUNNER',plannedProfit:{netUsd:0,minNetUsd:minPlannedNetProfitUsd,requiredNetUsd:floorPlan.requiredNetUsd||null,requiredR:floorPlan.requiredR||null,maxRunnerR:floorPlan.maxRunnerR||null},risk:preRisk,size:sized,market,scan,lifecycles:managed.events,state,plan:clusterPlan(state,pos,setup)};}setup=floorPlan.setup;"""
new="""  const baseLeverage=leverageFor(cfg,setup,preRisk.capital?.capitalBaseUsd||equity,preRisk.multiplier,pos,market),maxProfitLeverage=Math.max(baseLeverage,Math.min(num(cfg?.leverage?.max)||20,num(cfg?.leverage?.profitFloorMax)||num(cfg?.leverage?.max)||20)),leverageCandidates=[baseLeverage,Math.min(maxProfitLeverage,Math.ceil(baseLeverage*1.25)),Math.min(maxProfitLeverage,baseLeverage+4),maxProfitLeverage].map(x=>Math.max(1,Math.round(x))).filter((x,i,a)=>a.indexOf(x)===i),capitalUsd=num(preRisk.capital?.capitalBaseUsd)||equity,minPlannedNetProfitUsd=plannedProfitFloor(cfg,capitalUsd,setup);let leverage=baseLeverage,sized=null,floorPlan=null;const leverageAttempts=[];for(const lev of leverageCandidates){const sz=sizeBtcSetup({setup,riskUsd:preRisk.candidateRiskUsd,maxRiskUsd:preRisk.maxCandidateRiskUsd,filters,leverage:lev,equityUsd:equity,capitalBaseUsd:preRisk.capital?.capitalBaseUsd,marginCapPct:preRisk.scale?.marginCapPct});if(!sz.ok){leverageAttempts.push({leverage:lev,ok:false,reason:sz.reason});continue;}const fp=expandSetupToProfitFloor(setup,sz,minPlannedNetProfitUsd,cfg);leverageAttempts.push({leverage:lev,ok:!!fp.ok,qty:sz.qty,actualRiskUsd:sz.actualRiskUsd,initialMarginUsd:sz.initialMarginUsd,requiredR:fp.requiredR||null,maxRunnerR:fp.maxRunnerR||null});if(!sized){sized=sz;floorPlan=fp;leverage=lev;}if(fp.ok){sized=sz;floorPlan=fp;leverage=lev;break;}}if(!sized){const last=leverageAttempts.at(-1)||{};state.lastRiskReject={at:iso(),reason:last.reason||'SIZING_FAILED_ALL_LEVERAGE_LEVELS',entryTier:setup.entryTier,leverageAttempts};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:last.reason||'SIZING_FAILED_ALL_LEVERAGE_LEVELS',risk:preRisk,market,scan,lifecycles:managed.events,state,plan:clusterPlan(state,pos,setup),leverageAttempts};}if(!floorPlan?.ok){state.lastRiskReject={at:iso(),reason:'PLANNED_NET_PROFIT_FLOOR_NOT_FEASIBLE_WITHIN_RUNNER',plannedNetProfitUsd:0,minPlannedNetProfitUsd,requiredNetProfitUsd:floorPlan?.requiredNetUsd||null,requiredR:floorPlan?.requiredR||null,maxRunnerR:floorPlan?.maxRunnerR||null,entryTier:setup.entryTier,leverageAttempts};await put(env,state);return {version:state.version,mode,equity,executed:false,reason:'PLANNED_NET_PROFIT_FLOOR_NOT_FEASIBLE_WITHIN_RUNNER',plannedProfit:{netUsd:0,minNetUsd:minPlannedNetProfitUsd,requiredNetUsd:floorPlan?.requiredNetUsd||null,requiredR:floorPlan?.requiredR||null,maxRunnerR:floorPlan?.maxRunnerR||null},risk:preRisk,size:sized,market,scan,lifecycles:managed.events,state,plan:clusterPlan(state,pos,setup),leverageAttempts};}setup=floorPlan.setup;"""
if engine_text.count(old)!=1:
    raise SystemExit(f'{engine}: sizing block expected 1 match, got {engine_text.count(old)}')
engine_text=engine_text.replace(old,new,1)
engine.write_text(engine_text,encoding='utf-8')

# 6) Runtime contract and validator.
runtime=CF/'bybit-runtime-contract.js'
patch(runtime,[
("BYBIT_MULTI_ASSET_RUNTIME_V15_PROFIT_RETENTION_RUNNER","BYBIT_MULTI_ASSET_RUNTIME_V16_OBJECTIVE_PROFIT_EFFICIENCY",1),
("BYBIT-MULTI-STATEFLOW-4.2","BYBIT-MULTI-STATEFLOW-4.3",1),
("scalpAuthority:'SCALE_LADDER_NET_PROFIT_RETENTION_THESIS_AWARE_RUNNER'","scalpAuthority:'OBJECTIVE_SCALE_FLOOR_ADAPTIVE_LEVERAGE_THESIS_AWARE_RUNNER'",1),
("perSymbolProfitFloorMultiplier:true,profitFloorRetentionAfterHit:true,shortMomentumAloneCanExit:false","perSymbolProfitFloorMultiplier:true,profitFloorRetentionAfterHit:true,profitFloorAdaptiveLeverage:true,profileNormalizedQuality:true,peakNetProfitRetention:true,shortMomentumAloneCanExit:false",1)
])

validator=CF/'validate-btc-hyperscale.mjs'
patch(validator,[
("assert.ok(cfg.scalp.minPlannedNetProfitUsd>=1);assert.ok(ladder[0].minNetUsd>=1);","assert.ok(cfg.scalp.minPlannedNetProfitUsd>1);assert.ok(ladder[0].minNetUsd>1);",1),
("assert.equal(cfg.scalp.profitFloorProtectAfterHit,true);assert.ok(cfg.scalp.profitFloorRetentionPct>=.75);","assert.equal(cfg.scalp.profitFloorProtectAfterHit,true);assert.ok(cfg.scalp.profitFloorRetentionPct>=.75);assert.ok(cfg.scalp.profitPeakRetentionPct>=.5);assert.equal(cfg.leverage.profitFloorAdaptive,true);assert.ok(cfg.leverage.profitFloorMax<=cfg.leverage.max);",1),
("'PROFIT_FLOOR_RETENTION_LOCK','expandSetupToProfitFloor','PROFIT_HARVEST_EDGE_EXHAUSTED','MULTI_STAGE_PROFIT_RETENTION_HOLD_V3','BYBIT-MULTI-ASSET-ENGINE-4.2-PROFIT-RETENTION'","'PROFIT_FLOOR_RETENTION_LOCK','expandSetupToProfitFloor','leverageCandidates','PROFIT_HARVEST_EDGE_EXHAUSTED','MULTI_STAGE_PROFIT_RETENTION_HOLD_V4_OBJECTIVE','BYBIT-MULTI-ASSET-ENGINE-4.3-OBJECTIVE-PROFIT-EFFICIENCY'",1),
("'BYBIT_MULTI_ASSET_RUNTIME_V15_PROFIT_RETENTION_RUNNER','multiAsset:true','PER_SYMBOL_COGNITION_STATE_FIRST','profitFloorRetentionAfterHit:true','shortMomentumAloneCanExit:false'","'BYBIT_MULTI_ASSET_RUNTIME_V16_OBJECTIVE_PROFIT_EFFICIENCY','multiAsset:true','PER_SYMBOL_COGNITION_STATE_FIRST','profitFloorRetentionAfterHit:true','profitFloorAdaptiveLeverage:true','profileNormalizedQuality:true','peakNetProfitRetention:true','shortMomentumAloneCanExit:false'",1),
("version:'BYBIT-MULTI-STATEFLOW-4.2'","version:'BYBIT-MULTI-STATEFLOW-4.3'",1),
("profitHarvest:true,profitFloorRetention:true,perSymbolProfitFloor:true,shortMomentumAloneExit:false","profitHarvest:true,profitFloorRetention:true,perSymbolProfitFloor:true,adaptiveLeverage:true,normalizedQuality:true,peakNetRetention:true,shortMomentumAloneExit:false",1)
])

print('BYBIT_V43_OBJECTIVE_PATCH_APPLIED=1')
