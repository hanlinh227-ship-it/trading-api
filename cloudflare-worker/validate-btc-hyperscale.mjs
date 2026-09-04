import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {BYBIT_AUTO_CONFIG,bybitAutoConfig,bybitExecutionMode} from './bybit-auto-config.js';
import {drawdownState,btcRiskDecision,equityScaleState,capitalBaseState,sizeBtcSetup} from './bybit-btc-risk-engine.js';
import {selectBtcSetup} from './bybit-btc-strategy.js';

const root=process.cwd();
const read=f=>fs.readFileSync(path.join(root,f),'utf8');
const readRepo=f=>fs.readFileSync(path.resolve(root,'..',f),'utf8');
const required=['index.js','bybit-runtime-contract.js','bybit-auto-config.js','bybit-auto-controller.js','bybit-auto-hub.js','bybit-control-plane.js','bybit-readonly-health.js','bybit-v5-client.js','bybit-btc-balance-reconciler.js','bybit-btc-microstructure-client.js','bybit-btc-market-state.js','bybit-btc-strategy.js','bybit-btc-risk-engine.js','bybit-btc-engine.js','prepare-wrangler.mjs','providers/bybit-signed-client.js','providers/telegram-client.js'];
for(const f of required)assert.ok(fs.existsSync(path.join(root,f)),`MISSING ${f}`);
for(const old of ['bybit-auto-v1.js','v11','providers/anthropic-client.js','providers/decision-evidence.js','providers/entry-intelligence.js','providers/indicators.js'])assert.ok(!fs.existsSync(path.join(root,old)),`LEGACY ACTIVE BOT FILE MUST BE REMOVED ${old}`);

const cfg=bybitAutoConfig({});
assert.equal(cfg.symbol,'BTCUSDT');assert.equal(cfg.category,'linear');
assert.equal(cfg.risk.martingale,false);assert.equal(cfg.risk.gridRescue,false);assert.equal(cfg.risk.addToLoser,false);assert.equal(cfg.risk.pyramidWinner,true);
assert.equal(cfg.scan.hardDailyTradeQuota,false);assert.equal(cfg.scan.entryQuotaPerDay,null);assert.equal(cfg.scan.timeGate,false);assert.equal(cfg.scan.sessionGate,false);assert.equal(cfg.scan.cooldownGate,false);
assert.equal(cfg.execution.noTimeGate,true);assert.equal(cfg.execution.managementEveryMarketStateChange,true);assert.equal(cfg.risk.timedPause,false);assert.equal(cfg.risk.lossStreakTimeGate,false);
assert.equal(cfg.risk.fullAccountAuthority,true);assert.ok(cfg.risk.absoluteSingleEntryRiskPct<=1.6);assert.ok(cfg.risk.maxPortfolioMarginPct<=85);assert.ok(cfg.risk.minFreeReservePct>=10);
assert.equal(bybitExecutionMode({BYBIT_AUTO_LIVE:'true'}),'PAPER');assert.equal(bybitExecutionMode({BYBIT_AUTO_LIVE:'true',BYBIT_BTC_LIVE_ACK:'true'}),'LIVE');

const dd4=drawdownState({equityUsd:96,highWaterUsd:100,cfg}),dd20=drawdownState({equityUsd:80,highWaterUsd:100,cfg});assert.equal(dd4.multiplier,.9);assert.equal(dd20.multiplier,0);assert.equal(dd20.newRiskLocked,true);
const cUp=capitalBaseState({equityUsd:120,walletBalanceUsd:100,cfg});assert.equal(cUp.capitalBaseUsd,105);
const s50=equityScaleState(50,cfg),s60=equityScaleState(60,cfg),s75=equityScaleState(75,cfg);assert.ok(s60.riskMult>s50.riskMult&&s60.riskMult<s75.riskMult);
const setup={side:'Buy',strength:'NORMAL',entry:101,sl:100,tp:103,rr:2,setup:'TEST',regime:'TREND_UP'};
let r=btcRiskDecision({cfg,equityUsd:100,state:{lastWalletBalanceUsd:100,highWaterUsd:100,tranches:[{id:'L1',status:'OPEN',side:'Buy',qty:1,entry:100,sl:99,managedSl:99,initialRiskUsd:1,createdAt:1}]},setup,markPrice:99});assert.equal(r.ok,false);assert.equal(r.reason,'NO_ADD_TO_LOSER');
const protectedWinner=[{id:'P',status:'OPEN',side:'Buy',qty:1,entry:100,sl:100.1,managedSl:100.1,initialRiskUsd:1,createdAt:2}];r=btcRiskDecision({cfg,equityUsd:100,state:{lastWalletBalanceUsd:100,highWaterUsd:100,tranches:protectedWinner},setup,markPrice:101});assert.equal(r.ok,true);

