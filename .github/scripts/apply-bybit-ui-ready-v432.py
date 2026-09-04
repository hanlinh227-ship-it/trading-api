from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
CF=ROOT/'cloudflare-worker'


def replace_once(path,old,new):
    text=path.read_text(encoding='utf-8')
    got=text.count(old)
    if got!=1:
        raise SystemExit(f'{path}: expected 1 match, got {got}: {old[:180]}')
    path.write_text(text.replace(old,new,1),encoding='utf-8')


def replace_count(path,old,new,count):
    text=path.read_text(encoding='utf-8')
    got=text.count(old)
    if got!=count:
        raise SystemExit(f'{path}: expected {count} matches, got {got}: {old[:180]}')
    path.write_text(text.replace(old,new),encoding='utf-8')

# 1) Portfolio policy: protected winners can release a fractional risk slot,
# while a hard physical-position buffer prevents unbounded position count.
profiles=CF/'bybit-coin-profiles.js'
replace_once(profiles,
    "authority:'MAJOR_CAP_LIQUIDITY_PROFILE_PORTFOLIO_V3_OBJECTIVE_COVERAGE',",
    "authority:'MAJOR_CAP_LIQUIDITY_PROFILE_PORTFOLIO_V4_PROTECTED_RISK_SLOT_REUSE',")
replace_once(profiles,
    "  deepScanCount:6,\n  maxCorrelatedSmall:1,",
    "  deepScanCount:6,\n  protectedRiskSlotReuse:true,\n  protectedSlotWeight:.20,\n  protectedActiveRiskEquityPct:.05,\n  physicalPositionBuffer:1,\n  forcedOpportunityReplacement:false,\n  maxCorrelatedSmall:1,")

# 2) Profit objective: once the planned minimum has actually been reached,
# aim to lock the full floor (subject to exchange tick/gap/slippage constraints).
config=CF/'bybit-auto-config.js'
replace_once(config,
    "// BYBIT-MULTI-STATEFLOW-4.3.1 FRESHNESS + OBJECTIVE-ENTRY configuration.",
    "// BYBIT-MULTI-STATEFLOW-4.3.2 PROTECTED-RISK-SLOT + UI-READY configuration.")
replace_once(config,
    "authority:'OBJECTIVE_PROFIT_FLOOR_EDGE_PERSISTENCE',",
    "authority:'OBJECTIVE_PROFIT_FLOOR_EDGE_PERSISTENCE_FLOOR_LOCK',")
replace_once(config,
    "    profitFloorProtectAfterHit:true,\n    profitFloorRetentionPct:.82,\n    profitPeakRetentionPct:.58,",
    "    profitFloorProtectAfterHit:true,\n    profitFloorLockAtHit:true,\n    profitFloorRetentionPct:1.00,\n    profitPeakRetentionPct:.68,")
replace_once(config,
    "profileNormalizedQuality:true,peakNetProfitRetention:true",
    "profileNormalizedQuality:true,peakNetProfitRetention:true,protectedRiskSlotReuse:true,uiReadOnlyContract:true")

# 3) Engine: accept a 100% floor retention target after profit-floor hit.
engine=CF/'bybit-symbol-engine.js'
replace_count(engine,
    'BYBIT-MULTI-ASSET-ENGINE-4.3.1-FRESHNESS-FAIR-ENTRY',
    'BYBIT-MULTI-ASSET-ENGINE-4.3.2-FLOOR-RISK-SLOT-UI',3)
replace_once(engine,
    "retentionPct=clamp(num(cfg?.scalp?.profitFloorRetentionPct)||.82,.55,.95),peakRetentionPct=clamp(num(cfg?.scalp?.profitPeakRetentionPct)||.58,.35,.80)",
    "retentionPct=clamp(num(cfg?.scalp?.profitFloorRetentionPct)||1,.70,1.05),peakRetentionPct=clamp(num(cfg?.scalp?.profitPeakRetentionPct)||.68,.35,.90)")
replace_once(engine,
    "state.holdLogicVersion='MULTI_STAGE_PROFIT_RETENTION_HOLD_V4_OBJECTIVE';",
    "state.holdLogicVersion='MULTI_STAGE_PROFIT_RETENTION_HOLD_V5_FLOOR_FIRST';")

