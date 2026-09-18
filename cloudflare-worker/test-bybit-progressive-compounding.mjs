import assert from 'node:assert/strict';
import {BYBIT_AUTO_CONFIG} from './bybit-auto-config.js';
import {drawdownState,equityScaleState,capitalBaseState} from './bybit-btc-risk-engine.js';

const cfg=BYBIT_AUTO_CONFIG;

const s39=equityScaleState(39,cfg);
const s150=equityScaleState(150,cfg);
const s500=equityScaleState(500,cfg);
const s2500=equityScaleState(2500,cfg);
const s25000=equityScaleState(25000,cfg);

assert.equal(s39.riskMult,.75);
assert.equal(s150.riskMult,1);
assert.equal(s500.riskMult,1.10);
assert.equal(s2500.riskMult,1.22);
assert.equal(s25000.riskMult,1.35);
assert.ok(s39.riskMult<s150.riskMult);
assert.ok(s150.riskMult<s500.riskMult);
assert.ok(s500.riskMult<s2500.riskMult);
assert.ok(s2500.riskMult<=s25000.riskMult);
assert.equal(s25000.marginCapPct,100);
assert.equal(cfg.risk.maxPortfolioMarginPct,100);
assert.equal(cfg.risk.maxMarginPerPositionPct,100);
assert.equal(cfg.risk.minFreeReservePct,0);
assert.equal(cfg.risk.dailyTarget,false);
assert.equal(cfg.risk.dailyLossLimit,false);
assert.equal(cfg.risk.dailyMaxProfit,false);
assert.equal(cfg.risk.dailyMaxLoss,false);
assert.equal(cfg.risk.maxDailyTrades,null);
assert.equal(cfg.scan.hardDailyTradeQuota,false);
assert.equal(cfg.scan.entryQuotaPerDay,null);

const d0=drawdownState({equityUsd:1000,highWaterUsd:1000,cfg});
const d2=drawdownState({equityUsd:980,highWaterUsd:1000,cfg});
const d5=drawdownState({equityUsd:950,highWaterUsd:1000,cfg});
const d8=drawdownState({equityUsd:920,highWaterUsd:1000,cfg});
const d10=drawdownState({equityUsd:900,highWaterUsd:1000,cfg});
const d15=drawdownState({equityUsd:850,highWaterUsd:1000,cfg});
const d20=drawdownState({equityUsd:800,highWaterUsd:1000,cfg});

assert.equal(d0.multiplier,1);
assert.equal(d2.multiplier,.92);
assert.equal(d5.multiplier,.80);
assert.equal(d8.multiplier,.65);
assert.equal(d10.multiplier,.55);
assert.equal(d15.multiplier,.30);
assert.equal(d20.multiplier,0);
assert.equal(d20.newRiskLocked,true);

const capProfit=capitalBaseState({equityUsd:1200,walletBalanceUsd:1000,cfg});
assert.equal(capProfit.creditPct,25);
assert.equal(capProfit.capitalBaseUsd,1050);

const capLoss=capitalBaseState({equityUsd:900,walletBalanceUsd:1000,cfg});
assert.equal(capLoss.capitalBaseUsd,900);
assert.equal(capLoss.creditPct,0);

// Dollar risk compounds even before the percentage multiplier increases.
const normalPct=cfg.risk.baseEntryRiskPct;
const riskAt150=150*normalPct*s150.riskMult/100;
const riskAt500=500*normalPct*s500.riskMult/100;
const riskAt2500=2500*normalPct*s2500.riskMult/100;
assert.ok(riskAt150<riskAt500);
assert.ok(riskAt500<riskAt2500);

// Drawdown contracts risk from both a lower equity base and the DD multiplier.
const healthyRisk=1000*normalPct*equityScaleState(1000,cfg).riskMult/100;
const ddRisk=900*normalPct*equityScaleState(900,cfg).riskMult*d10.multiplier/100;
assert.ok(ddRisk<healthyRisk);

console.log('BYBIT_PROGRESSIVE_COMPOUNDING_RISK_TEST=PASS');
