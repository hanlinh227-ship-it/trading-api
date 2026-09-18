import assert from 'node:assert/strict';
import {computeAdaptiveTradeGeometry} from './bybit-symbol-strategy.js';

const base={
  price:100,
  regime:'RANGE',
  book:{spreadBps:1},
  range5:{lo:99.75,hi:100.50,width:.75},
  range15:{lo:99.20,hi:100.90,width:1.70},
  structure5:{recentLow:99.88,recentHigh:100.45},
  structure15:{recentLow:99.82,recentHigh:100.48},
  sweep5:{priorLow:99.90,priorHigh:100.40},
};

const buy=computeAdaptiveTradeGeometry('Buy',base,{},'CONFIRM');
assert.equal(buy.ok,true);
assert.ok(buy.structuralInvalidation<100);
assert.ok(buy.sl<buy.structuralInvalidation,'buy stop must sit beyond thesis invalidation, not exactly on the swing');
assert.ok(buy.noiseBuffer>0);
assert.equal(buy.stopAuthority,'STRUCTURE_INVALIDATION_PLUS_VOLATILITY_LIQUIDITY_BUFFER');
assert.ok(buy.rr>=1.05);
assert.equal(buy.targetFrontRun,true);
assert.ok(buy.tp<buy.opposingLiquidity,'range target should front-run opposing liquidity');

const sellState={
  ...base,
  price:100,
  range5:{lo:99.50,hi:100.25,width:.75},
  structure5:{recentLow:99.55,recentHigh:100.12},
  structure15:{recentLow:99.52,recentHigh:100.18},
  sweep5:{priorLow:99.60,priorHigh:100.10},
};
const sell=computeAdaptiveTradeGeometry('Sell',sellState,{},'CONFIRM');
assert.equal(sell.ok,true);
assert.ok(sell.structuralInvalidation>100);
assert.ok(sell.sl>sell.structuralInvalidation,'sell stop must sit beyond thesis invalidation, not exactly on the swing');
assert.ok(sell.rr>=1.05);

// A nearby opposing-liquidity wall that destroys reward/risk must reject the setup
// instead of stretching TP through that wall.
const blocked=computeAdaptiveTradeGeometry('Buy',{
  ...base,
  range5:{lo:99.75,hi:100.14,width:.39},
  structure5:{recentLow:99.90,recentHigh:100.15},
  structure15:{recentLow:99.88,recentHigh:100.16},
  sweep5:{priorLow:99.92,priorHigh:100.13},
}, {}, 'CONFIRM');
assert.equal(blocked.ok,false);
assert.equal(blocked.reason,'OPPOSING_LIQUIDITY_TOO_CLOSE');

// Remote structure must not force a huge scalp stop. Nearby relevant structure
// is selected and remote references are ignored for stop placement.
const remote=computeAdaptiveTradeGeometry('Buy',{
  ...base,
  range5:{lo:97,hi:100.6,width:3.6},
  structure15:{recentLow:97.5,recentHigh:100.7},
  structure5:{recentLow:99.9,recentHigh:100.5},
  sweep5:{priorLow:99.88,priorHigh:100.45},
}, {}, 'CONFIRM');
assert.equal(remote.ok,true);
assert.ok(remote.stopDistance<=remote.maxStopDistance+1e-9);

console.log('BYBIT_STOP_TARGET_GEOMETRY_TEST=PASS');
