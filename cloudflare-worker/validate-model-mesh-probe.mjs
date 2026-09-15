import {validateProbeCanary} from './model-mesh/canary-policy.js';
import {collectSecretValues,PROVIDER_SECRET_NAMES} from './security/secret-scan.js';

let input='';
for await(const chunk of process.stdin)input+=chunk;
const envelope=JSON.parse(input);
const requireHealthy=process.argv.includes('--require-healthy');
// Match the concrete secret values this job holds, not just credential
// shapes, so a value that leaks without a recognisable prefix is still caught.
const summary=validateProbeCanary(envelope,{requireHealthy,secretValues:collectSecretValues(process.env,PROVIDER_SECRET_NAMES)});
const matrix=envelope.results.map(row=>({providerId:row.providerId,modelId:row.modelId,configured:row.configured,ok:row.ok,status:row.status,state:row.state,category:row.category,latencyMs:row.latencyMs,evidencePersisted:row.evidencePersisted,skipped:row.skipped??null}));
console.log(`MODEL_MESH_PROBE_MATRIX=${JSON.stringify(matrix)}`);
console.log(`MODEL_MESH_PROBE=PASS probed=${envelope.probedProviderCount} configured=${summary.configuredCount} successful=${summary.healthyCount} unavailable=${summary.unavailableCount}`);
