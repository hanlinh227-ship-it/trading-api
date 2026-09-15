import assert from 'node:assert/strict';
import {validateProbeCanary,validateLiveOverlay} from './model-mesh/canary-policy.js';

const pass={providerId:'groq',modelId:'free-a',configured:true,ok:true,status:200,state:'LIVE_HEALTHY',category:null,latencyMs:12,evidencePersisted:true};
const cooldown={providerId:'mistral',modelId:'free-b',configured:true,ok:false,status:429,state:'COOLDOWN',category:'RATE_LIMITED',latencyMs:15,evidencePersisted:true};
const quarantined={providerId:'gemini_developer_api',modelId:'free-c',configured:true,ok:false,status:404,state:'QUARANTINED',category:'MODEL_NOT_FOUND',latencyMs:17,evidencePersisted:true};
const envelope={ok:true,mode:'FREE_ONLY',routingAuthority:false,reasoningAuthority:false,probedProviderCount:3,successfulProviderCount:1,results:[pass,cooldown,quarantined]};

const summary=validateProbeCanary(envelope,{requireHealthy:true});
assert.equal(summary.configuredCount,3);
assert.equal(summary.healthyCount,1);
assert.equal(summary.unavailableCount,2);
assert.deepEqual(summary.healthyProviderIds,['groq']);
assert.equal(validateLiveOverlay(envelope,{providers:[{providerId:'groq',active:true},{providerId:'mistral',active:false},{providerId:'gemini_developer_api',active:false}]}).activeCount,1);

assert.throws(()=>validateProbeCanary({...envelope,probedProviderCount:1,successfulProviderCount:0,results:[{...pass,ok:false,state:'DEGRADED'}]},{requireHealthy:true}),/no_live_healthy_provider/);
assert.throws(()=>validateProbeCanary({...envelope,probedProviderCount:1,successfulProviderCount:1,results:[{...cooldown,ok:true}]},{requireHealthy:false}),/probe_state_mismatch/);
assert.throws(()=>validateProbeCanary({...envelope,probedProviderCount:1,successfulProviderCount:1,results:[{...pass,evidencePersisted:false}]},{requireHealthy:false}),/probe_evidence_not_persisted/);
assert.throws(()=>validateLiveOverlay(envelope,{providers:[{providerId:'groq',active:true},{providerId:'mistral',active:true}]}),/overlay_active_set_mismatch/);
assert.equal(JSON.stringify(summary).includes('secret'),false);
console.log('model mesh partial-outage canary policy ok');
