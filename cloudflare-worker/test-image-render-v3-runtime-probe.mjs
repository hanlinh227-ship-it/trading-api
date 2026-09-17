import assert from 'node:assert/strict';
import {probeImageRuntimes} from './image-render/runtime-probe.js';

// With no binding the probe reports the runtime as absent; it never invents evidence.
let result=await probeImageRuntimes({});
assert.equal(result.ok,true);
const cf=result.providers.find(p=>p.providerId==='cloudflare_workers_ai');
assert.equal(cf.health.ok,false);
assert.equal(cf.health.detail,'workers_ai_binding_unavailable');
assert.equal(cf.runtimeDiscovered.ok,false);

// A working binding yields discovery and health evidence stamped with what was run.
const calls=[];
const env={AI:{async run(model,input){calls.push({model,input});return {image:'ZmFrZQ=='};}}};
result=await probeImageRuntimes(env);
const ok=result.providers.find(p=>p.providerId==='cloudflare_workers_ai');
assert.equal(ok.runtimeDiscovered.ok,true);
assert.equal(ok.health.ok,true);
assert.ok(ok.health.at);
assert.ok(ok.health.detail.includes('@cf/'));
// The probe must be bounded: one tiny generation, not a render of real work.
assert.equal(calls.length,1);
assert.equal(calls[0].input.steps,1,'probe must use the fewest diffusion steps');
assert.equal(calls[0].input.width,undefined,'probe must not send parameters the model rejects');

// A failing runtime is reported as failing, and never advances discovery to health.
const broken={AI:{async run(){throw new Error('nope');}}};
result=await probeImageRuntimes(broken);
const bad=result.providers.find(p=>p.providerId==='cloudflare_workers_ai');
assert.equal(bad.runtimeDiscovered.ok,true,'the binding exists, so the runtime is discovered');
assert.equal(bad.health.ok,false,'but it did not answer, so health is not verified');

// An exhausted free allocation is a wait state, not a health failure to route around.
const exhausted={AI:{async run(){const e=new Error('neurons');e.status=429;throw e;}}};
result=await probeImageRuntimes(exhausted);
const spent=result.providers.find(p=>p.providerId==='cloudflare_workers_ai');
assert.equal(spent.health.ok,false);
assert.equal(spent.health.waitState,'WAITING_FOR_FREE_COMPUTE');
assert.equal(spent.health.paidFallback,false);

// Providers reached over the network are reported as probed by the deployed Worker only.
assert.ok(result.providers.some(p=>p.providerId==='ai_horde'));
assert.equal(result.mode,'FREE_ONLY');
assert.equal(result.paidFallback,false);

console.log('image render v3 runtime probe contracts: PASS');
