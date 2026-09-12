import assert from 'node:assert/strict';
import {createResearchGatewayHandler} from './research-gateway.js';

const degradedResult={ok:false,degraded:true,error:'provider_bridge_fetch_failed'};
const fallbackResult={
  ok:true,
  executionQuote:{
    executionVerified:true,
    status:'OK',
    venue:'bybit',
    instrument:'perpetual',
    side:'LONG',
    bid:100,
    ask:101,
    executablePrice:101,
    quoteAgeMs:25,
  },
};

function runtimeFor(result){
  return {
    getLastProbeAt:()=>1,
    getHealth:()=>({bybit:{ok:false}}),
    probeAll:async()=>{},
    runMarket:async()=>result,
  };
}

let fallbackCalls=0;
const fallbackFetch=async(url,options)=>{
  fallbackCalls+=1;
  assert.equal(url,'https://crypto-research-gateway-prod-production.up.railway.app/research/market');
  assert.equal(options.method,'POST');
  const payload=JSON.parse(options.body);
  assert.equal(payload.executionVenue,'bybit');
  return new Response(JSON.stringify(fallbackResult),{status:200,headers:{'content-type':'application/json'}});
};

const handler=createResearchGatewayHandler({runtime:runtimeFor(degradedResult),now:()=>2,fallbackFetch});
const response=await handler(new Request('https://worker.example/research/market',{
  method:'POST',
  headers:{'content-type':'application/json'},
  body:JSON.stringify({action:'execution_quote',symbol:'BTCUSDT',instrument:'perpetual',side:'LONG',executionVenue:'bybit'}),
}),{});
assert.equal(response.status,200);
const body=await response.json();
assert.equal(body.ok,true);
assert.equal(body.executionQuote.venue,'bybit');
assert.equal(body.edgeRuntimeProvider,'cloudflare-workers');
assert.equal(body.upstreamFallback,'railway');
assert.equal(fallbackCalls,1);

fallbackCalls=0;
const direct={...fallbackResult};
const directHandler=createResearchGatewayHandler({runtime:runtimeFor(direct),now:()=>2,fallbackFetch});
const directResponse=await directHandler(new Request('https://worker.example/research/market',{
  method:'POST',
  headers:{'content-type':'application/json'},
  body:JSON.stringify({action:'execution_quote',symbol:'BTCUSDT',instrument:'perpetual',side:'LONG',executionVenue:'bybit'}),
}),{});
assert.equal(directResponse.status,200);
assert.equal(fallbackCalls,0);

fallbackCalls=0;
const binanceHandler=createResearchGatewayHandler({runtime:runtimeFor(degradedResult),now:()=>2,fallbackFetch});
const binanceResponse=await binanceHandler(new Request('https://worker.example/research/market',{
  method:'POST',
  headers:{'content-type':'application/json'},
  body:JSON.stringify({action:'execution_quote',symbol:'BTCUSDT',instrument:'perpetual',side:'LONG',executionVenue:'binance'}),
}),{});
assert.equal(binanceResponse.status,503);
assert.equal(fallbackCalls,0);

console.log('CLOUDFLARE_RESEARCH_FAILOVER_TESTS=PASS');
