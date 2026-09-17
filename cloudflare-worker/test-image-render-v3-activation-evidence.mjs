import assert from 'node:assert/strict';
import {buildStaticActivationEvidence} from './image-render/activation-evidence.js';
import {getProviderAdapter} from './image-render/provider-adapter-registry.js';
import {getModelVaultEntry} from './image-render/model-vault.js';

const cf=getProviderAdapter('cloudflare_workers_ai');
const flux=getModelVaultEntry('flux-1-schnell');
let evidence=buildStaticActivationEvidence({model:flux,adapter:cf,taskType:'TEXT_TO_IMAGE',at:'2026-09-17T00:00:00Z'});
assert.equal(evidence.license.ok,true);
assert.equal(evidence.privacy.ok,true);
assert.match(evidence.license.source,/^https:\/\//);
assert.match(evidence.privacy.source,/^https:\/\//);

const ref=getModelVaultEntry('stable-diffusion-v1-5-img2img');
evidence=buildStaticActivationEvidence({model:ref,adapter:cf,taskType:'REFERENCE_GENERATION'});
assert.equal(evidence.license.ok,true);
assert.equal(evidence.privacy.ok,true,'reference task needs a verified reference-safe provider policy');

const horde=getProviderAdapter('ai_horde');
evidence=buildStaticActivationEvidence({model:ref,adapter:horde,taskType:'REFERENCE_GENERATION'});
assert.equal(evidence.privacy.ok,false,'PUBLIC volunteer compute can never satisfy reference privacy evidence');

console.log('image render v3 activation evidence contracts: PASS');
