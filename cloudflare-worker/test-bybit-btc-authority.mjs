import assert from 'node:assert/strict';
import {BYBIT_AUTO_CONFIG,bybitAutoConfig,bybitExecutionMode,bybitExecutionAllowsOrders} from './bybit-auto-config.js';
import {handleBybitControlApi} from './bybit-control-plane.js';
import {bybitV5} from './bybit-v5-client.js';
import {BYBIT_RUNTIME_CONTRACT,BYBIT_AUTO_VERSION,LEGACY_BYBIT_MULTI_COIN_DISABLED} from './bybit-runtime-contract.js';
import {BYBIT_TRADE_UNIVERSE,isSupportedTradeSymbol} from './bybit-coin-profiles.js';
import {runBybitSymbolEngine} from './bybit-symbol-engine.js';

const AUTH='BYBIT-TOP100-STATEFLOW-3.0';
const NON_BTC='BYBIT_SYMBOL_OUTSIDE_TOP100_EXECUTION_AUTHORITY';

// Production execution authority is a fail-closed top-100 market-cap USDT-linear universe.
assert.equal(BYBIT_AUTO_VERSION,AUTH);
assert.equal(BYBIT_RUNTIME_CONTRACT.executionAuthority,AUTH);
assert.equal(LEGACY_BYBIT_MULTI_COIN_DISABLED,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.symbol,'DYNAMIC_TOP100');
assert.deepEqual(BYBIT_RUNTIME_CONTRACT.symbols,['DYNAMIC_TOP100_MARKET_CAP_USDT_LINEAR']);
assert.ok(BYBIT_RUNTIME_CONTRACT.coreSymbols.includes('BTCUSDT'));assert.ok(BYBIT_RUNTIME_CONTRACT.coreSymbols.includes('ETHUSDT'));
assert.equal(BYBIT_RUNTIME_CONTRACT.multiAsset,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.allActiveCryptoEligible,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.dynamicBybitScalpUniverse,true);
assert.equal(BYBIT_AUTO_CONFIG.symbol,'BTCUSDT');
assert.deepEqual(BYBIT_AUTO_CONFIG.symbols,['DYNAMIC_TOP100_MARKET_CAP_USDT_LINEAR']);
assert.equal(BYBIT_AUTO_CONFIG.multiAsset,true);
assert.equal(BYBIT_AUTO_CONFIG.aiLegion.authority,'ADVISORY_EVIDENCE_ONLY');
assert.equal(BYBIT_AUTO_CONFIG.aiLegion.mayPlaceOrders,false);
assert.equal(BYBIT_AUTO_CONFIG.aiLegion.mayIncreaseRisk,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.aiLegionVersion,'BYBIT_AI_LEGION_V2_MARKET_INTELLIGENCE');
assert.equal(BYBIT_RUNTIME_CONTRACT.aiLegionMayPlaceOrders,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.demoExecutionSupported,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.vpsRequired,false);
assert.equal(BYBIT_RUNTIME_CONTRACT.cloudNativeMarketStream,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.directBybitRest,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.demoServerlessEgressFallback,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.demoServerlessEgressProvider,'DENO_DEPLOY');
const demoApi=bybitV5({BYBIT_AUTO_DEMO:'true',BYBIT_DEMO_API_KEY:'demo-key',BYBIT_DEMO_API_SECRET:'demo-secret'});
assert.deepEqual(demoApi.bases,['https://api-demo.bybit.com']);
assert.ok(demoApi.publicBases.includes('https://api.bybit.com'));
assert.equal(demoApi.privateTransport,'CLOUDFLARE_BYBIT_DEMO_DIRECT');
assert.equal(demoApi.marketTransport,'CLOUDFLARE_BYBIT_PUBLIC_DIRECT');
assert.equal(BYBIT_RUNTIME_CONTRACT.structureBufferedStops,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.opposingLiquidityTargeting,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.markPriceStopTrigger,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.latencyProfile,'EVENT_DRIVEN_ULTRA_LOW_LATENCY_V1');
assert.equal(BYBIT_RUNTIME_CONTRACT.eventDebounceDefaultMs,150);
assert.equal(BYBIT_RUNTIME_CONTRACT.eventDebounceFloorMs,75);
assert.equal(BYBIT_RUNTIME_CONTRACT.pendingEventCoalescing,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.aiRefreshOffCriticalPath,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.accountReconciliationParallel,true);
assert.equal(BYBIT_RUNTIME_CONTRACT.instrumentMetadataCacheMs,300000);
assert.equal(BYBIT_RUNTIME_CONTRACT.fillPollIntervalMs,80);
assert.equal(BYBIT_RUNTIME_CONTRACT.privateTransport,'CLOUDFLARE_BYBIT_PRIVATE_DIRECT');
assert.equal(bybitExecutionMode({BYBIT_AUTO_DEMO:'true'}),'DEMO');
assert.equal(bybitExecutionAllowsOrders('DEMO'),true);
assert.equal(bybitExecutionMode({BYBIT_AUTO_DEMO:'true',BYBIT_AUTO_LIVE:'true',BYBIT_BTC_LIVE_ACK:'true'}),'BLOCKED');
const hardCeilingAttempt=bybitAutoConfig({BYBIT_BTC_MAX_ACTIVE_RISK_PCT:'12',BYBIT_BTC_MAX_PORTFOLIO_MARGIN_PCT:'150'});
assert.equal(hardCeilingAttempt.risk.maxActiveRiskPct,6);
assert.equal(hardCeilingAttempt.risk.maxPortfolioMarginPct,100);
const tightenAttempt=bybitAutoConfig({BYBIT_BTC_MAX_ACTIVE_RISK_PCT:'3.5',BYBIT_BTC_MAX_PORTFOLIO_MARGIN_PCT:'50'});
assert.equal(tightenAttempt.risk.maxActiveRiskPct,3.5);
assert.equal(tightenAttempt.risk.maxPortfolioMarginPct,50);
assert.ok(BYBIT_AUTO_CONFIG.portfolio.concurrentByEquity.length>=4);

