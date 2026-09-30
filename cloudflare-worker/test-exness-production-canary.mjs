import assert from 'node:assert/strict';
import {runExnessProductionCanary} from './validate-exness-production-canary.mjs';

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
