import assert from 'node:assert/strict';
import {evaluateModelPromotion,evaluateModelRegression,recordBenchmarkResult} from './image-render/benchmark-registry.js';

let state={models:{}};
for(let i=0;i<10;i+=1){
  state=recordBenchmarkResult(state,{modelKey:'p::m',taskType:'TEXT_TO_IMAGE',score:92,verified:true});
  state=recordBenchmarkResult(state,{modelKey:'p::m',taskType:'CHARACTER_CONSISTENCY',score:72,verified:true});
}
// Passing the benchmark thresholds now lands at BENCHMARKED, not ACTIVE: the policy and
// runtime gate (evaluatePromotionGate) decides ACTIVE, so no model goes live on scores alone.
// The full gate matrix is covered by test-image-render-v4-promotion-gate.mjs.
let promotion=evaluateModelPromotion(state,{modelKey:'p::m',taskType:'TEXT_TO_IMAGE',minSamples:8,minAverage:85,minVerifiedRate:0.8});
assert.equal(promotion.status,'BENCHMARKED');
assert.equal(promotion.gate.ok,false);
promotion=evaluateModelPromotion(state,{modelKey:'p::m',taskType:'CHARACTER_CONSISTENCY',minSamples:8,minAverage:85,minVerifiedRate:0.8});
assert.equal(promotion.status,'CANDIDATE');

for(let i=0;i<5;i+=1)state=recordBenchmarkResult(state,{modelKey:'p::m',taskType:'TEXT_TO_IMAGE',score:40,verified:false});
const regression=evaluateModelRegression(state,{modelKey:'p::m',taskType:'TEXT_TO_IMAGE',window:5,minAverage:70,minVerifiedRate:0.6});
assert.equal(regression.status,'DEGRADED');

const insufficient=evaluateModelPromotion({models:{}},{modelKey:'unknown',taskType:'TEXT_TO_IMAGE',minSamples:8});
assert.equal(insufficient.status,'CANDIDATE');
assert.equal(insufficient.reason,'insufficient_benchmark_evidence');

console.log('image render v4 benchmark registry contracts: PASS');