// Broad crypto discovery remains available as read-only/research evidence only.
assert.ok(BYBIT_TRADE_UNIVERSE.includes('BTCUSDT'));
assert.ok(BYBIT_TRADE_UNIVERSE.includes('ETHUSDT'));
assert.equal(isSupportedTradeSymbol('ETHUSDT'),true);

// Symbol authority now permits USDT-linear symbols to reach the dynamic universe gate.
assert.equal(isSupportedTradeSymbol('ETHUSDT'),true);
assert.equal(isSupportedTradeSymbol('SOLUSDT'),true);
assert.equal(isSupportedTradeSymbol('EURUSD'),false);

// UI bootstrap advertises the multi-asset execution family.
const bootstrapResponse=await handleBybitControlApi(new Request('https://local.test/bybit/ui/bootstrap'),{});
assert.equal(bootstrapResponse.status,200);
const bootstrap=await bootstrapResponse.json();
assert.equal(bootstrap.executionAuthority,AUTH);
assert.equal(bootstrap.portfolio.authority,'BYBIT_TOP100_MARKET_CAP_STATEFLOW_PORTFOLIO');
assert.ok(Array.isArray(bootstrap.portfolio.concurrentByEquity));

// Final signed-write primitive accepts syntactically valid USDT-linear symbols;
// top-100/liquidity admission is enforced before the controller reaches signed writes.
const client=bybitV5({});
await assert.rejects(
  ()=>client.order({symbol:'ETHUSDT',side:'Buy',orderType:'Market',qty:'1'}),
  error=>/CREDENTIAL|API_KEY|SECRET|MISSING/i.test(String(error?.message||error))
);
await assert.rejects(
  ()=>client.order({symbol:'EURUSD',side:'Buy',orderType:'Market',qty:'1'}),
  error=>error?.code===NON_BTC||/SYMBOL|INVALID/i.test(String(error?.message||error))
);

