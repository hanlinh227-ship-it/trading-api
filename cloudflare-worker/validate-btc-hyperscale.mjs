import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {BYBIT_AUTO_CONFIG,bybitAutoConfig,bybitExecutionMode} from './bybit-auto-config.js';
import {drawdownState,btcRiskDecision,activeRiskUsd} from './bybit-btc-risk-engine.js';
import {selectBtcSetup} from './bybit-btc-strategy.js';

const root=process.cwd();
const read=f=>fs.readFileSync(path.join(root,f),'utf8');
const required=[
  'index.js','bybit-runtime-contract.js','bybit-auto-config.js','bybit-auto-v1.js','bybit-auto-controller.js','bybit-auto-hub.js','bybit-control-plane.js','bybit-readonly-health.js','bybit-v5-client.js',
  'bybit-btc-market-state.js','bybit-btc-strategy.js','bybit-btc-risk-engine.js','bybit-btc-engine.js','providers/bybit-signed-client.js','providers/telegram-client.js'
];
for(const f of required)assert.ok(fs.existsSync(path.join(root,f)),`MISSING ${f}`);

const cfg=bybitAutoConfig({});
assert.equal(cfg.symbol,'BTCUSDT');
assert.equal(cfg.category,'linear');
assert.equal(cfg.risk.martingale,false);
assert.equal(cfg.risk.gridRescue,false);
assert.equal(cfg.risk.addToLoser,false);
assert.equal(cfg.risk.pyramidWinner,true);
assert.equal(cfg.risk.dailyTarget,false);
assert.equal(cfg.scan.hardDailyTradeQuota,false);
assert.ok(cfg.maxTradesPerDay>=1_000_000_000);
assert.ok(cfg.risk.maxActiveRiskPct<=8);
assert.ok(cfg.risk.absoluteSingleEntryRiskPct<=1.5);
assert.ok(cfg.risk.maxPortfolioMarginPct<=65);
assert.ok(cfg.risk.minFreeReservePct>=25);
assert.equal(bybitExecutionMode({BYBIT_AUTO_LIVE:'true'}),'PAPER','LIVE must require BTC acknowledgement');
assert.equal(bybitExecutionMode({BYBIT_AUTO_LIVE:'true',BYBIT_BTC_LIVE_ACK:'true'}),'LIVE');

const dd5=drawdownState({equityUsd:95,highWaterUsd:100,cfg});
const dd10=drawdownState({equityUsd:90,highWaterUsd:100,cfg});
const dd15=drawdownState({equityUsd:85,highWaterUsd:100,cfg});
const dd20=drawdownState({equityUsd:80,highWaterUsd:100,cfg});
assert.equal(dd5.multiplier,.8);
assert.equal(dd10.multiplier,.55);
assert.equal(dd15.multiplier,.3);
assert.equal(dd20.multiplier,0);
assert.equal(dd20.newRiskLocked,true);

const setup={side:'Buy',strength:'NORMAL',entry:101,sl:100,tp:103,rr:2,setup:'TEST',regime:'TREND_UP'};
let r=btcRiskDecision({cfg,equityUsd:100,state:{highWaterUsd:100,tranches:[{id:'L1',status:'OPEN',side:'Buy',qty:1,entry:100,sl:99,managedSl:99,initialRiskUsd:1,createdAt:1}]},setup,markPrice:99});
assert.equal(r.ok,false);
assert.equal(r.reason,'NO_ADD_TO_LOSER');

r=btcRiskDecision({cfg,equityUsd:100,state:{highWaterUsd:125,tranches:[]},setup,markPrice:101});
assert.equal(r.ok,false);
assert.equal(r.reason,'DRAWDOWN_NEW_RISK_LOCK');

