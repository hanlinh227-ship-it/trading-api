import assert from 'node:assert/strict';
import {runExnessProductionCanary,observeExnessBatch} from './validate-exness-production-canary.mjs';

const validQuote={ok:true,exchange:'EXNESS',readOnly:true,instrument:'XAUUSD',bid:2000,ask:2001,sourceTimestamp:new Date().toISOString(),receivedAt:new Date().toISOString(),source:'EXNESS_WEBSOCKET_TICKS'};
let calls=[];
const fetchImpl=async(url,init)=>{
  calls.push({url:String(url),method:init.method,headers:init.headers});
  return calls.length===1
    ?new Response(JSON.stringify({ok:true,exchange:'EXNESS',readOnly:true,instruments:['XAUUSD','EURUSD']}),{status:200})
    :new Response(JSON.stringify(validQuote),{status:200});
};
const result=await runExnessProductionCanary({fetchImpl});
assert.equal(result.instrument,'XAUUSD');
assert.equal(calls.length,2);
assert.ok(calls.every(x=>x.method==='GET'&&x.headers===undefined),'the Exness read-only canary must not require or send a gateway action key');
assert.match(calls[1].url,/instrument=XAUUSD$/);
await assert.rejects(runExnessProductionCanary({fetchImpl,baseUrl:'https://example.com'}),/WORKER_ORIGIN_INVALID/);
console.log('exness production read-only E2E canary contract ok');

await assert.rejects(
  runExnessProductionCanary({fetchImpl:async()=>new Response(JSON.stringify({ok:false,error:'EXNESS_RUNTIME_CONFIGURATION_MISSING'}),{status:503})}),
  /INSTRUMENTS_HTTP_503_EXNESS_RUNTIME_CONFIGURATION_MISSING/
);

{
  // The batch observation is advisory: it reports, and never throws, whatever the route returns.
  const ok=await observeExnessBatch({fetchImpl:async()=>new Response(JSON.stringify({ok:true,exchange:'EXNESS',state:'PARTIAL',quotes:{EURUSD:{state:'LIVE',bid:1.1,ask:1.1002,quoteAgeMs:420},GBPUSD:{state:'LIVE',bid:1.3,ask:1.3001,quoteAgeMs:900},USDJPY:{state:'STALE',reason:'TICK_OLD',quoteAgeMs:9000}}}),{status:200})});
  assert.deepEqual(ok,{http:200,state:'PARTIAL',pairs:3,live:2,maxAgeMs:900,valid:true});
  const leaked=await observeExnessBatch({fetchImpl:async()=>new Response(JSON.stringify({ok:true,exchange:'EXNESS',state:'PARTIAL',quotes:{EURUSD:{state:'LIVE',bid:1.1,ask:1.1002,quoteAgeMs:1},USDJPY:{state:'STALE',bid:150,ask:150.1}}}),{status:200})});
  assert.equal(leaked.valid,false,'a stale pair carrying a price is invalid');
  const closed=await observeExnessBatch({fetchImpl:async()=>new Response(JSON.stringify({ok:false,error:'EXNESS_TICK_STALE',state:'STALE',quotes:{EURUSD:{state:'STALE'}}}),{status:503})});
  assert.equal(closed.http,503);assert.equal(closed.live,0);assert.equal(closed.valid,false);
  const down=await observeExnessBatch({fetchImpl:async()=>{throw new Error('network');}});
  assert.equal(down.state,'UNREACHABLE');
  assert.equal((await observeExnessBatch({fetchImpl:async()=>{throw new Error('must not be called');},baseUrl:'https://example.com'})).state,'ORIGIN_INVALID');
  console.log('exness batch observation contract ok');
}