const originalFetch=globalThis.fetch;
const fallbackCalls=[];
globalThis.fetch=async (url,options={})=>{
  const href=String(url);
  fallbackCalls.push({href,method:String(options.method||'GET')});
  if(href.startsWith('https://api-demo.bybit.com/')){
    return new Response('blocked',{status:403,headers:{'content-type':'text/plain'}});
  }
  if(href==='https://demo-egress.example/bybit/private-egress'){
    const relay=JSON.parse(String(options.body||'{}'));
    assert.equal(relay.path,'/v5/position/list');
    assert.equal(relay.method,'GET');
    assert.ok(relay.headers['X-BAPI-SIGN']);
    return new Response(JSON.stringify({ok:true,httpStatus:200,upstream:{retCode:0,retMsg:'OK',result:{list:[]}}}),{status:200,headers:{'content-type':'application/json'}});
  }
  throw new Error('unexpected fetch '+href);
};
try{
  const demoFallback=bybitV5({
    BYBIT_AUTO_DEMO:'true',
    BYBIT_DEMO_API_KEY:'demo-key',
    BYBIT_DEMO_API_SECRET:'demo-secret',
    BYBIT_DEMO_EGRESS_URL:'https://demo-egress.example',
    BYBIT_DEMO_EGRESS_SHARED_SECRET:'relay-secret'
  });
  const positions=await demoFallback.positions();
  assert.equal(positions.retCode,0);
  assert.equal(fallbackCalls.some(x=>x.href==='https://demo-egress.example/bybit/private-egress'),true);
}finally{
  globalThis.fetch=originalFetch;
}


const originalFetchTime=globalThis.fetch;
globalThis.fetch=async (url,options={})=>{
  const href=String(url);
  if(href.includes('/v5/market/time'))return new Response('blocked',{status:403,headers:{'content-type':'text/plain'}});
  throw new Error('unexpected fetch '+href);
};
try{
  const demoClock=bybitV5({BYBIT_AUTO_DEMO:'true',BYBIT_DEMO_API_KEY:'demo-key',BYBIT_DEMO_API_SECRET:'demo-secret'});
  const t=await demoClock.serverTime();
  assert.equal(t.retCode,0);
  assert.equal(t.fallback,'EDGE_CLOCK');
  assert.ok(Number(t.time)>0);
}finally{
  globalThis.fetch=originalFetchTime;
}


const originalFetchVpc=globalThis.fetch;
const vpcCalls=[];
globalThis.fetch=async (url,options={})=>{
  const href=String(url);
  if(href.startsWith('https://api-demo.bybit.com/'))return new Response('blocked',{status:403,headers:{'content-type':'text/plain'}});
  if(href==='https://demo-egress.example/bybit/private-egress')return new Response(JSON.stringify({ok:false,error:'bybit_demo_egress_fetch_failed'}),{status:502,headers:{'content-type':'application/json'}});
  throw new Error('unexpected fetch '+href);
};
try{
  const demoVpc=bybitV5({
    BYBIT_AUTO_DEMO:'true',
    BYBIT_DEMO_API_KEY:'demo-key',
    BYBIT_DEMO_API_SECRET:'demo-secret',
    BYBIT_DEMO_EGRESS_URL:'https://demo-egress.example',
    BYBIT_DEMO_EGRESS_SHARED_SECRET:'relay-secret',
    V11_AI_BRIDGE_SECRET:'bridge-secret',
    AI_BRIDGE:{
      fetch:async request=>{
        const relay=await request.json();
        vpcCalls.push(relay);
        assert.equal(relay.base,'https://api-demo.bybit.com');
        assert.equal(relay.path,'/v5/position/list');
        return new Response(JSON.stringify({ok:true,httpStatus:200,upstream:{retCode:0,retMsg:'OK',result:{list:[]}},base:'https://api-demo.bybit.com',attempts:['https://api-demo.bybit.com'],transport:'VPS_BYBIT_PRIVATE_PROXY'}),{status:200,headers:{'content-type':'application/json'}});
      }
    }
  });
  const positions=await demoVpc.positions();
  assert.equal(positions.retCode,0);
  assert.equal(vpcCalls.length,1);
}finally{
  globalThis.fetch=originalFetchVpc;
}

console.log('BYBIT_TOP100_EXECUTION_AUTHORITY_VALIDATION=PASS');