# 4) Controller: slot usage is based on active risk, not only raw position count.
controller=CF/'bybit-multi-asset-controller.js'
replace_once(controller,
    "function groupCount(positions,group){return positions.filter(x=>coinProfileForSymbol(sym(x))?.correlationGroup===group).length;}\nfunction rotatingDeepSymbols",
    "function groupCount(positions,group){return positions.filter(x=>coinProfileForSymbol(sym(x))?.correlationGroup===group).length;}\nfunction protectedStop(x={}){const e=num(x.avgPrice),sl=num(x.stopLoss),side=String(x.side||'');return e>0&&sl>0&&((side==='Buy'&&sl>=e)||(side==='Sell'&&sl<=e));}\nfunction slotWeight(x={},equity=0){if(!BYBIT_PORTFOLIO_POLICY.protectedRiskSlotReuse)return 1;const risk=positionRisk(x),tiny=Math.max(.01,Math.max(0,num(equity))*Math.max(0,num(BYBIT_PORTFOLIO_POLICY.protectedActiveRiskEquityPct)||0)/100),protectedNow=protectedStop(x)&&risk<=tiny+1e-9;return protectedNow?clamp(num(BYBIT_PORTFOLIO_POLICY.protectedSlotWeight)||.20,.05,.50):1;}\nfunction slotUsage(positions=[],equity=0){return positions.reduce((s,x)=>s+slotWeight(x,equity),0);}\nfunction groupSlotUsage(positions=[],group,equity=0){return positions.filter(x=>coinProfileForSymbol(sym(x))?.correlationGroup===group).reduce((s,x)=>s+slotWeight(x,equity),0);}\nfunction rotatingDeepSymbols")
replace_once(controller,
    "function entryBlockFor({symbol,positions,equity,newEntryDone,ranked}){const p=coinProfileForSymbol(symbol),existing=positions.find(x=>sym(x)===symbol);if(!p)return 'SYMBOL_NOT_IN_MAJOR_CAP_UNIVERSE';if(existing)return newEntryDone?'EVENT_NEW_RISK_ALREADY_USED':null;const row=ranked.find(x=>x.symbol===symbol);if(row&&!row.eligible)return 'UNIVERSE_LIQUIDITY_OR_SPREAD_GATE';if(newEntryDone)return 'EVENT_NEW_RISK_ALREADY_USED';if(positions.length>=maxConcurrentForEquity(equity))return 'PORTFOLIO_CONCURRENT_POSITION_CAP';if(groupCount(positions,p.correlationGroup)>=correlationCapForEquity(equity))return 'PORTFOLIO_CORRELATION_CAP';return null;}",
    "function entryBlockFor({symbol,positions,equity,newEntryDone,ranked}){const p=coinProfileForSymbol(symbol),existing=positions.find(x=>sym(x)===symbol);if(!p)return 'SYMBOL_NOT_IN_MAJOR_CAP_UNIVERSE';if(existing)return newEntryDone?'EVENT_NEW_RISK_ALREADY_USED':null;const row=ranked.find(x=>x.symbol===symbol);if(row&&!row.eligible)return 'UNIVERSE_LIQUIDITY_OR_SPREAD_GATE';if(newEntryDone)return 'EVENT_NEW_RISK_ALREADY_USED';const baseMax=maxConcurrentForEquity(equity),hardMax=baseMax+Math.max(0,Math.floor(num(BYBIT_PORTFOLIO_POLICY.physicalPositionBuffer)||0));if(positions.length>=hardMax)return 'PORTFOLIO_PHYSICAL_POSITION_HARD_CAP';if(slotUsage(positions,equity)>=baseMax-1e-9)return 'PORTFOLIO_RISK_SLOT_CAP';if(groupSlotUsage(positions,p.correlationGroup,equity)>=correlationCapForEquity(equity)-1e-9)return 'PORTFOLIO_CORRELATION_RISK_SLOT_CAP';return null;}")
replace_once(controller,
    "targets=[...new Set([...openSymbols,eventSymbol,...rotation.symbols])],results=[],scanRows=[];let newEntryDone=false;",
    "targets=[...new Set([...openSymbols,eventSymbol,...rotation.symbols])],results=[],scanRows=[],candidateDecisions=[];let newEntryDone=false;")