const quant=sizeBtcSetup({setup:{side:'Buy',strength:'NORMAL',entry:80930,sl:80535.5,cost:{totalCostBps:11.2}},riskUsd:.33,maxRiskUsd:.62,filters:{qtyStep:.001,minQty:.001,minNotional:5,maxQty:10},leverage:6,equityUsd:39,capitalBaseUsd:39,marginCapPct:72});assert.equal(quant.ok,true);assert.equal(quant.qty,.001);assert.ok(quant.actualRiskUsd<=quant.hardRiskCapUsd+1e-9);assert.ok(quant.costReserveUsd>0);
const quantLarger=sizeBtcSetup({setup:{side:'Buy',strength:'STRONG',entry:80930,sl:80535.5,cost:{totalCostBps:11.2}},riskUsd:1,maxRiskUsd:1.6,filters:{qtyStep:.001,minQty:.001,minNotional:5,maxQty:10},leverage:8,equityUsd:120,capitalBaseUsd:120,marginCapPct:78});assert.equal(quantLarger.ok,true);assert.ok(quantLarger.qty>=.002);assert.ok(quantLarger.actualRiskUsd<=1.6+1e-9);

const noEntry=selectBtcSetup({quality:{freshBook:true,freshTrades:true,spreadOk:true},regime:'HIGH_VOL_SHOCK',trades:{aggressorImbalance:.9},book:{imbalance5:.9},openInterest:{deltaPct:1},direction5:1,direction15:1,direction60:1,efficiency15:.9,crowding:{}});assert.equal(noEntry.ok,false);assert.equal(noEntry.reason,'HIGH_VOL_SHOCK_NO_NEW_RISK');
const momentumEarly=selectBtcSetup({quality:{freshBook:true,freshTrades:true,spreadOk:true,wsFastPath:true},microstructureSource:'VPS_BYBIT_WS',regime:'SQUEEZE',price:80000,range5:{width:500},range15:{width:700},structure5:{breakUp:false,breakDown:false},structure15:{recentLow:79700,recentHigh:80300},sweep5:{priorLow:79700,priorHigh:80300},trades:{window5s:{imbalance:.42},window15s:{imbalance:.48},window60s:{imbalance:.21},burst5x:.31},ultraFast:{flowAcceleration:.12,pressureScore:.31,impulseScore:.27,signPersistence:2},book:{imbalance2:.14,imbalance5:.12,micropriceEdgeBps:.08},openInterest:{deltaPct:.04},direction5:.08,direction15:.01,direction60:.02,efficiency15:.08,crowding:{},executionCost:{baseRoundTripCostBps:11,fundingWithinExpectedHold:false,fundingRate:0}});assert.equal(momentumEarly.ok,true);assert.equal(momentumEarly.setup.setup,'SQUEEZE_MOMENTUM_EARLY_RELEASE');
const conflictNoEntry=selectBtcSetup({quality:{freshBook:true,freshTrades:true,spreadOk:true,wsFastPath:true},microstructureSource:'VPS_BYBIT_WS',regime:'SQUEEZE',price:80000,range5:{width:500},range15:{width:700},structure5:{breakDown:true},structure15:{recentLow:79700,recentHigh:80300},sweep5:{priorLow:79700,priorHigh:80300},trades:{window5s:{imbalance:-.16},window15s:{imbalance:-.50},window60s:{imbalance:-.32},burst5x:.07},ultraFast:{flowAcceleration:.34,pressureScore:-.12,impulseScore:.07,signPersistence:2},book:{imbalance2:.28,imbalance5:.28,micropriceEdgeBps:.01},openInterest:{deltaPct:.02},direction5:-.19,direction15:0,direction60:-.18,efficiency15:.01,crowding:{},executionCost:{baseRoundTripCostBps:11,fundingWithinExpectedHold:false,fundingRate:0}});assert.equal(conflictNoEntry.ok,false);

