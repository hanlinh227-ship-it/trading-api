from pathlib import Path
import re

ROOT=Path('cloudflare-worker')

def replace_once(path, old, new, label):
    p=ROOT/path
    s=p.read_text()
    if new in s:
        return
    if old not in s:
        raise SystemExit(f'MISSING:{label}')
    p.write_text(s.replace(old,new,1))

def regex_once(path, pattern, repl, label):
    p=ROOT/path
    s=p.read_text()
    if repl in s:
        return
    out,n=re.subn(pattern,repl,s,count=1,flags=re.S)
    if n!=1:
        raise SystemExit(f'MISSING_REGEX:{label}:{n}')
    p.write_text(out)

# Runtime/version: V5.1 becomes the entry authority while preserving V5.0 risk/profit-floor rules.
replace_once('bybit-runtime-contract.js',
"BYBIT_MULTI_ASSET_RUNTIME_V28_SCALP_QUALITY_POSITIVE_EDGE",
"BYBIT_MULTI_ASSET_RUNTIME_V29_THREE_LANE_MICROSTRUCTURE_SCALP",
'runtime contract version')
replace_once('bybit-runtime-contract.js',
"BYBIT-MULTI-STATEFLOW-5.0.0",
"BYBIT-MULTI-STATEFLOW-5.1.0",
'auto version')
replace_once('bybit-runtime-contract.js',
"strategyAuthority:'PER_SYMBOL_COGNITION_MOMENTUM_FOOTPRINT_STATE_FIRST'",
"strategyAuthority:'THREE_LANE_MICROSTRUCTURE_SCALP_TTT_MAE_POSITIVE_EDGE'",
'runtime strategy authority')
replace_once('bybit-runtime-contract.js',
"entryTierAuthority:'PROBE_CONFIRM_FULL'",
"entryTierAuthority:'CONFIRM_FULL_ONLY'",
'entry tier authority')
replace_once('bybit-runtime-contract.js',
"positiveExpectancyGovernorV2:true,adaptiveLeverageExpanded:true,",
"positiveExpectancyGovernorV2:true,scalpEntryEngineV51:true,threeLaneScalpEntry:true,liquiditySweepReclaimLane:true,breakoutRetestContinuationLane:true,trendPullbackReaccelerationLane:true,expectedTimeToTargetGate:true,expectedTimeToTargetRanking:true,maeAwareEntryRanking:true,netProfitPerMinuteRanking:true,legacyBroadSetupRouterDisabledForNewRisk:true,adaptiveLeverageExpanded:true,",
'runtime v51 entry flags')

replace_once('bybit-auto-config.js',
"strategyAuthority:'SCALP_QUALITY_SHORT_HORIZON_CONFIRMATION_POSITIVE_NET_EDGE_PER_SYMBOL'",
"strategyAuthority:'V51_THREE_LANE_MICROSTRUCTURE_TTT_MAE_POSITIVE_EDGE'",
'config strategy authority')
replace_once('bybit-auto-config.js',
"entries:{trendPullback:true,trendContinuation:true,breakoutRetest:true,rangeMeanReversion:true,liquidationExhaustion:true,absorptionReversal:true,squeezeRelease:true,momentumEarlyRelease:true,rangeMicroReclaimScalp:true,transitionWsScalp:false,shortHorizonReversal:true,sampleQualityGuard:true,probeConfirmFull:false,confirmOrFullOnly:true,shortHorizonPriceConfirmation:true,positiveNetEdgeRequired:true},",
"entries:{liquiditySweepReclaim:true,breakoutRetestContinuation:true,trendPullbackReacceleration:true,trendPullback:false,trendContinuation:false,breakoutRetest:false,rangeMeanReversion:false,liquidationExhaustion:false,absorptionReversal:false,squeezeRelease:false,momentumEarlyRelease:false,rangeMicroReclaimScalp:false,transitionWsScalp:false,shortHorizonReversal:false,probeConfirmFull:false,confirmOrFullOnly:true,shortHorizonPriceConfirmation:true,positiveNetEdgeRequired:true,legacyBroadSetupRouterDisabled:true},",
'config three lane entries')