replace_once(controller,
    "positions=openPos(await api.positions());const queue=scanRows.sort((a,b)=>b.rankScore-a.rankScore||b.priority-a.priority);for(const candidate of queue){if(newEntryDone)break;const symbol=candidate.symbol,block=entryBlockFor({symbol,positions,equity,newEntryDone:false,ranked});if(block)continue;const ctx=portfolioContext(positions,symbol,balance),r=await runBybitSymbolEngine(env,{symbol,entryBlockReason:null,portfolioContext:ctx});results.push(r);await sendEntry(env,r);await sendLifecycle(env,r);if(r?.executed){newEntryDone=true;positions=openPos(await api.positions());break;}if(r?.reason==='SMART_CUT'||(r?.lifecycles||[]).some(x=>x?.cutExecuted))positions=openPos(await api.positions());}",
    "positions=openPos(await api.positions());const queue=scanRows.sort((a,b)=>b.rankScore-a.rankScore||b.priority-a.priority);for(const candidate of queue){if(newEntryDone)break;const symbol=candidate.symbol,block=entryBlockFor({symbol,positions,equity,newEntryDone:false,ranked});const decision={...candidate,finalBlock:block||null,action:block?'BLOCKED':'FRESH_RECHECK'};candidateDecisions.push(decision);if(block)continue;const ctx=portfolioContext(positions,symbol,balance),r=await runBybitSymbolEngine(env,{symbol,entryBlockReason:null,portfolioContext:ctx});results.push(r);await sendEntry(env,r);await sendLifecycle(env,r);decision.action=r?.executed?'EXECUTED':'RECHECK_REJECTED';decision.finalReason=r?.reason||null;if(r?.executed){newEntryDone=true;positions=openPos(await api.positions());break;}if(r?.reason==='SMART_CUT'||(r?.lifecycles||[]).some(x=>x?.cutExecuted))positions=openPos(await api.positions());}")
replace_once(controller,
    "activeRiskUsd:positionRisk(x)})),best=ranked.find(x=>x.eligible)||null,last=results.at(-1)||{},ctl=",
    "activeRiskUsd:positionRisk(x),protectedForRiskSlot:protectedStop(x)&&slotWeight(x,equity)<1,riskSlotWeight:slotWeight(x,equity)})),best=ranked.find(x=>x.eligible)||null,last=results.at(-1)||{},baseMax=maxConcurrentForEquity(equity),physicalHardCap=baseMax+Math.max(0,Math.floor(num(BYBIT_PORTFOLIO_POLICY.physicalPositionBuffer)||0)),riskSlotsUsed=slotUsage(positions,equity),protectedPositionCount=positions.filter(x=>slotWeight(x,equity)<1).length,ctl=")
replace_once(controller,
    "activePositionCount:active.length,maxConcurrent:maxConcurrentForEquity(equity),rankedUniverse:",
    "activePositionCount:active.length,maxConcurrent:baseMax,physicalPositionHardCap:physicalHardCap,riskSlotsUsed:Number(riskSlotsUsed.toFixed(3)),riskSlotsAvailable:Number(Math.max(0,baseMax-riskSlotsUsed).toFixed(3)),protectedPositionCount,protectedRiskSlotReuse:!!BYBIT_PORTFOLIO_POLICY.protectedRiskSlotReuse,forcedOpportunityReplacement:false,rankedUniverse:")
replace_once(controller,
    "objectiveCandidateRanking:queue.slice(0,8),bestUniverseSymbol:",
    "objectiveCandidateRanking:queue.slice(0,8),candidateDecisions:candidateDecisions.slice(0,8),replacementPolicy:'NO_FORCED_REPLACEMENT_PROTECTED_SLOT_REUSE_ONLY',bestUniverseSymbol:")
replace_once(controller,
    "export const BYBIT_MULTI_ASSET_CONTROLLER_VERSION='BYBIT_MULTI_ASSET_CONTROLLER_V2_OBJECTIVE_RANKED_ROTATING';",
    "export const BYBIT_MULTI_ASSET_CONTROLLER_VERSION='BYBIT_MULTI_ASSET_CONTROLLER_V3_PROTECTED_RISK_SLOT_UI_READY';")

