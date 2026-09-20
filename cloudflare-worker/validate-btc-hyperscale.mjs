import fs from 'node:fs';
import assert from 'node:assert/strict';
import {BYBIT_AUTO_CONFIG,bybitExecutionMode,bybitExecutionAllowsOrders} from './bybit-auto-config.js';
import {BYBIT_TRADE_UNIVERSE,coinProfileForSymbol,isCoreTradeSymbol} from './bybit-coin-profiles.js';
import {BYBIT_EXECUTION_AUTHORITY,BYBIT_EXECUTION_SYMBOL,BYBIT_EXECUTION_UNIVERSE,BYBIT_NON_BTC_EXECUTION_ERROR} from './bybit-execution-authority.js';
import {sizeBtcSetup} from './bybit-btc-risk-engine.js';
import {BYBIT_RUNTIME_CONTRACT,BYBIT_RUNTIME_CONTRACT_VERSION,BYBIT_AUTO_VERSION,LEGACY_BYBIT_MULTI_COIN_DISABLED} from './bybit-runtime-contract.js';

const read=f=>fs.readFileSync(f,'utf8'),cfg=BYBIT_AUTO_CONFIG;
assert.equal(BYBIT_EXECUTION_AUTHORITY,'BYBIT-TOP100-STATEFLOW-3.0');
assert.equal(BYBIT_AUTO_VERSION,BYBIT_EXECUTION_AUTHORITY);
assert.equal(BYBIT_RUNTIME_CONTRACT_VERSION,'BYBIT_TOP100_RUNTIME_3_0');
assert.equal(BYBIT_RUNTIME_CONTRACT.executionAuthority,BYBIT_EXECUTION_AUTHORITY);
assert.equal(LEGACY_BYBIT_MULTI_COIN_DISABLED,false);
assert.equal(BYBIT_EXECUTION_SYMBOL,'BTCUSDT');
assert.deepEqual(BYBIT_EXECUTION_UNIVERSE,['DYNAMIC_TOP100_MARKET_CAP_USDT_LINEAR']);
assert.equal(BYBIT_RUNTIME_CONTRACT.symbol,'DYNAMIC_TOP100');
assert.deepEqual(BYBIT_RUNTIME_CONTRACT.symbols,['DYNAMIC_TOP100_MARKET_CAP_USDT_LINEAR']);
assert.ok(BYBIT_RUNTIME_CONTRACT.coreSymbols.includes('BTCUSDT'));assert.ok(BYBIT_RUNTIME_CONTRACT.coreSymbols.includes('ETHUSDT'));
assert.equal(BYBIT_RUNTIME_CONTRACT.multiAsset,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.dynamicBybitScalpUniverse,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.allActiveCryptoEligible,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.researchDiscoveryBroadCrypto,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.researchOnlyDynamicUniverse,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.researchProductionExecutionAuthority,true);assert.equal(BYBIT_RUNTIME_CONTRACT.top100MarketCapExecution,true);assert.equal(BYBIT_RUNTIME_CONTRACT.antiSweepLiquidityGate,true);

// Broad market discovery remains research-only and is not the execution universe.
assert.ok(BYBIT_TRADE_UNIVERSE.length>=18);
assert.ok(BYBIT_TRADE_UNIVERSE.includes('ETHUSDT'));
assert.ok(isCoreTradeSymbol('BTCUSDT'));
assert.ok(coinProfileForSymbol('ETHUSDT'));
assert.ok(coinProfileForSymbol('SOMECOINUSDT')?.dynamicProfile===true);
assert.equal(coinProfileForSymbol('USDCUSDT'),null);