# Symbol router: old broad setup logic remains in the file for rollback/history, but is no longer the new-risk authority.
replace_once('bybit-symbol-strategy.js',
"import {selectBtcSetup as selectBaseSetup} from './bybit-btc-strategy.js';",
"import {selectScalpEntryV51} from './bybit-scalp-entry-v51.js';",
'v51 entry import')
new_router="""export function selectBybitSymbolSetup(s={}){const symbol=normalizeBybitSymbol(s.symbol||'BTCUSDT'),p=coinProfileForSymbol(symbol);if(!p)return {ok:false,reason:'SYMBOL_NOT_IN_MAJOR_CAP_UNIVERSE',symbol};const q=s?.quality||{},freshWs=String(s.microstructureSource)==='VPS_BYBIT_WS'&&q.freshBook===true&&q.freshTrades===true&&q.spreadOk!==false;if(!freshWs)return {ok:false,reason:'PROFILE_MICROSTRUCTURE_STALE_OR_FALLBACK_ONLY',symbol,profile:p,source:s.microstructureSource||null,freshBook:q.freshBook??null,freshTrades:q.freshTrades??null,spreadOk:q.spreadOk??null};const gate=profileGate(s,p);if(!gate.ok)return {...gate,symbol,profile:p};return selectScalpEntryV51({...s,symbol},p);}\nexport const BYBIT_SYMBOL_STRATEGY_VERSION='BYBIT_SYMBOL_COGNITION_V8_THREE_LANE_TTT_MAE';"""
regex_once('bybit-symbol-strategy.js',
r"export function selectBybitSymbolSetup\(s=\{\}\)\{.*?\}\nexport const BYBIT_SYMBOL_STRATEGY_VERSION='[^']+';",
new_router,
'v51 symbol router')

# Candidate ranking now prioritizes probability-adjusted net bps/minute and low MAE, not raw velocity/chasing.
new_rank="""function setupRank(r={}){const s=r?.scan?.best;if(!s)return null;const strength=String(s.strength||'NORMAL')==='A_PLUS'?3:String(s.strength||'NORMAL')==='STRONG'?2:1,tier=String(s.entryTier||'CONFIRM')==='FULL'?3:2,e=s.evidence||{},profile=coinProfileForSymbol(s.symbol||r?.market?.symbol||''),hit=clamp(num(e.hitProbability||e.score),0,1),quality=clamp(num(e.quality),0,1),netRR=num(s.cost?.netRewardRisk),priority=num(profile?.priority),expectedTimeToTargetSec=Math.max(1,num(e.expectedTimeToTargetSec)||999),expectedNetBpsPerMinute=Math.max(0,num(e.expectedNetBpsPerMinute)),maePenalty=clamp(num(e.maePenalty),0,1),scalpScore=Math.max(0,num(e.scalpScore)||hit*expectedNetBpsPerMinute*(1-maePenalty)),rankScore=hit*220+clamp(expectedNetBpsPerMinute,0,30)*4.5+(1-maePenalty)*35+strength*24+tier*10+quality*22+clamp(scalpScore,0,25)*2+priority/100;return {symbol:normalizeBybitSymbol(s.symbol||r?.market?.symbol||''),side:String(s.side||''),regime:String(s.regime||''),rankScore,strength:String(s.strength||'NORMAL'),entryTier:String(s.entryTier||'CONFIRM'),edgeScore:hit,quality,netRR,scalpVelocityBps:Number((num(e.velocityBpsPerSec)*5).toFixed(3)),velocityScore:Number(clamp(num(e.velocityBpsPerSec)/2,0,1).toFixed(3)),expectedTimeToTargetSec:Number(expectedTimeToTargetSec.toFixed(2)),expectedNetBpsPerMinute:Number(expectedNetBpsPerMinute.toFixed(3)),maePenalty:Number(maePenalty.toFixed(4)),scalpScore:Number(scalpScore.toFixed(4)),lane:String(e.lane||'V51_UNKNOWN'),priority,setup:String(s.setup||'V51_SCALP'),localCounterTrend:!!e.localCounterTrend,reversalValidated:!!e.reversalValidated,marketContrarianQualified:!!e.marketContrarianQualified};}\nfunction marketBreadth"""
regex_once('bybit-multi-asset-controller.js',
r"function setupRank\(r=\{\}\)\{.*?\}\nfunction marketBreadth",
new_rank,
'v51 controller ranking')

# Report the actual engine generation in state/telemetry.
p=ROOT/'bybit-symbol-engine.js';s=p.read_text();old='BYBIT-MULTI-ASSET-ENGINE-4.9.0-SCALP-FIRST-FAST-TURNOVER';new='BYBIT-MULTI-ASSET-ENGINE-5.1.0-THREE-LANE-MICROSTRUCTURE-SCALP';
if old in s:s=s.replace(old,new)
elif new not in s:raise SystemExit('MISSING:engine version')
p.write_text(s)