# 5) Stable UI contract and read-only endpoints.
ui_contract=CF/'bybit-ui-contract.js'
ui_contract.write_text("""export const BYBIT_UI_SCHEMA_VERSION='BYBIT_UI_SCHEMA_V1';
export const BYBIT_UI_ROUTES=Object.freeze({
  bootstrap:'/bybit/ui/bootstrap',
  snapshot:'/bybit/ui/snapshot',
  health:'/bybit/health',
  entryHealth:'/bybit/entry-health',
  runtimeContract:'/runtime/contract'
});
export const BYBIT_UI_CAPABILITIES=Object.freeze({
  readOnlyBootstrap:true,
  authenticatedReadOnlySnapshot:true,
  liveAccountSummary:true,
  activePositions:true,
  protectedRiskSlots:true,
  candidateRanking:true,
  candidateDecisions:true,
  profitObjective:true,
  leveragePolicy:true,
  riskPolicy:true,
  executionWriteControlsExposedToUi:false,
  realizedProfitGuaranteed:false
});
""",encoding='utf-8')

control=CF/'bybit-control-plane.js'
replace_once(control,
    "import {bybitCredentials,bybitExecutionMode} from './bybit-auto-config.js';",
    "import {bybitCredentials,bybitExecutionMode,bybitAutoConfig} from './bybit-auto-config.js';")
replace_once(control,
    "import {BYBIT_AUTO_VERSION} from './bybit-runtime-contract.js';",
    "import {BYBIT_AUTO_VERSION,BYBIT_RUNTIME_CONTRACT} from './bybit-runtime-contract.js';")
replace_once(control,
    "import {BYBIT_TRADE_UNIVERSE,isSupportedTradeSymbol,normalizeBybitSymbol} from './bybit-coin-profiles.js';",
    "import {BYBIT_TRADE_UNIVERSE,BYBIT_PORTFOLIO_POLICY,isSupportedTradeSymbol,normalizeBybitSymbol} from './bybit-coin-profiles.js';\nimport {BYBIT_UI_SCHEMA_VERSION,BYBIT_UI_ROUTES,BYBIT_UI_CAPABILITIES} from './bybit-ui-contract.js';")
