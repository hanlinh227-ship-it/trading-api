import fs from 'node:fs';
import assert from 'node:assert/strict';
import {BYBIT_AUTO_CONFIG,bybitExecutionMode} from './bybit-auto-config.js';
import {BYBIT_TRADE_UNIVERSE,coinProfileForSymbol,isCoreTradeSymbol} from './bybit-coin-profiles.js';
import {BYBIT_EXECUTION_AUTHORITY,BYBIT_EXECUTION_SYMBOL,BYBIT_EXECUTION_UNIVERSE,BYBIT_NON_BTC_EXECUTION_ERROR} from './bybit-execution-authority.js';
import {sizeBtcSetup} from './bybit-btc-risk-engine.js';
import {BYBIT_RUNTIME_CONTRACT,BYBIT_RUNTIME_CONTRACT_VERSION,BYBIT_AUTO_VERSION,LEGACY_BYBIT_MULTI_COIN_DISABLED} from './bybit-runtime-contract.js';

const read=f=>fs.readFileSync(f,'utf8'),cfg=BYBIT_AUTO_CONFIG;
assert.equal(BYBIT_EXECUTION_AUTHORITY,'BYBIT-BTC-STATEFLOW-2.1');
assert.equal(BYBIT_AUTO_VERSION,BYBIT_EXECUTION_AUTHORITY);
assert.equal(BYBIT_RUNTIME_CONTRACT_VERSION,'BYBIT_BTC_RUNTIME_2_1');
assert.equal(BYBIT_RUNTIME_CONTRACT.executionAuthority,BYBIT_EXECUTION_AUTHORITY);
assert.equal(LEGACY_BYBIT_MULTI_COIN_DISABLED,true);
assert.equal(BYBIT_EXECUTION_SYMBOL,'BTCUSDT');
assert.deepEqual(BYBIT_EXECUTION_UNIVERSE,['BTCUSDT']);
assert.equal(BYBIT_RUNTIME_CONTRACT.symbol,'BTCUSDT');
assert.deepEqual(BYBIT_RUNTIME_CONTRACT.symbols,['BTCUSDT']);
assert.deepEqual(BYBIT_RUNTIME_CONTRACT.coreSymbols,['BTCUSDT']);
assert.equal(BYBIT_RUNTIME_CONTRACT.multiAsset,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.dynamicBybitScalpUniverse,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.allActiveCryptoEligible,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.researchDiscoveryBroadCrypto,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.researchOnlyDynamicUniverse,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.researchProductionExecutionAuthority,false);

// Broad market discovery remains research-only and is not the execution universe.
assert.ok(BYBIT_TRADE_UNIVERSE.length>=18);
assert.ok(BYBIT_TRADE_UNIVERSE.includes('ETHUSDT'));
assert.ok(isCoreTradeSymbol('BTCUSDT'));
assert.ok(coinProfileForSymbol('ETHUSDT'));
assert.ok(coinProfileForSymbol('SOMECOINUSDT')?.dynamicProfile===true);
assert.equal(coinProfileForSymbol('USDCUSDT'),null);

assert.equal(cfg.symbol,'BTCUSDT');
assert.deepEqual(cfg.symbols,['BTCUSDT']);
assert.equal(cfg.multiAsset,false);
assert.equal(cfg.portfolio.authority,'BYBIT_BTC_STATEFLOW_SINGLE_EXECUTION_UNIVERSE');
assert.deepEqual(cfg.portfolio.concurrentByEquity,[{equityUsd:0,max:1}]);
assert.equal(cfg.risk.maxSameDirectionPositions,1);
assert.equal(cfg.risk.martingale,false);assert.equal(cfg.risk.addToLoser,false);assert.equal(cfg.risk.gridRescue,false);assert.equal(cfg.execution.noTimeGate,true);assert.equal(cfg.execution.requireFreshBook,true);assert.equal(cfg.execution.requireFreshTrades,true);assert.equal(cfg.execution.reduceOnlyExits,true);
assert.ok(cfg.risk.baseEntryRiskPct>=1);assert.ok(cfg.risk.strongEntryRiskPct>=1.4);assert.ok(cfg.risk.aPlusEntryRiskPct>=2);assert.ok(cfg.risk.absoluteSingleEntryRiskPct>=2.2);assert.ok(cfg.risk.maxActiveRiskPct>=7);assert.ok(cfg.risk.maxPortfolioMarginPct<=85);assert.ok(cfg.risk.minFreeReservePct>=10);
assert.equal(cfg.scalp.requireNetFloorAfterFees,true);assert.ok(cfg.scalp.minPlannedNetProfitUsd>=.25);assert.ok(cfg.scalp.preferredRunnerNetProfitUsd>=1);assert.equal(cfg.scalp.positiveAntiSweep.enabled,true);
assert.equal(cfg.leverage.exchangeInstrumentCapRequired,true);assert.ok(cfg.leverage.max>=100);assert.ok(cfg.leverage.equityAdaptive.steps[0].normal>=16);assert.ok(cfg.leverage.equityAdaptive.steps[0].aPlus>=30);
for(const k of ['infiniteLeverage','realizedProfitGuarantee','recoveryMartingale','recoveryAddToLoser','multiEntryUntilCapacity','dynamicBybitScalpUniverse','allActiveCryptoEligible'])assert.equal(BYBIT_RUNTIME_CONTRACT[k],false,`RUNTIME ${k}`);
for(const k of ['exchangeMaxLeverageCap','capitalIntelligenceV4','separateCapitalState','instantDepositRecognition','instantWithdrawalRiskReduction','paginatedTransactionReconciliation','capitalHighWaterDoubleCountFixed','fastScaleControlled','scalpOnly','scalpTargetDistanceCapped','profitFloorNeverForcesSwingTarget','existingPositionScalpRebase','adaptiveLeverageExpanded','freshWsRequiredForNewRisk','researchDiscoveryBroadCrypto','researchOnlyDynamicUniverse'])assert.equal(BYBIT_RUNTIME_CONTRACT[k],true,`RUNTIME ${k}`);
assert.equal(bybitExecutionMode({BYBIT_AUTO_LIVE:'true'}),'PAPER');assert.equal(bybitExecutionMode({BYBIT_AUTO_LIVE:'true',BYBIT_BTC_LIVE_ACK:'true'}),'LIVE');

