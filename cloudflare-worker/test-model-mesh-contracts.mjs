import assert from 'node:assert/strict';
import {FREE_ONLY_ELIGIBLE_STATUSES,classifyProviderFailure,freeOnlyEligible,sanitizeDataClass,selectionRejection} from './model-mesh/contracts.js';

assert.deepEqual([...FREE_ONLY_ELIGIBLE_STATUSES].sort(),['account_specific','recurring']);
assert.equal(freeOnlyEligible({free_status:'recurring',free_verified_at:'2026-09-15T00:00:00Z'}),true);
assert.equal(freeOnlyEligible({free_status:'account_specific',free_verified_at:'2026-09-15T00:00:00Z'}),true);
for(const status of ['trial_credit','limited_time','unknown','paid','expired']){
  assert.equal(freeOnlyEligible({free_status:status,free_verified_at:'2026-09-15T00:00:00Z'}),false,status);
}
assert.equal(freeOnlyEligible({free_status:'recurring',free_verified_at:null}),false);
assert.equal(sanitizeDataClass(undefined),'PUBLIC');
assert.equal(sanitizeDataClass('SECRETT'),'SECRET');

assert.equal(classifyProviderFailure({status:401}),'AUTH_FAILED');
assert.equal(classifyProviderFailure({status:404}),'MODEL_NOT_FOUND');
assert.equal(classifyProviderFailure({status:429}),'RATE_LIMITED');
assert.equal(classifyProviderFailure({status:402}),'FREE_ENTITLEMENT_INVALID');
assert.equal(classifyProviderFailure({status:400}),'REQUEST_INVALID');
assert.equal(classifyProviderFailure({status:503}),'PROVIDER_5XX');
assert.equal(classifyProviderFailure({code:'TIMEOUT'}),'TIMEOUT');
assert.equal(classifyProviderFailure({code:'PARSE_FAILED'}),'PARSE_FAILED');
assert.equal(classifyProviderFailure({status:451}),'REGION_UNAVAILABLE');
assert.equal(classifyProviderFailure({status:418,detail:'sk-secret-value'}),'UNKNOWN_SANITIZED');

const capabilityModel={
  free_status:'recurring',free_verified_at:'2026-09-15T00:00:00Z',usage_terms:'production_allowed',
  capabilities:{coding:{supported:true,score:0.9}},privacy_class:'public_safe',health:'healthy',
  quota_state:{state:'AVAILABLE'},context_window:131072,capability_evidence:{},
};
assert.equal(selectionRejection(capabilityModel,{requiredCapability:'coding'}),null);
assert.equal(selectionRejection(capabilityModel,{requiredCapability:'coding',hardCapabilityGate:true}),'capability');
assert.equal(selectionRejection({...capabilityModel,capability_evidence:{coding:{state:'PROVISIONAL'}}},{requiredCapability:'coding',hardCapabilityGate:true}),'capability');
assert.equal(selectionRejection({...capabilityModel,capability_evidence:{coding:{state:'VERIFIED'}}},{requiredCapability:'coding',hardCapabilityGate:true}),null);

console.log('model mesh canonical contracts ok');