ui_helpers="""
function uiStaticPolicy(env){const cfg=bybitAutoConfig(env);return {profitObjective:{authority:cfg.scalp.authority,plannedNetProfitFloor:true,minPlannedNetProfitUsd:cfg.scalp.minPlannedNetProfitUsd,minPlannedNetProfitPct:cfg.scalp.minPlannedNetProfitPct,profitFloorLadder:cfg.scalp.profitFloorLadder,profitFloorBufferMult:cfg.scalp.profitFloorBufferMult,profitFloorRetentionPct:cfg.scalp.profitFloorRetentionPct,profitPeakRetentionPct:cfg.scalp.profitPeakRetentionPct,afterFeesRequired:cfg.scalp.requireNetFloorAfterFees===true,realizedProfitGuaranteed:false,note:'PLANNED_NET_PROFIT_FLOOR_IS_AN_ENTRY_AND_PROTECTION_OBJECTIVE_NOT_A GUARANTEE_OF_REALIZED_PROFIT'},leverage:{min:cfg.leverage.min,max:cfg.leverage.max,profitFloorAdaptive:cfg.leverage.profitFloorAdaptive===true,profitFloorMax:cfg.leverage.profitFloorMax,equityAdaptive:cfg.leverage.equityAdaptive},risk:{baseEntryRiskPct:cfg.risk.baseEntryRiskPct,strongEntryRiskPct:cfg.risk.strongEntryRiskPct,aPlusEntryRiskPct:cfg.risk.aPlusEntryRiskPct,absoluteSingleEntryRiskPct:cfg.risk.absoluteSingleEntryRiskPct,maxActiveRiskPct:cfg.risk.maxActiveRiskPct,maxPortfolioMarginPct:cfg.risk.maxPortfolioMarginPct,minFreeReservePct:cfg.risk.minFreeReservePct,martingale:false,addToLoser:false},portfolio:{authority:BYBIT_PORTFOLIO_POLICY.authority,concurrentByEquity:BYBIT_PORTFOLIO_POLICY.concurrentByEquity,protectedRiskSlotReuse:BYBIT_PORTFOLIO_POLICY.protectedRiskSlotReuse,protectedSlotWeight:BYBIT_PORTFOLIO_POLICY.protectedSlotWeight,physicalPositionBuffer:BYBIT_PORTFOLIO_POLICY.physicalPositionBuffer,forcedOpportunityReplacement:false}};}
function uiBootstrap(env){return {ok:true,readOnly:true,schemaVersion:BYBIT_UI_SCHEMA_VERSION,version:BYBIT_AUTO_VERSION,runtimeContract:BYBIT_RUNTIME_CONTRACT.version,routes:BYBIT_UI_ROUTES,capabilities:BYBIT_UI_CAPABILITIES,universe:BYBIT_TRADE_UNIVERSE,...uiStaticPolicy(env),checkedAt:new Date().toISOString()};}
async function uiSnapshot(env){const [preflight,controller]=await Promise.all([runtimePreflight(env),getMultiAssetControllerState(env)]);return {ok:true,readOnly:true,schemaVersion:BYBIT_UI_SCHEMA_VERSION,version:BYBIT_AUTO_VERSION,runtimeContract:BYBIT_RUNTIME_CONTRACT.version,runtimeRevision:String(env.RUNTIME_REVISION||'UNKNOWN'),mode:preflight.mode,ready:preflight.ok,blockers:preflight.blockers||[],account:preflight.account||null,portfolio:{positions:Array.isArray(controller?.activePositions)?controller.activePositions:preflight.positions||[],openOrders:preflight.openOrders||0,activePositionCount:Number(controller?.activePositionCount||0),maxConcurrent:Number(controller?.maxConcurrent||0),physicalPositionHardCap:Number(controller?.physicalPositionHardCap||0),riskSlotsUsed:Number(controller?.riskSlotsUsed||0),riskSlotsAvailable:Number(controller?.riskSlotsAvailable||0),protectedPositionCount:Number(controller?.protectedPositionCount||0),replacementPolicy:controller?.replacementPolicy||'NO_FORCED_REPLACEMENT_PROTECTED_SLOT_REUSE_ONLY'},candidates:{ranking:controller?.objectiveCandidateRanking||[],decisions:controller?.candidateDecisions||[],bestUniverseSymbol:controller?.bestUniverseSymbol||null,lastEventSymbol:controller?.lastEventSymbol||null},controller:{lastCycleAt:controller?.lastCycleAt||null,lastCycleReason:controller?.lastCycleReason||null,lastCycleExecuted:!!controller?.lastCycleExecuted,entrySelectionAuthority:controller?.entrySelectionAuthority||null,deepScanAuthority:controller?.deepScanAuthority||null},...uiStaticPolicy(env),checkedAt:new Date().toISOString()};}
"""
replace_once(control,
    "export async function handleBybitControlApi(req,env){const u=new URL(req.url);",
    ui_helpers+"\nexport async function handleBybitControlApi(req,env){const u=new URL(req.url);if(u.pathname===BYBIT_UI_ROUTES.bootstrap&&req.method==='GET')return json(uiBootstrap(env));if(u.pathname===BYBIT_UI_ROUTES.snapshot&&req.method==='GET'){if(!authState(req,env).ok)return unauthorized(req,env);try{return json(await uiSnapshot(env))}catch(e){return json({ok:false,readOnly:true,schemaVersion:BYBIT_UI_SCHEMA_VERSION,reason:'BYBIT_UI_SNAPSHOT_FAILED',error:String(e?.message||e)},502)}}")

# 6) Runtime contract advertises the new stable UI/read-only schema and safety semantics.
runtime=CF/'bybit-runtime-contract.js'
replace_once(runtime,
    "export const BYBIT_RUNTIME_CONTRACT_VERSION='BYBIT_MULTI_ASSET_RUNTIME_V17_FRESHNESS_FAIR_ENTRY';",
    "export const BYBIT_RUNTIME_CONTRACT_VERSION='BYBIT_MULTI_ASSET_RUNTIME_V18_PROTECTED_RISK_SLOT_UI_READY';")