# Validator expectations and explicit V5.1 invariants.
p=ROOT/'validate-btc-hyperscale.mjs';s=p.read_text();s=s.replace("BYBIT-MULTI-STATEFLOW-5.0.0","BYBIT-MULTI-STATEFLOW-5.1.0").replace("BYBIT_MULTI_ASSET_RUNTIME_V28_SCALP_QUALITY_POSITIVE_EDGE","BYBIT_MULTI_ASSET_RUNTIME_V29_THREE_LANE_MICROSTRUCTURE_SCALP").replace("4.9.0-SCALP-FIRST-FAST-TURNOVER","5.1.0-THREE-LANE-MICROSTRUCTURE-SCALP")
marker="assert.equal(BYBIT_RUNTIME_CONTRACT.recoveryMartingale,false);assert.equal(BYBIT_RUNTIME_CONTRACT.recoveryAddToLoser,false);assert.equal(BYBIT_RUNTIME_CONTRACT.opportunityBreadthDoesNotIncreaseRiskBudget,true);assert.equal(BYBIT_RUNTIME_CONTRACT.plannedNetProfitFloorStartsAtOneUsd,true);assert.equal(BYBIT_RUNTIME_CONTRACT.profitFloorRelaxationDisabled,true);assert.ok(Number(BYBIT_RUNTIME_CONTRACT.minimumNewEntryPlannedNetProfitUsd)>=1);"
extra=marker+"assert.equal(BYBIT_RUNTIME_CONTRACT.entryTierAuthority,'CONFIRM_FULL_ONLY');for(const k of ['scalpEntryEngineV51','threeLaneScalpEntry','liquiditySweepReclaimLane','breakoutRetestContinuationLane','trendPullbackReaccelerationLane','expectedTimeToTargetGate','expectedTimeToTargetRanking','maeAwareEntryRanking','netProfitPerMinuteRanking','legacyBroadSetupRouterDisabledForNewRisk'])assert.equal(BYBIT_RUNTIME_CONTRACT[k],true,`V51 ${k}`);assert.equal(cfg.entries.liquiditySweepReclaim,true);assert.equal(cfg.entries.breakoutRetestContinuation,true);assert.equal(cfg.entries.trendPullbackReacceleration,true);assert.equal(cfg.entries.rangeMeanReversion,false);assert.equal(cfg.entries.momentumEarlyRelease,false);assert.equal(cfg.entries.transitionWsScalp,false);"
if extra not in s:
    if marker not in s:raise SystemExit('MISSING:validator marker')
    s=s.replace(marker,extra,1)
engine_marker="const engine=read('bybit-symbol-engine.js'),controller=read('bybit-multi-asset-controller.js'),dynamic=read('bybit-dynamic-universe.js'),runtime=read('bybit-runtime-contract.js'),balance=read('bybit-btc-balance-reconciler.js'),performance=read('bybit-performance-governor.js'),monitor=read('bybit-android-monitor.js'),capital=read('bybit-capital-state.js'),sync=read('bybit-capital-sync-handler.js'),bridge=read('../bybit-live-bridge/bybit_live_bridge.py');"
engine_extra=engine_marker+"\nconst symbolStrategy=read('bybit-symbol-strategy.js'),entryV51=read('bybit-scalp-entry-v51.js');assert.ok(symbolStrategy.includes('BYBIT_SYMBOL_COGNITION_V8_THREE_LANE_TTT_MAE'));for(const x of ['LIQUIDITY_SWEEP_RECLAIM','BREAKOUT_RETEST_CONTINUATION','TREND_PULLBACK_REACCELERATION','expectedTimeToTargetSec','expectedNetBpsPerMinute','maePenalty','V51_HIT_PROBABILITY_BELOW_QUALITY_FLOOR'])assert.ok(entryV51.includes(x),`ENTRY_V51 ${x}`);assert.ok(controller.includes('expectedNetBpsPerMinute'));assert.ok(controller.includes('maePenalty'));"
if engine_extra not in s:
    if engine_marker not in s:raise SystemExit('MISSING:validator engine marker')
    s=s.replace(engine_marker,engine_extra,1)
p.write_text(s)

print('BYBIT_V510_THREE_LANE_SCALP_PATCH_APPLIED')
