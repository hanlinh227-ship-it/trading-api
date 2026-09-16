import assert from 'node:assert/strict';
import {FREE_ONLY_ELIGIBLE_STATUSES,PROVIDER_FAILURE_ACTIONS,REPLACEMENT_DISCOVERY_CATEGORIES,classifyProviderFailure,freeOnlyEligible,sanitizeDataClass,selectionRejection} from './model-mesh/contracts.js';
import {zeroCostRejection} from './model-mesh/zero-cost.js';

assert.deepEqual([...FREE_ONLY_ELIGIBLE_STATUSES].sort(),['account_specific','free_quota_hard_stop','recurring','temporary_zero_price']);
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
// 410 used to fall through to UNKNOWN_SANITIZED, which made a retired model id
// look like an unexplained provider fault instead of a stale id to replace.
assert.equal(classifyProviderFailure({status:410}),'MODEL_GONE');
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

// --- zero-cost eligibility at execution time --------------------------------
// A class label is a claim; the recorded price is evidence. Evidence wins.
const zeroPriced={input_price_per_million:0,output_price_per_million:0};
assert.equal(freeOnlyEligible({free_status:'recurring',free_verified_at:'2026-09-15T00:00:00Z',zero_cost:{...zeroPriced,price_model:'recurring_free'}}),true);
assert.equal(freeOnlyEligible({free_status:'recurring',free_verified_at:'2026-09-15T00:00:00Z',zero_cost:{input_price_per_million:0.5,output_price_per_million:0}}),false,'a price above zero vetoes any class');
assert.equal(freeOnlyEligible({free_status:'recurring',free_verified_at:'2026-09-15T00:00:00Z',zero_cost:{price_model:'paid'}}),false,'a paid price model vetoes any class');

// temporary_zero_price has to re-prove its price on a timer.
const nowMs=Date.parse('2026-09-16T12:00:00Z');
const temporary=priceVerifiedAt=>({free_status:'temporary_zero_price',free_verified_at:'2026-09-15T00:00:00Z',zero_cost:{...zeroPriced,price_model:'temporary_zero_price',price_verified_at:priceVerifiedAt,price_revalidate_after_hours:24}});
assert.equal(freeOnlyEligible(temporary('2026-09-16T06:00:00Z'),{nowMs}),true);
assert.equal(freeOnlyEligible(temporary('2026-09-14T06:00:00Z'),{nowMs}),false,'stale price evidence quarantines the model');
assert.equal(freeOnlyEligible(temporary(null),{nowMs}),false,'no price evidence means no zero-cost proof');
assert.equal(zeroCostRejection(temporary('2026-09-14T06:00:00Z'),{nowMs}),'price_evidence_stale');

// A finite free quota may only run behind a verified hard stop.
const finite=extra=>({free_status:'free_quota_hard_stop',free_verified_at:'2026-09-15T00:00:00Z',zero_cost:{...zeroPriced,price_model:'finite_free_quota',quota_model:'finite',...extra}});
assert.equal(freeOnlyEligible(finite({hard_stop_verified:true})),true);
assert.equal(freeOnlyEligible(finite({hard_stop_verified:false})),false);
assert.equal(zeroCostRejection(finite({hard_stop_verified:false})),'finite_free_quota_without_hard_stop');
assert.equal(zeroCostRejection(finite({hard_stop_verified:true,quota_headroom_ratio:0.05})),'free_quota_below_safety_reserve');
assert.equal(zeroCostRejection(finite({hard_stop_verified:true,quota_headroom_ratio:0.4})),null);
// An account_specific model whose quota is finite gets the same treatment: the
// class it was filed under never buys it past the billable boundary.
assert.equal(freeOnlyEligible({free_status:'account_specific',free_verified_at:'2026-09-15T00:00:00Z',zero_cost:{...zeroPriced,quota_model:'finite',hard_stop_verified:false}}),false);

// The failure table drives fallback, and 402 never becomes a paid retry.
assert.equal(PROVIDER_FAILURE_ACTIONS.FREE_ENTITLEMENT_INVALID,'quarantine_model_and_failover');
assert.equal(PROVIDER_FAILURE_ACTIONS.MODEL_NOT_FOUND,'discover_probe_replacement');
assert.equal(PROVIDER_FAILURE_ACTIONS.MODEL_GONE,'discover_probe_replacement');
assert.equal(PROVIDER_FAILURE_ACTIONS.RATE_LIMITED,'cooldown_and_failover');
assert.equal(PROVIDER_FAILURE_ACTIONS.PROVIDER_5XX,'degrade_and_failover');
assert.deepEqual([...REPLACEMENT_DISCOVERY_CATEGORIES].sort(),['MODEL_GONE','MODEL_NOT_FOUND']);
for(const action of Object.values(PROVIDER_FAILURE_ACTIONS))assert.equal(/paid|purchase|upgrade/.test(action)&&!/no_paid_fallback/.test(action),false,action);

// A zero-cost rejection is a static filter: it removes the model from the pool
// outright rather than leaving it as a temporarily unhealthy candidate.
assert.equal(selectionRejection({...capabilityModel,free_status:'temporary_zero_price',zero_cost:{}},{requiredCapability:'coding'}),'zero_cost');