replace_once(runtime,
    "export const BYBIT_AUTO_VERSION='BYBIT-MULTI-STATEFLOW-4.3.1';",
    "export const BYBIT_AUTO_VERSION='BYBIT-MULTI-STATEFLOW-4.3.2';")
replace_once(runtime,
    "protectedStopZeroActiveRisk:true,shortMomentumAloneCanExit:false,",
    "protectedStopZeroActiveRisk:true,protectedRiskSlotReuse:true,physicalPositionHardBuffer:true,forcedOpportunityReplacement:false,profitFloorLockObjective:true,uiContractReady:true,uiBootstrapPublicReadOnly:true,uiSnapshotAuthenticatedReadOnly:true,realizedProfitGuarantee:false,shortMomentumAloneCanExit:false,")

# 7) Status endpoint exposes UI discovery without exposing live account state.
index=CF/'index.js'
replace_once(index,
    "import {BYBIT_TRADE_UNIVERSE} from './bybit-coin-profiles.js';",
    "import {BYBIT_TRADE_UNIVERSE} from './bybit-coin-profiles.js';\nimport {BYBIT_UI_SCHEMA_VERSION,BYBIT_UI_ROUTES} from './bybit-ui-contract.js';")
replace_once(index,
    "scheduledExecution:false,timeGate:false,hardDailyTradeQuota:false,martingale:false,addToLoser:false,winnerPyramiding:true}});",
    "scheduledExecution:false,timeGate:false,hardDailyTradeQuota:false,martingale:false,addToLoser:false,winnerPyramiding:true,ui:{schemaVersion:BYBIT_UI_SCHEMA_VERSION,routes:BYBIT_UI_ROUTES,snapshotAuth:'ACTION_OR_VPS_BRIDGE_KEY'}}});")

# 8) Validator upgrades.
validator=CF/'validate-btc-hyperscale.mjs'
replace_once(validator,
    "assert.equal(BYBIT_PORTFOLIO_POLICY.noDailyQuota,true);",
    "assert.equal(BYBIT_PORTFOLIO_POLICY.noDailyQuota,true);assert.equal(BYBIT_PORTFOLIO_POLICY.protectedRiskSlotReuse,true);assert.ok(BYBIT_PORTFOLIO_POLICY.protectedSlotWeight>0&&BYBIT_PORTFOLIO_POLICY.protectedSlotWeight<1);assert.ok(BYBIT_PORTFOLIO_POLICY.physicalPositionBuffer>=1);assert.equal(BYBIT_PORTFOLIO_POLICY.forcedOpportunityReplacement,false);")
replace_once(validator,
    "assert.ok(cfg.scalp.profitFloorRetentionPct>=.75);assert.ok(cfg.scalp.profitPeakRetentionPct>=.5);",
    "assert.ok(cfg.scalp.profitFloorRetentionPct>=1);assert.ok(cfg.scalp.profitPeakRetentionPct>=.6);assert.equal(cfg.scalp.profitFloorLockAtHit,true);")
replace_once(validator,
    "const engine=read('bybit-symbol-engine.js'),controller=read('bybit-multi-asset-controller.js'),control=read('bybit-control-plane.js'),runtime=read('bybit-runtime-contract.js'),bridge=read('../bybit-live-bridge/bybit_live_bridge.py'),strategy=read('bybit-symbol-strategy.js'),index=read('index.js');",
    "const engine=read('bybit-symbol-engine.js'),controller=read('bybit-multi-asset-controller.js'),control=read('bybit-control-plane.js'),runtime=read('bybit-runtime-contract.js'),ui=read('bybit-ui-contract.js'),bridge=read('../bybit-live-bridge/bybit_live_bridge.py'),strategy=read('bybit-symbol-strategy.js'),index=read('index.js');")
replace_once(validator,
    "'MULTI_STAGE_PROFIT_RETENTION_HOLD_V4_OBJECTIVE','NATIVE_PROTECTION_STALE_DATA_HOLD_V1','BYBIT-MULTI-ASSET-ENGINE-4.3.1-FRESHNESS-FAIR-ENTRY'",
    "'MULTI_STAGE_PROFIT_RETENTION_HOLD_V5_FLOOR_FIRST','NATIVE_PROTECTION_STALE_DATA_HOLD_V1','BYBIT-MULTI-ASSET-ENGINE-4.3.2-FLOOR-RISK-SLOT-UI'")
