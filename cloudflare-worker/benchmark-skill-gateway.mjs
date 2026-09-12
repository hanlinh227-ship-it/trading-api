import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';
import {routeSkillRequest} from './skill-gateway.js';
import {SKILL_GATEWAY_SNAPSHOT} from './generated/skill-gateway-snapshot.js';

const inputs=[
  'giải thích bác sĩ nội trú',
  'tóm tắt nội dung này',
  'dịch đoạn văn này',
  'viết quảng cáo giày cho khách hàng',
  'compare two simple ideas',
  'explain this concept',
];
let externalCalls=0;
const originalFetch=globalThis.fetch;
globalThis.fetch=()=>{externalCalls+=1;throw new Error('BENCHMARK_ROUTER_NETWORK_CALL');};
try{
  for(let i=0;i<200;i++)routeSkillRequest({text:inputs[i%inputs.length]},SKILL_GATEWAY_SNAPSHOT);
  const samples=[];
  for(let i=0;i<10_000;i++){
    const start=performance.now();
    const route=routeSkillRequest({text:inputs[i%inputs.length]},SKILL_GATEWAY_SNAPSHOT);
    samples.push(performance.now()-start);
    assert.equal(route.externalRoutingCalls,0);
    assert.ok(route.primarySkill);
    assert.ok(route.capsuleHash);
  }
  samples.sort((a,b)=>a-b);
  const percentile=p=>samples[Math.min(samples.length-1,Math.floor(samples.length*p))];
  const p50=percentile(.50),p95=percentile(.95);
  assert.equal(externalCalls,0);
  console.log(`FAST_ROUTE_P50_MS=${p50.toFixed(4)}`);
  console.log(`FAST_ROUTE_P95_MS=${p95.toFixed(4)}`);
  console.log(`FAST_EXTERNAL_CALLS=${externalCalls}`);
  console.log(`FAST_P95_TARGET_MS=25`);
  console.log(`FAST_P95_TARGET_MET=${p95<=25}`);
} finally {
  globalThis.fetch=originalFetch;
}