const riskHeavy=[
  {id:'OLD',status:'OPEN',side:'Buy',qty:1,entry:100,sl:94,managedSl:94,initialRiskUsd:6,createdAt:1},
  {id:'NEW',status:'OPEN',side:'Buy',qty:1,entry:100,sl:100.1,managedSl:100.1,initialRiskUsd:1,createdAt:2}
];
assert.ok(activeRiskUsd(riskHeavy)>=6-1e-9);
r=btcRiskDecision({cfg,equityUsd:100,state:{highWaterUsd:100,tranches:riskHeavy},setup,markPrice:101});
assert.equal(r.ok,false);
assert.equal(r.reason,'ACTIVE_RISK_BUDGET_EXHAUSTED');

const protectedWinner=[{id:'P',status:'OPEN',side:'Buy',qty:1,entry:100,sl:100.1,managedSl:100.1,initialRiskUsd:1,createdAt:2}];
r=btcRiskDecision({cfg,equityUsd:100,state:{highWaterUsd:100,tranches:protectedWinner},setup,markPrice:101});
assert.equal(r.ok,true,'Protected winner must be eligible for a fresh risk-budgeted pyramid');

const noEntry=selectBtcSetup({quality:{freshBook:true,spreadOk:true},regime:'HIGH_VOL_SHOCK',trades:{aggressorImbalance:.9},book:{imbalance:.9},openInterest:{deltaPct:1},direction5:1,direction15:1,direction60:1,efficiency15:.9,crowding:{}});
assert.equal(noEntry.ok,false);
assert.equal(noEntry.reason,'HIGH_VOL_SHOCK_NO_NEW_RISK');

const index=read('index.js');
assert.ok(index.includes('runBybitAutoControlled'));
assert.ok(index.includes('BTCUSDT'));
assert.ok(index.includes('legacyBotsDisabled:true'));
for(const oldImport of ['forex-','meme-','binance-','hub-v10','hub-v11','hub-v77','hyro-','signal-v10','multi-ai-control-plane','gpt-5ai-action']){
  assert.ok(!new RegExp(`from\\s+["'][^"']*${oldImport.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}`, 'i').test(index),`OLD RUNTIME IMPORT ${oldImport}`);
}
const runtime=read('bybit-runtime-contract.js');
assert.ok(runtime.includes('BYBIT_BTC_ONLY'));
assert.ok(runtime.includes('LEGACY_BYBIT_MULTI_COIN_DISABLED=true'));
const engine=read('bybit-btc-engine.js');
for(const x of ['BTCUSDT','BTC_LIVE_ACK_REQUIRED_PAPER_SIGNAL','BTC_NATIVE_STOP_VERIFICATION_FAILED_EMERGENCY_FLAT','reduceOnly:true','STRUCTURE_FLOW_INVALIDATION'])assert.ok(engine.includes(x),`ENGINE missing ${x}`);
const strategy=read('bybit-btc-strategy.js');
for(const x of ['BREAKOUT_RETEST','TREND_PULLBACK_LIQUIDITY_RECLAIM','RANGE_SELLSIDE_SWEEP_ABSORPTION','NO_NON_INDICATOR_EDGE'])assert.ok(strategy.includes(x),`STRATEGY missing ${x}`);
const market=read('bybit-btc-market-state.js');
for(const x of ['/v5/market/orderbook','/v5/market/recent-trade','/v5/market/open-interest','/v5/market/account-ratio','fundingRate','microprice'])assert.ok(market.includes(x),`MARKET STATE missing ${x}`);

console.log('BTC_HYPERSCALE_VALIDATION=PASS');
console.log(JSON.stringify({symbol:cfg.symbol,strategyAuthority:BYBIT_AUTO_CONFIG.strategyAuthority,singleRiskMaxPct:cfg.risk.absoluteSingleEntryRiskPct,activeRiskPct:cfg.risk.maxActiveRiskPct,temporaryAPlusRiskPct:cfg.risk.temporaryAPlusActiveRiskPct,marginCapPct:cfg.risk.maxPortfolioMarginPct,liveRequiresBtcAck:true,noMartingale:true,noAddToLoser:true,winnerPyramiding:true},null,2));
