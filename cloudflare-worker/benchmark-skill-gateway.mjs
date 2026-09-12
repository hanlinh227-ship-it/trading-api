import {performance} from 'node:perf_hooks';
import {routeSkillRequest} from './skill-gateway.js';
import {SKILL_GATEWAY_SNAPSHOT} from './generated/skill-gateway-snapshot.js';

const samples=[
  'giải thích bác sĩ nội trú',
  'sửa lỗi API này',
  'viết kịch bản quảng cáo giày',
  'so sánh hai phương án này',
  'dịch đoạn này sang tiếng Anh',
  'thiết kế UX UI cho app',
  'prompt video giữ nhân vật không thay đổi',
  'một câu hỏi chung chưa có alias',
];
for(let i=0;i<500;i++)routeSkillRequest({text:samples[i%samples.length]},SKILL_GATEWAY_SNAPSHOT);
const durations=[];
let external=0;
for(let i=0;i<10_000;i++){
  const start=performance.now();
  const route=routeSkillRequest({text:samples[i%samples.length]},SKILL_GATEWAY_SNAPSHOT);
  durations.push(performance.now()-start);
  external+=route.externalRoutingCalls||0;
}
durations.sort((a,b)=>a-b);
const percentile=p=>durations[Math.min(durations.length-1,Math.floor(durations.length*p))];
const p50=percentile(0.50),p95=percentile(0.95);
console.log(`FAST_ROUTE_P50_MS=${p50.toFixed(4)}`);
console.log(`FAST_ROUTE_P95_MS=${p95.toFixed(4)}`);
console.log(`FAST_EXTERNAL_CALLS=${external}`);
if(external!==0)throw new Error('FAST_EXTERNAL_CALLS_MUST_BE_ZERO');
if(p95>25)throw new Error(`FAST_ROUTE_P95_EXCEEDS_TARGET:${p95}`);
