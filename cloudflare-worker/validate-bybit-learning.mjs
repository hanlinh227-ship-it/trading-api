import assert from 'node:assert/strict';
import {recordBybitLearningEvent,getBybitLearningState} from './bybit-learning-engine.js';

class KV{
  constructor(){this.m=new Map();}
  async get(k,opt){const v=this.m.get(k);if(v===undefined)return null;return opt?.type==='json'?JSON.parse(v):v;}
  async put(k,v){this.m.set(k,String(v));}
}
const env={TRADING_STATE:new KV()};
const base={stage:'OUTCOME',mode:'LIVE',symbol:'BTCUSDT',side:'Buy',strategy:'TEST:RANGE',riskUsd:5,ai:{verdicts:{claude:'PASS',codex:'PASS',deepseek:'PASS'}}};

await recordBybitLearningEvent(env,{...base,id:'win',outcome:{status:'WIN',authority:'BYBIT_CLOSED_PNL',netPnlUsd:5,netR:1,rMultiple:1.1,feesUsd:.5}});
await recordBybitLearningEvent(env,{...base,id:'loss',outcome:{status:'LOSS',authority:'BYBIT_CLOSED_PNL',netPnlUsd:-2.5,netR:-.5,rMultiple:-.4,feesUsd:.5}});
await recordBybitLearningEvent(env,{...base,id:'be',outcome:{status:'BREAKEVEN',authority:'BYBIT_CLOSED_PNL',netPnlUsd:0,netR:0,rMultiple:.1,feesUsd:.5}});
await recordBybitLearningEvent(env,{...base,id:'invalid-null',outcome:{status:'UNKNOWN',authority:'BROKEN',netPnlUsd:null,netR:null,rMultiple:null,feesUsd:null}});
let s=await getBybitLearningState(env);
assert.equal(s.summary.sampleSize,3,'only valid net outcomes count');
assert.equal(s.summary.wins,1);
assert.equal(s.summary.losses,1);
assert.equal(s.summary.breakevens,1);
assert.equal(s.summary.netWinRate,1/3);
assert.equal(s.summary.adaptiveLearning.nullSafe,true);
assert.ok(s.quarantineCount>=1,'invalid null outcome must be quarantined');
assert.ok(!s.recentEvents.some(e=>e.id==='invalid-null'),'quarantined outcome must not appear in canonical history');

await recordBybitLearningEvent(env,{...base,id:'win',outcome:{status:'LOSS',authority:'BYBIT_CLOSED_PNL',netPnlUsd:-5,netR:-1,rMultiple:-.9,feesUsd:.5}});
s=await getBybitLearningState(env);
assert.equal(s.summary.sampleSize,3,'idempotent outcome replacement must not duplicate trade');
assert.equal(s.summary.wins,0);
assert.equal(s.summary.losses,2);
assert.equal(s.summary.breakevens,1);

console.log('BYBIT_LEARNING_INTEGRITY=PASS null-safe canonical W/L/BE + quarantine + idempotency');