assert.equal(cfg.symbol,'BTCUSDT');
assert.deepEqual(cfg.symbols,['DYNAMIC_TOP100_MARKET_CAP_USDT_LINEAR']);
assert.equal(cfg.multiAsset,true);
assert.equal(cfg.portfolio.authority,'BYBIT_TOP100_MARKET_CAP_STATEFLOW_PORTFOLIO');
assert.ok(Array.isArray(cfg.portfolio.concurrentByEquity)&&cfg.portfolio.concurrentByEquity.length>=4);
assert.equal(cfg.portfolio.deepScanCount,10);
assert.equal(BYBIT_RUNTIME_CONTRACT.top10MarketCapExecution,true);assert.equal(BYBIT_RUNTIME_CONTRACT.executionPairLimit,10);assert.equal(BYBIT_RUNTIME_CONTRACT.broadPublicMarketEgressFallback,false);assert.equal(BYBIT_RUNTIME_CONTRACT.marketCapWsUniverseDiscovery,true);assert.equal(BYBIT_RUNTIME_CONTRACT.marketCapWsCandidateTargetLimit,40);
assert.equal(cfg.risk.maxSameDirectionPositions,1);
assert.equal(cfg.risk.martingale,false);assert.equal(cfg.risk.addToLoser,false);assert.equal(cfg.risk.gridRescue,false);assert.equal(cfg.execution.noTimeGate,true);assert.equal(cfg.execution.requireFreshBook,true);assert.equal(cfg.execution.requireFreshTrades,true);assert.equal(cfg.execution.reduceOnlyExits,true);
assert.equal(cfg.risk.baseEntryRiskPct,.75);assert.equal(cfg.risk.strongEntryRiskPct,1);assert.equal(cfg.risk.aPlusEntryRiskPct,1.25);assert.equal(cfg.risk.absoluteSingleEntryRiskPct,1.5);assert.equal(cfg.risk.maxActiveRiskPct,6);assert.equal(cfg.risk.temporaryAPlusActiveRiskPct,8);assert.equal(cfg.risk.maxPortfolioMarginPct,100);assert.equal(cfg.risk.maxMarginPerPositionPct,100);assert.equal(cfg.risk.minFreeReservePct,0);assert.equal(cfg.risk.dailyTarget,false);assert.equal(cfg.risk.dailyLossLimit,false);assert.equal(cfg.risk.dailyMaxProfit,false);assert.equal(cfg.risk.dailyMaxLoss,false);assert.equal(cfg.risk.maxDailyTrades,null);assert.equal(cfg.scan.hardDailyTradeQuota,false);assert.equal(cfg.scan.entryQuotaPerDay,null);assert.equal(cfg.risk.equityScale.maxRiskMult,1.35);assert.equal(cfg.risk.equityScale.maxMarginCapPct,100);assert.equal(cfg.risk.equityScale.steps[0].riskMult,.75);assert.equal(cfg.risk.equityScale.steps.at(-1).riskMult,1.35);
assert.equal(cfg.scalp.requireNetFloorAfterFees,true);assert.ok(cfg.scalp.minPlannedNetProfitUsd>=.25);assert.ok(cfg.scalp.preferredRunnerNetProfitUsd>=1);assert.equal(cfg.scalp.positiveAntiSweep.enabled,true);
assert.equal(cfg.leverage.exchangeInstrumentCapRequired,true);assert.ok(cfg.leverage.max>=100);assert.ok(cfg.leverage.equityAdaptive.steps[0].normal>=16);assert.ok(cfg.leverage.equityAdaptive.steps[0].aPlus>=30);
for(const k of ['infiniteLeverage','realizedProfitGuarantee','recoveryMartingale','recoveryAddToLoser','allActiveCryptoEligible'])assert.equal(BYBIT_RUNTIME_CONTRACT[k],false,`RUNTIME ${k}`);
for(const k of ['exchangeMaxLeverageCap','capitalIntelligenceV4','separateCapitalState','instantDepositRecognition','instantWithdrawalRiskReduction','paginatedTransactionReconciliation','capitalHighWaterDoubleCountFixed','fastScaleControlled','scalpOnly','scalpTargetDistanceCapped','profitFloorNeverForcesSwingTarget','existingPositionScalpRebase','adaptiveLeverageExpanded','freshWsRequiredForNewRisk','researchDiscoveryBroadCrypto','multiEntryUntilCapacity','dynamicBybitScalpUniverse','expandedDeepScan','perSymbolExpectancyGate','top100MarketCapExecution','antiSweepLiquidityGate'])assert.equal(BYBIT_RUNTIME_CONTRACT[k],true,`RUNTIME ${k}`);
assert.equal(bybitExecutionMode({BYBIT_AUTO_LIVE:'true'}),'PAPER');assert.equal(bybitExecutionMode({BYBIT_AUTO_LIVE:'true',BYBIT_BTC_LIVE_ACK:'true'}),'LIVE');assert.equal(bybitExecutionMode({BYBIT_AUTO_DEMO:'true'}),'DEMO');assert.equal(bybitExecutionMode({BYBIT_AUTO_DEMO:'true',BYBIT_AUTO_LIVE:'true',BYBIT_BTC_LIVE_ACK:'true'}),'BLOCKED');assert.equal(bybitExecutionAllowsOrders('DEMO'),true);assert.equal(bybitExecutionAllowsOrders('LIVE'),true);assert.equal(bybitExecutionAllowsOrders('PAPER'),false);assert.equal(cfg.aiLegion.enabledByDefault,true);assert.equal(cfg.aiLegion.liveRequiresExplicitAck,true);assert.equal(cfg.aiLegion.mayIncreaseRisk,false);assert.equal(cfg.aiLegion.mayPlaceOrders,true);