replace_once(validator,
    "for(const x of ['rankUniverse','PORTFOLIO_CORRELATION_CAP','maxNewEntriesPerEvent:1','PER_SYMBOL_COGNITION_V1','OBJECTIVE_SCAN_THEN_RANK_FRESH_RECHECK','TOP_LIQUIDITY_PLUS_ROTATING_COVERAGE','BYBIT_MULTI_ASSET_CONTROLLER_V2_OBJECTIVE_RANKED_ROTATING'])",
    "for(const x of ['rankUniverse','PORTFOLIO_RISK_SLOT_CAP','PORTFOLIO_CORRELATION_RISK_SLOT_CAP','protectedForRiskSlot','riskSlotsAvailable','candidateDecisions','maxNewEntriesPerEvent:1','PER_SYMBOL_COGNITION_V1','OBJECTIVE_SCAN_THEN_RANK_FRESH_RECHECK','TOP_LIQUIDITY_PLUS_ROTATING_COVERAGE','BYBIT_MULTI_ASSET_CONTROLLER_V3_PROTECTED_RISK_SLOT_UI_READY'])")
replace_once(validator,
    "for(const x of ['BYBIT_TRADE_UNIVERSE','x-bybit-symbol','BYBIT_MULTI_ENTRY_INFRA_READY'])",
    "for(const x of ['BYBIT_TRADE_UNIVERSE','x-bybit-symbol','BYBIT_MULTI_ENTRY_INFRA_READY','BYBIT_UI_ROUTES.bootstrap','BYBIT_UI_ROUTES.snapshot','uiSnapshot'])")
replace_once(validator,
    "for(const x of ['BYBIT_MULTI_ASSET_RUNTIME_V17_FRESHNESS_FAIR_ENTRY','BYBIT-MULTI-STATEFLOW-4.3.1','multiAsset:true','PER_SYMBOL_COGNITION_STATE_FIRST','profitFloorRetentionAfterHit:true','profitFloorAdaptiveLeverage:true','profileNormalizedQuality:true','peakNetProfitRetention:true','freshWsRequiredForNewRisk:true','staleDataNativeProtectionHold:true','adaptiveProfileVoteThreshold:true','executionQualityAdaptiveLiquidityGate:true','objectiveCandidateRanking:true','rotatingDeepCoverage:true','protectedStopZeroActiveRisk:true','shortMomentumAloneCanExit:false'])",
    "for(const x of ['BYBIT_MULTI_ASSET_RUNTIME_V18_PROTECTED_RISK_SLOT_UI_READY','BYBIT-MULTI-STATEFLOW-4.3.2','multiAsset:true','PER_SYMBOL_COGNITION_STATE_FIRST','profitFloorRetentionAfterHit:true','profitFloorAdaptiveLeverage:true','profileNormalizedQuality:true','peakNetProfitRetention:true','freshWsRequiredForNewRisk:true','staleDataNativeProtectionHold:true','adaptiveProfileVoteThreshold:true','executionQualityAdaptiveLiquidityGate:true','objectiveCandidateRanking:true','rotatingDeepCoverage:true','protectedStopZeroActiveRisk:true','protectedRiskSlotReuse:true','physicalPositionHardBuffer:true','forcedOpportunityReplacement:false','profitFloorLockObjective:true','uiContractReady:true','realizedProfitGuarantee:false','shortMomentumAloneCanExit:false'])")
replace_once(validator,
    "assert.ok(strategy.includes('BYBIT_SYMBOL_COGNITION_V3_FRESHNESS_ADAPTIVE_CONSENSUS'));",
    "for(const x of ['BYBIT_UI_SCHEMA_V1','authenticatedReadOnlySnapshot:true','executionWriteControlsExposedToUi:false','realizedProfitGuaranteed:false'])assert.ok(ui.includes(x),`UI ${x}`);assert.ok(strategy.includes('BYBIT_SYMBOL_COGNITION_V3_FRESHNESS_ADAPTIVE_CONSENSUS'));")