const index=read('index.js'),runtime=read('bybit-runtime-contract.js'),controller=read('bybit-auto-controller.js'),control=read('bybit-control-plane.js'),client=read('bybit-v5-client.js'),engine=read('bybit-btc-engine.js'),risk=read('bybit-btc-risk-engine.js'),strategy=read('bybit-btc-strategy.js'),market=read('bybit-btc-market-state.js'),telegram=read('providers/telegram-client.js'),hub=read('bybit-auto-hub.js'),prep=read('prepare-wrangler.mjs'),workflow=readRepo('.github/workflows/deploy-cloudflare-worker.yml');
assert.ok(index.includes('legacyBotsDisabled:true'));assert.ok(index.includes('scheduledExecution:false'));assert.ok(!index.includes('scheduled(event'));assert.ok(!index.includes('recordBybitAutoSchedulerError'));
for(const x of ['BYBIT_BTC_RUNTIME_CONTRACT_V9_EVENT_DRIVER_ONLY','decisionAuthority:\'VPS_WS_MARKET_STATE_CHANGE\'','entryTriggerAuthority:\'VPS_BRIDGE_SECRET_ONLY\'','cronRole:\'NONE_EVENT_DRIVER_ONLY\'','scheduledExecution:false','timeGate:false','strategyCooldown:\'NONE\'','dailyTradeQuota:\'NONE\''])assert.ok(runtime.includes(x),`RUNTIME missing ${x}`);
for(const x of ['notifyPendingLiveEntries','ENTRY_ALERTS_CONFIRMED','IDEMPOTENT_WRITE_NO_CHANGE','entrySpacingSec:0','timeGate:false','eventDriven:true'])assert.ok(controller.includes(x),`CONTROLLER missing ${x}`);assert.ok(!controller.includes('cooldownSec'));assert.ok(!controller.includes('BTC_ENTRY_SPACING_'));
for(const x of ['BTC_ENTRY_TRIGGER_REQUIRES_VPS_WS_DRIVER','VPS_BRIDGE_SECRET_ONLY','a.source!=="VPS_BRIDGE_SECRET"','BTC_ENGINE_DISABLED'])assert.ok(control.includes(x),`CONTROL missing ${x}`);
for(const x of ['TRADING_STOP_UNCHANGED','LEVERAGE_UNCHANGED','BYBIT_VPS_BRIDGE_SECRET','unchangedWrite'])assert.ok(client.includes(x),`CLIENT missing ${x}`);
for(const x of ['reconcileTranchesToPosition','EXCHANGE_POSITION_RECONCILED','candidateActualRiskUsd:sized.actualRiskUsd','UNPROTECTED_POSITION_EMERGENCY_FLAT','rewardToTarget','BYBIT-BTC-HYPERSCALE-2.6-RECONCILED'])assert.ok(engine.includes(x),`ENGINE missing ${x}`);
for(const x of ['BTC_RISK_RECYCLE_V6_SMART_QUANTIZED_SIZING','maxCandidateRiskUsd','candidateActualRiskUsd','NEAREST_TARGET_WITH_STRENGTH_AWARE_UPSTEP_WITHIN_HARD_CAP'])assert.ok(risk.includes(x),`RISK missing ${x}`);assert.ok(!risk.includes("row={id,symbol:'BTCUSDT'"),'RISK duplicate id pattern returned');
for(const x of ['BREAKOUT_MOMENTUM_FLOW_CONFIRM','TREND_MOMENTUM_CONTINUATION','SQUEEZE_MOMENTUM_EARLY_RELEASE','TRANSITION_MOMENTUM_CONFIRM','VPS_BYBIT_WS'])assert.ok(strategy.includes(x),`STRATEGY missing ${x}`);
for(const x of ['executionCost','ultraFast','fetchBtcMicrostructure'])assert.ok(market.includes(x),`MARKET missing ${x}`);
for(const x of ['TELEGRAM_API_FAILED','TELEGRAM_TRANSPORT_FAILED','j?.ok!==true','AbortSignal.timeout(10000)'])assert.ok(telegram.includes(x),`TELEGRAM missing ${x}`);
for(const x of ['CURRENT_RUNTIME_ENV','retry-until-confirmed','lastPositionReconcile'])assert.ok(hub.includes(x),`HUB missing ${x}`);
assert.ok(prep.includes('CRON=NONE_EVENT_DRIVER_ONLY'));assert.ok(!prep.includes("triggers:{crons"));assert.ok(prep.includes('keep_vars:true'));
assert.ok(workflow.includes('validate-only'));assert.ok(workflow.includes('BTC_GITHUB_CI_VALIDATION_ONLY=PASS'));assert.ok(!workflow.includes('npx wrangler deploy'));assert.ok(!workflow.includes("BYBIT_BTC_LIVE_ACK: 'false'"));
for(const oldImport of ['forex-','meme-','binance-','hub-v10','hub-v11','hub-v77','hyro-','signal-v10','multi-ai-control-plane','gpt-5ai-action','bybit-btc-execution-policy','bybit-btc-market-model'])assert.ok(!new RegExp(`from\\s+["'][^"']*${oldImport.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}`,'i').test([index,controller,control,engine,strategy,market].join('\n')),`ACTIVE RUNTIME IMPORT CONFLICT ${oldImport}`);

console.log('BTC_STATEFLOW_VALIDATION=PASS');
console.log(JSON.stringify({version:'BYBIT-BTC-STATEFLOW-2.5',symbol:cfg.symbol,strategyAuthority:BYBIT_AUTO_CONFIG.strategyAuthority,autonomous:true,eventDriven:true,timeGate:false,scheduledExecution:false,entryTriggerAuthority:'VPS_BRIDGE_SECRET_ONLY',singleWorkerDeployAuthority:'CLOUDFLARE_BUILDS',wsMomentumRouting:true,smartQuantizedSizing:true,exchangePositionReconciliation:true,telegramDeliveryConfirmedOnly:true,telegramEntryRetry:true,idempotentTradingStop:true,noMartingale:true,noAddToLoser:true,winnerPyramiding:true},null,2));