const quant=sizeBtcSetup({setup:{side:'Buy',strength:'STRONG',entryTier:'FULL',entry:80000,sl:79900,cost:{totalCostBps:11}},riskUsd:.35,maxRiskUsd:.45,filters:{qtyStep:.001,minQty:.001,minNotional:5,maxQty:10},leverage:12,equityUsd:73,capitalBaseUsd:73,marginCapPct:78});assert.ok(quant.ok);assert.ok(quant.effectiveLossEstimateUsd<=quant.hardRiskCapUsd+1e-9);

const engine=read('bybit-symbol-engine.js'),control=read('bybit-control-plane.js'),client=read('bybit-v5-client.js'),dynamic=read('bybit-dynamic-universe.js'),runtime=read('bybit-runtime-contract.js'),balance=read('bybit-btc-balance-reconciler.js'),monitor=read('bybit-android-monitor.js'),capital=read('bybit-capital-state.js'),sync=read('bybit-capital-sync-handler.js'),bridge=read('../bybit-live-bridge/bybit_live_bridge.py');
for(const x of ['BYBIT_EXECUTION_SYMBOL','BYBIT_NON_BTC_EXECUTION_ERROR','positiveLockReady','exchangeMaxLeverage','reduceOnly:true','nearerTarget','scalpCapTarget','floorRelaxedForFastScalp'])assert.ok(engine.includes(x),`ENGINE ${x}`);
for(const x of ['BYBIT_NON_BTC_EXECUTION_ERROR','runBtcHyperscale','researchOnly:true','UNMANAGED_SYMBOL_ORDER_PRESENT'])assert.ok(control.includes(x),`CONTROL ${x}`);
assert.ok(!control.includes('runBybitMultiAssetControlled'), 'CONTROL must not invoke legacy multi-asset execution controller');
for(const x of ['assertBybitExecutionSymbol','guardSignedWrite','TRADING_WRITE_PATHS'])assert.ok(client.includes(x),`CLIENT ${x}`);
for(const x of ['TRADE_CORE','TRADE_ALL_CRYPTO','WATCH_EXECUTION_UNSAFE','DO_NOT_TRADE','BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V5_ALL_ACTIVE_CRYPTO'])assert.ok(dynamic.includes(x),`RESEARCH ${x}`);
for(const x of ['BYBIT_BTC_RUNTIME_2_1','researchOnlyDynamicUniverse:true','researchProductionExecutionAuthority:false'])assert.ok(runtime.includes(x),`RUNTIME ${x}`);
for(const x of ['bybit:capital:intelligence:v1','transactionPages','forceUpside:true','CAPITAL_INTELLIGENCE_V4'])assert.ok(balance.includes(x),`BALANCE ${x}`);
for(const x of ['intervalMs=750','500,10000','tradingEndpointsExposedByMonitor:false'])assert.ok(monitor.includes(x),`MONITOR ${x}`);
for(const x of ['BYBIT_CAPITAL_STATE_MIRROR_V2_READONLY_EXECUTION','ordersCreated:false','positionsChanged:false','lastCapitalBaseUsd'])assert.ok(capital.includes(x),`CAPITAL_MIRROR ${x}`);
for(const x of ['NO_ORDER_SUBMISSION','NO_TP_SL_CHANGE','KV_CAPITAL_METADATA_ONLY'])assert.ok(sync.includes(x),`CAPITAL_SYNC ${x}`);
for(const x of ['discover_ws_symbols','MAX_WS_SYMBOLS','bookFreshCount','tradeFreshCount','marketTelemetry'])assert.ok(bridge.includes(x),`BRIDGE ${x}`);
assert.equal(BYBIT_NON_BTC_EXECUTION_ERROR,'BYBIT_NON_BTC_EXECUTION_RETIRED');

console.log('BYBIT_BTC_STATEFLOW_VALIDATION=PASS');
console.log(JSON.stringify({version:BYBIT_AUTO_VERSION,contract:BYBIT_RUNTIME_CONTRACT.version,executionSymbol:BYBIT_EXECUTION_SYMBOL,researchUniverseSymbols:BYBIT_TRADE_UNIVERSE.length,researchOnlyDynamicUniverse:true,capitalIntelligenceV4:true,instantDepositRecognition:true,fastScaleControlled:true,baseRiskPct:cfg.risk.baseEntryRiskPct,strongRiskPct:cfg.risk.strongEntryRiskPct,aPlusRiskPct:cfg.risk.aPlusEntryRiskPct,maxActiveRiskPct:cfg.risk.maxActiveRiskPct,maxConfiguredLeverage:cfg.leverage.max,freshWsRequired:true,martingale:false,addToLoser:false,monitorReadOnly:true},null,2));
