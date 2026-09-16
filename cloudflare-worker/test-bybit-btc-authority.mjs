import assert from 'node:assert/strict';
import fs from 'node:fs';
import {BYBIT_AUTO_CONFIG} from './bybit-auto-config.js';
import {BYBIT_RUNTIME_CONTRACT,BYBIT_AUTO_VERSION,BYBIT_EXECUTION_AUTHORITY,LEGACY_BYBIT_MULTI_COIN_DISABLED} from './bybit-runtime-contract.js';
import {BYBIT_TRADE_UNIVERSE,isSupportedTradeSymbol} from './bybit-coin-profiles.js';

const AUTH='BYBIT-BTC-STATEFLOW-2.1';

// Canonical Trading authority is BTCUSDT Linear Perpetual only. These
// assertions intentionally fail against the drifted multi-asset runtime.
assert.equal(BYBIT_EXECUTION_AUTHORITY,AUTH);
assert.equal(BYBIT_AUTO_VERSION,AUTH);
assert.equal(LEGACY_BYBIT_MULTI_COIN_DISABLED,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.executionAuthority,AUTH);
assert.equal(BYBIT_RUNTIME_CONTRACT.symbol,'BTCUSDT');
assert.deepEqual(BYBIT_RUNTIME_CONTRACT.symbols,['BTCUSDT']);
assert.deepEqual(BYBIT_RUNTIME_CONTRACT.coreSymbols,['BTCUSDT']);
assert.equal(BYBIT_RUNTIME_CONTRACT.multiAsset,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.allActiveCryptoEligible,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.dynamicBybitScalpUniverse,false);
assert.deepEqual(BYBIT_TRADE_UNIVERSE,['BTCUSDT']);
assert.equal(BYBIT_AUTO_CONFIG.symbol,'BTCUSDT');
assert.deepEqual(BYBIT_AUTO_CONFIG.symbols,['BTCUSDT']);
assert.equal(BYBIT_AUTO_CONFIG.multiAsset,false);
assert.equal(isSupportedTradeSymbol('BTCUSDT'),true);
assert.equal(isSupportedTradeSymbol('ETHUSDT'),false);
assert.equal(isSupportedTradeSymbol('SOLUSDT'),false);

// Defense in depth: both the public control plane and the symbol engine must
// carry an explicit BTC-only execution guard before any signed V5 order path.
const control=fs.readFileSync('bybit-control-plane.js','utf8');
const engine=fs.readFileSync('bybit-symbol-engine.js','utf8');
assert.match(control,/BYBIT_EXECUTION_SYMBOL/);
assert.match(control,/BYBIT_NON_BTC_EXECUTION_RETIRED/);
assert.match(engine,/BYBIT_EXECUTION_SYMBOL/);
assert.match(engine,/BYBIT_NON_BTC_EXECUTION_RETIRED/);

console.log('BYBIT_BTC_EXECUTION_AUTHORITY_VALIDATION=PASS');