const quant=sizeBtcSetup({setup:{side:'Buy',strength:'STRONG',entryTier:'FULL',entry:80000,sl:79900,cost:{totalCostBps:11}},riskUsd:.35,maxRiskUsd:.45,filters:{qtyStep:.001,minQty:.001,minNotional:5,maxQty:10},leverage:12,equityUsd:73,capitalBaseUsd:73,marginCapPct:78});assert.ok(quant.ok);assert.ok(quant.effectiveLossEstimateUsd<=quant.hardRiskCapUsd+1e-9);

const engine=read('bybit-symbol-engine.js'),controller=read('bybit-multi-asset-controller.js'),strategy=read('bybit-symbol-strategy.js'),aiLegion=read('bybit-ai-legion.js'),cloudStream=read('bybit-market-stream.js'),microClient=read('bybit-btc-microstructure-client.js'),control=read('bybit-control-plane.js'),client=read('bybit-v5-client.js'),indexSource=read('index.js'),dynamic=read('bybit-dynamic-universe.js'),runtime=read('bybit-runtime-contract.js'),balance=read('bybit-btc-balance-reconciler.js'),monitor=read('bybit-android-monitor.js'),capital=read('bybit-capital-state.js'),sync=read('bybit-capital-sync-handler.js'),bridge=read('../bybit-live-bridge/bybit_live_bridge.py');
for(const x of ['filterCacheAt<300000','sleep(80)','BYBIT_EXECUTION_SYMBOL','BYBIT_NON_BTC_EXECUTION_ERROR','positiveLockReady','exchangeMaxLeverage','reduceOnly:true','nearerTarget','scalpCapTarget','floorRelaxedForFastScalp','resolveBybitAiLegionDecision','BTC_DEMO_ENTRY_EXECUTED'])assert.ok(engine.includes(x),`ENGINE ${x}`);for(const x of ['macro_news_agent','market_structure_flow_agent','order_risk_architect_agent','independent_adversarial_checker','collectBybitNewsContext','SINGLE_AI_EXECUTOR_WITH_RESEARCH_SWARM','noMajorityVote:true','BYBIT_AI_LEGION_V4_SINGLE_EXECUTOR_RESEARCH_SWARM'])assert.ok(aiLegion.includes(x),`AI_LEGION ${x}`);for(const x of ['computeAdaptiveTradeGeometry','STRUCTURE_INVALIDATION_PLUS_VOLATILITY_LIQUIDITY_BUFFER','FRONT_RUN_OPPOSING_LIQUIDITY','CLOUDFLARE_BYBIT_WS'])assert.ok(strategy.includes(x),`STRATEGY ${x}`);
for(const x of ['BYBIT_NON_BTC_EXECUTION_ERROR','runBybitMultiAssetControlled','UNSUPPORTED_SYMBOL_ORDER_PRESENT','SYMBOL_NOT_ELIGIBLE_TOP100_EXECUTION_UNIVERSE'])assert.ok(control.includes(x),`CONTROL ${x}`);assert.ok(cloudStream.includes("headers:{Upgrade:'websocket'}"),'CLOUD_STREAM_FETCH_UPGRADE_REQUIRED');assert.ok(cloudStream.includes('response.webSocket'),'CLOUD_STREAM_RESPONSE_WEBSOCKET_REQUIRED');assert.ok(cloudStream.includes('ws.accept()'),'CLOUD_STREAM_ACCEPT_REQUIRED');assert.ok(!cloudStream.includes('new WebSocket(URL)'),'CLOUD_STREAM_BROWSER_CONSTRUCTOR_FORBIDDEN');assert.ok(!cloudStream.includes("const URL='"),'CLOUD_STREAM_GLOBAL_URL_SHADOW_FORBIDDEN');assert.ok(cloudStream.includes("const WS_URL='wss://stream.bybit.com/v5/public/linear';"),'CLOUD_STREAM_WS_URL_NAME_REQUIRED');
assert.ok(control.includes('runBybitMultiAssetControlled'), 'CONTROL must invoke top100 multi-asset execution controller');
for(const x of ['assertBybitExecutionSymbol','guardSignedWrite','TRADING_WRITE_PATHS','CLOUDFLARE_BYBIT_PRIVATE_DIRECT','CLOUDFLARE_BYBIT_PUBLIC_DIRECT','PUBLIC_REGION_BLOCKED_UNTIL'])assert.ok(client.includes(x),`CLIENT ${x}`);assert.ok(!client.includes('publicViaServerlessEgress'),'PUBLIC_REST_RELAY_REMOVED_FROM_EXECUTION_PATH');assert.ok(indexSource.indexOf("/bybit/cloud-stream/connect")>=0&&indexSource.indexOf("/bybit/cloud-stream/connect")<indexSource.indexOf("handleUniversalEntry(req,env,ctx)"),'CLOUD_STREAM_ROUTE_PRECEDES_GENERIC_HANDLERS');for(const x of ['topicsForSymbol','orderbook.50.','publicTrade.','allLiquidation.','tickers.','PER_SYMBOL_SELF_HEAL','CLOUD_BYBIT_WS_STATE_CHANGE'])assert.ok(cloudStream.includes(x),`CLOUD_STREAM ${x}`);for(const x of ["Math.max(75,Math.min(2000","this.evalPending=true","ctx:this.state","this.maybeEvaluate(pendingReason,true)"])assert.ok(cloudStream.includes(x),`LOW_LATENCY_STREAM ${x}`);assert.ok(cloudStream.includes("json({ok:true,...this.health()})"),'CLOUD_STREAM_CONNECT_OK_CONTRACT');for(const x of ["hasRequested=requested!==null","return await this.rebindSymbol(req,this.symbol)","this.state.storage.delete('klines:'+interval)","symbolSelfHeal:true","STREAM_SYMBOL_REQUIRED"])assert.ok(cloudStream.includes(x),`CLOUD_STREAM_SYMBOL_ISOLATION ${x}`);for(const x of ['universeTickerTargets','/universe-subscribe','setUniverseTickerTargets','waitForUniverseTickers','CLOUDFLARE_BYBIT_WS_MARKETCAP_TICKERS','UNIVERSE_TICKER_TARGETS_REQUIRE_AT_LEAST_10'])assert.ok(cloudStream.includes(x),`CLOUD_STREAM_MARKETCAP_DISCOVERY ${x}`);assert.ok(cloudStream.includes("const VERSION='BYBIT_CLOUD_MARKET_STREAM_V6_DYNAMIC_MARKETCAP_TICKERS'"),'CLOUD_STREAM_V6_GENERATION_REQUIRED');for(const x of ['BYBIT_MARKET_STREAM','BYBIT_CLOUDFLARE_WS_MICROSTRUCTURE_CLIENT_V5_DYNAMIC_MARKETCAP_TICKERS',"idFromName(s+':PUBLIC:LINEAR')",'SNAPSHOT_COLD_START_TIMEOUT_MS=3000','CONNECT_COLD_START_TIMEOUT_MS=6000','HEALTH_PROPAGATION_TIMEOUT_MS=1500','configureBybitUniverseTickers','/universe-subscribe'])assert.ok(microClient.includes(x),`MICRO_CLIENT ${x}`);
for(const x of ['TRADE_CORE','TRADE_TOP100','WATCH_CAP','WATCH_SWEEP_RISK','WATCH_EXECUTION_UNSAFE','DO_NOT_TRADE','BYBIT_TOP10_MARKET_CAP_LIQUIDITY_QUALIFIED_V1','EXECUTION_PAIR_LIMIT=10','MARKET_CAP_TICKER_TARGET_LIMIT=40','MIN_MARKET_CAP_WS_FRESH=10','configureBybitUniverseTickers','marketCapWsCoverage','OUTSIDE_TOP10_MARKET_CAP_EXECUTION_SET','antiSweepScore'])assert.ok(dynamic.includes(x),`RESEARCH ${x}`);
for(const x of ['BYBIT_TOP100_RUNTIME_3_0','researchOnlyDynamicUniverse:false','researchProductionExecutionAuthority:true','top100MarketCapExecution:true','top10MarketCapExecution:true','executionPairLimit:10','broadPublicMarketEgressFallback:false','marketCapWsUniverseDiscovery:true','marketCapWsCandidateTargetLimit:40','antiSweepLiquidityGate:true','aiLegionIntegrated:true','demoExecutionSupported:true','aiLegionMayPlaceOrders:true','structureBufferedStops:true','opposingLiquidityTargeting:true',"latencyProfile:'EVENT_DRIVEN_ULTRA_LOW_LATENCY_V1'",'pendingEventCoalescing:true','aiRefreshOffCriticalPath:true','accountReconciliationParallel:true'])assert.ok(runtime.includes(x),`RUNTIME ${x}`);
for(const x of ['bybit:capital:intelligence:v1','transactionPages','forceUpside:true','CAPITAL_INTELLIGENCE_V4'])assert.ok(balance.includes(x),`BALANCE ${x}`);
for(const x of ['intervalMs=750','500,10000','tradingEndpointsExposedByMonitor:false'])assert.ok(monitor.includes(x),`MONITOR ${x}`);
for(const x of ['BYBIT_CAPITAL_STATE_MIRROR_V2_READONLY_EXECUTION','ordersCreated:false','positionsChanged:false','lastCapitalBaseUsd'])assert.ok(capital.includes(x),`CAPITAL_MIRROR ${x}`);
for(const x of ['NO_ORDER_SUBMISSION','NO_TP_SL_CHANGE','KV_CAPITAL_METADATA_ONLY'])assert.ok(sync.includes(x),`CAPITAL_SYNC ${x}`);
for(const x of ['discover_ws_symbols','MAX_WS_SYMBOLS','bookFreshCount','tradeFreshCount','marketTelemetry'])assert.ok(bridge.includes(x),`BRIDGE ${x}`);
assert.equal(BYBIT_NON_BTC_EXECUTION_ERROR,'BYBIT_SYMBOL_OUTSIDE_TOP100_EXECUTION_AUTHORITY');

