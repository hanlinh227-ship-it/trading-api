import assert from 'node:assert/strict';
import {BYBIT_AUTO_CONFIG,bybitAutoConfig,bybitExecutionMode,bybitExecutionAllowsOrders} from './bybit-auto-config.js';
import {handleBybitControlApi} from './bybit-control-plane.js';
import {BYBIT_RUNTIME_CONTRACT,BYBIT_AUTO_VERSION,LEGACY_BYBIT_MULTI_COIN_DISABLED} from './bybit-runtime-contract.js';
import {BYBIT_TRADE_UNIVERSE,isSupportedTradeSymbol} from './bybit-coin-profiles.js';
import {runBybitSymbolEngine} from './bybit-symbol-engine.js';
import {bybitV5} from './bybit-v5-client.js';

const AUTH='BYBIT-BTC-STATEFLOW-2.1';
const NON_BTC='BYBIT_NON_BTC_EXECUTION_RETIRED';

// Production execution authority is BTCUSDT Linear Perpetual only.
assert.equal(BYBIT_AUTO_VERSION,AUTH);
assert.equal(BYBIT_RUNTIME_CONTRACT.executionAuthority,AUTH);
assert.equal(LEGACY_BYBIT_MULTI_COIN_DISABLED,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.symbol,'BTCUSDT');
assert.deepEqual(BYBIT_RUNTIME_CONTRACT.symbols,['BTCUSDT']);
assert.deepEqual(BYBIT_RUNTIME_CONTRACT.coreSymbols,['BTCUSDT']);
assert.equal(BYBIT_RUNTIME_CONTRACT.multiAsset,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.allActiveCryptoEligible,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.dynamicBybitScalpUniverse,false);
assert.equal(BYBIT_AUTO_CONFIG.symbol,'BTCUSDT');
assert.deepEqual(BYBIT_AUTO_CONFIG.symbols,['BTCUSDT']);
assert.equal(BYBIT_AUTO_CONFIG.multiAsset,false);
assert.equal(BYBIT_AUTO_CONFIG.aiLegion.authority,'ADVISORY_EVIDENCE_ONLY');
assert.equal(BYBIT_AUTO_CONFIG.aiLegion.mayPlaceOrders,false);
assert.equal(BYBIT_AUTO_CONFIG.aiLegion.mayIncreaseRisk,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.aiLegionVersion,'BYBIT_AI_LEGION_V1');
assert.equal(BYBIT_RUNTIME_CONTRACT.aiLegionMayPlaceOrders,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.demoExecutionSupported,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.vpsRequired,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.cloudNativeMarketStream,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.directBybitRest,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.privateTransport,'CLOUDFLARE_BYBIT_PRIVATE_DIRECT');
assert.equal(bybitExecutionMode({BYBIT_AUTO_DEMO:'true'}),'DEMO');
assert.equal(bybitExecutionAllowsOrders('DEMO'),true);
assert.equal(bybitExecutionMode({BYBIT_AUTO_DEMO:'true',BYBIT_AUTO_LIVE:'true',BYBIT_BTC_LIVE_ACK:'true'}),'BLOCKED');
const widenAttempt=bybitAutoConfig({BYBIT_BTC_MAX_ACTIVE_RISK_PCT:'12',BYBIT_BTC_MAX_PORTFOLIO_MARGIN_PCT:'85'});
assert.equal(widenAttempt.risk.maxActiveRiskPct,6);
assert.equal(widenAttempt.risk.maxPortfolioMarginPct,65);
const tightenAttempt=bybitAutoConfig({BYBIT_BTC_MAX_ACTIVE_RISK_PCT:'3.5',BYBIT_BTC_MAX_PORTFOLIO_MARGIN_PCT:'50'});
assert.equal(tightenAttempt.risk.maxActiveRiskPct,3.5);
assert.equal(tightenAttempt.risk.maxPortfolioMarginPct,50);
assert.deepEqual(BYBIT_AUTO_CONFIG.portfolio.concurrentByEquity,[{equityUsd:0,max:1}]);

// Broad crypto discovery remains available as read-only/research evidence only.
assert.ok(BYBIT_TRADE_UNIVERSE.includes('BTCUSDT'));
assert.ok(BYBIT_TRADE_UNIVERSE.includes('ETHUSDT'));
assert.equal(isSupportedTradeSymbol('ETHUSDT'),true);

// Engine guard must reject non-BTC before any exchange/network dependency is touched.
const blockedEngine=await runBybitSymbolEngine({}, {symbol:'ETHUSDT'});
assert.equal(blockedEngine.executed,false);
assert.equal(blockedEngine.mode,'BLOCKED');
assert.equal(blockedEngine.reason,NON_BTC);
assert.equal(blockedEngine.symbol,'ETHUSDT');

// HTTP execution route must reject non-BTC before calling the execution engine.
const blockedResponse=await handleBybitControlApi(new Request('https://local.test/bybit/auto/run',{
  method:'POST',
  headers:{authorization:'Bearer bridge-secret','x-bybit-symbol':'ETHUSDT'}
}),{V11_AI_BRIDGE_SECRET:'bridge-secret',BYBIT_AUTO_ENABLED:'true'});
assert.equal(blockedResponse.status,409);
const blockedBody=await blockedResponse.json();
assert.equal(blockedBody.reason,NON_BTC);
assert.equal(blockedBody.symbol,'ETHUSDT');

// UI bootstrap describes the execution lane, not the broad research universe.
const bootstrapResponse=await handleBybitControlApi(new Request('https://local.test/bybit/ui/bootstrap'),{});
assert.equal(bootstrapResponse.status,200);
const bootstrap=await bootstrapResponse.json();
assert.deepEqual(bootstrap.coreUniverse,['BTCUSDT']);
assert.equal(bootstrap.portfolio.authority,'BYBIT_BTC_STATEFLOW_SINGLE_EXECUTION_UNIVERSE');
assert.deepEqual(bootstrap.portfolio.concurrentByEquity,[{equityUsd:0,max:1}]);

// Final signed-write barrier: research symbols from every non-BTC domain must fail before credentials/network.
const client=bybitV5({});
for(const symbol of ['ETHUSDT','SOLUSDT','EURUSD','NQ','GC']){
  await assert.rejects(
    ()=>client.order({symbol,side:'Buy',orderType:'Market',qty:'1'}),
    error=>error?.code===NON_BTC&&error?.symbol===symbol
  );
}
await assert.rejects(
  ()=>client.signed('POST','/v5/order/create',{category:'linear',symbol:'SOLUSDT',side:'Buy',orderType:'Market',qty:'1'}),
  error=>error?.code===NON_BTC&&error?.symbol==='SOLUSDT'
);

console.log('BYBIT_BTC_EXECUTION_AUTHORITY_VALIDATION=PASS');