replace_once(validator,
    "assert.ok(index.includes('Bybit Major-Cap Multi-Asset StateFlow'));",
    "assert.ok(index.includes('Bybit Major-Cap Multi-Asset StateFlow'));assert.ok(index.includes('BYBIT_UI_SCHEMA_VERSION'));assert.ok(index.includes('snapshotAuth'));")
replace_once(validator,
    "console.log('BYBIT_MULTI_ASSET_VALIDATION=PASS');console.log(JSON.stringify({version:'BYBIT-MULTI-STATEFLOW-4.3.1'",
    "console.log('BYBIT_MULTI_ASSET_VALIDATION=PASS');console.log(JSON.stringify({version:'BYBIT-MULTI-STATEFLOW-4.3.2'")
replace_once(validator,
    "protectedStopZeroActiveRisk:true,shortMomentumAloneExit:false",
    "protectedStopZeroActiveRisk:true,protectedRiskSlotReuse:true,profitFloorLockAtHit:true,uiReady:true,realizedProfitGuaranteed:false,shortMomentumAloneExit:false")

# 9) UI handoff document: stable contract for the next project.
(ROOT/'BYBIT_UI_HANDOFF_V432.md').write_text("""# Bybit Bot V4.3.2 — UX/UI Handoff

## Runtime baseline
- Auto version: `BYBIT-MULTI-STATEFLOW-4.3.2`
- Runtime contract: `BYBIT_MULTI_ASSET_RUNTIME_V18_PROTECTED_RISK_SLOT_UI_READY`
- UI schema: `BYBIT_UI_SCHEMA_V1`
- Execution remains event-driven from VPS WebSocket market-state changes.
- The UI layer is read-only. It does **not** get order/close/leverage write endpoints.

## Read-only endpoints
- `GET /bybit/ui/bootstrap` — public static UI contract, universe, policy, capability metadata.
- `GET /bybit/ui/snapshot` — authenticated live account/controller snapshot.
- `GET /bybit/health` — transport/runtime health.
- `GET /bybit/entry-health` — current entry infrastructure readiness.
- `GET /runtime/contract` — canonical runtime contract.

## Authentication
`/bybit/ui/snapshot` requires the existing action key or VPS bridge secret. Do not embed either secret directly in a browser bundle. A production UI should call the snapshot through a trusted server-side/BFF layer.

## Portfolio semantics
- Base concurrent positions still scale with equity.
- A position with a native stop at/through breakeven is treated as protected active risk and consumes only a fractional risk slot.
- A physical hard cap of `base max + 1` remains, so protected-slot reuse cannot create an unlimited number of positions.
- Correlation limits use the same protected-risk weighting.
- There is no forced opportunity replacement: the controller does not close a healthy winner merely to make room for a new candidate.

## Profit objective semantics
- New risk is rejected if the planned net profit floor after estimated costs is not feasible inside the permitted runner geometry.
- At low equity the configured planned floor begins at `$1.05` net before per-symbol multipliers and the planning buffer.
- After the live position reaches its profit floor, V4.3.2 targets a 100% floor-retention lock when exchange geometry permits, while keeping native TP/SL and runner logic.
- This is an objective/protection rule, **not a guarantee of realized profit**. Gaps, slippage, liquidation conditions, exchange failures, or market movement can still produce less profit or a loss.

## UI fields to prioritize
1. Runtime: version, mode, ready, blockers, checkedAt.
2. Account: equity, wallet balance, available balance.
3. Portfolio: positions, active risk, protected status, risk-slot weight, slots used/available, hard physical cap.
4. Profit: planned floor ladder, floor retention %, live PnL, TP/SL.
5. Candidates: ranking, final block reason, recheck result, executed state.
6. Risk: leverage policy, active-risk cap, margin cap, reserve.

## UX safety
- Clearly label LIVE vs PAPER/DEMO.
- Never imply guaranteed profit.
- Any future write controls should be a separate authenticated control plane with confirmation, audit log, and server-side authorization; do not bolt them onto the read-only snapshot contract.
""",encoding='utf-8')

print('BYBIT_V432_PATCH_APPLIED')