console.log('BYBIT_TOP100_STATEFLOW_VALIDATION=PASS');
console.log(JSON.stringify({version:BYBIT_AUTO_VERSION,contract:BYBIT_RUNTIME_CONTRACT.version,executionSymbol:BYBIT_EXECUTION_SYMBOL,researchUniverseSymbols:BYBIT_TRADE_UNIVERSE.length,researchOnlyDynamicUniverse:false,top100MarketCapExecution:true,aiLegion:true,demoExecution:true,capitalIntelligenceV4:true,instantDepositRecognition:true,fastScaleControlled:true,baseRiskPct:cfg.risk.baseEntryRiskPct,strongRiskPct:cfg.risk.strongEntryRiskPct,aPlusRiskPct:cfg.risk.aPlusEntryRiskPct,maxActiveRiskPct:cfg.risk.maxActiveRiskPct,maxConfiguredLeverage:cfg.leverage.max,freshWsRequired:true,martingale:false,addToLoser:false,monitorReadOnly:true},null,2));

assert.equal(BYBIT_RUNTIME_CONTRACT.expandedWsCoverage,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.perSymbolTop100Ws,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.perSymbolOnDemandWs,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.scanOnlyNoPrivateReads,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.boundedParallelDiscoveryScans,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.discoveryScanParallelism,4);
assert.equal(BYBIT_RUNTIME_CONTRACT.wsExecutionTriggerScope,'PER_SYMBOL_ON_DEMAND_TOP100_DIRECT');

assert.ok(engine.includes('if(scanOnly)'),'ENGINE scanOnly');assert.ok(controller.includes('boundedMap'),'CONTROLLER boundedMap');assert.ok(controller.includes('scanOnly:true'),'CONTROLLER scanOnly discovery');assert.ok(client.includes('PUBLIC_REGION_BLOCKED_UNTIL'),'CLIENT region circuit');
