// Zero-cost routing: a mixed catalog, a price that moves, and a finite quota.
//
// FREE_ONLY means zero monetary cost at execution time, not that a provider is
// permanently free. These tests cover the cases that a provider-level verdict
// gets wrong: a catalog holding paid and free models at once, a model that was
// free yesterday and is not today, and an allowance that runs out.
import assert from 'node:assert/strict';
import {selectModelWorkers} from './model-mesh/selector.js';
import {zeroCostRejection} from './model-mesh/zero-cost.js';
import {freeOnlyEligible,selectionRejection} from './model-mesh/contracts.js';
import {FREE_ONLY_POLICY} from './generated/free-only-policy.js';

const base={free_verified_at:'2026-09-15T00:00:00Z',usage_terms:'production_allowed',privacy_class:'public_safe',health:'healthy',context_window:131072,quota_state:{state:'AVAILABLE'},capabilities:{text_reasoning:{supported:true,score:0.8}},quality_scores:{},capability_evidence:{}};
const zen=(id,{input=0,output=0,priceVerifiedAt='2026-09-16T11:00:00Z'}={})=>({...base,provider_id:'opencode_zen',model_id:id,model_family:id,free_status:'temporary_zero_price',zero_cost:{price_model:input>0||output>0?'paid':'temporary_zero_price',input_price_per_million:input,output_price_per_million:output,price_verified_at:priceVerifiedAt,price_revalidate_after_hours:24,quota_model:'unknown',hard_stop_verified:false,quota_headroom_ratio:null,evidence:['https://opencode.ai/zen/v1/models']}});
const nowMs=Date.parse('2026-09-16T12:00:00Z');

// --- the policy itself may never admit a billable class --------------------
assert.equal(FREE_ONLY_POLICY.schema_version,2);
assert.deepEqual([...FREE_ONLY_POLICY.eligible_statuses].sort(),['account_specific','free_quota_hard_stop','recurring','temporary_zero_price']);
for(const billable of ['paid','trial_credit','limited_time','expired','unknown'])assert.equal(FREE_ONLY_POLICY.eligible_statuses.includes(billable),false,billable);
assert.equal(FREE_ONLY_POLICY.requirements.auto_purchase_forbidden,true);
assert.equal(FREE_ONLY_POLICY.requirements.paid_fallback_forbidden,true);
assert.equal(FREE_ONLY_POLICY.model_level_eligibility.provider_blacklist_on_single_model_failure,false);

// --- mixed catalog: the paid models are rejected, the free ones are kept ----
{
  const models=[zen('big-pickle'),zen('premium-opus',{input:15,output:75}),zen('mimo-v2.5-free'),zen('premium-mini',{input:0.4,output:1.6})];
  const selected=selectModelWorkers({profile:'DEEP',domain:'core',models,nowMs});
  const ids=selected.map(row=>row.model_id).sort();
  assert.deepEqual(ids,['big-pickle','mimo-v2.5-free'],'a paid sibling never disqualifies the free models, and never sneaks in');
  for(const paid of ['premium-opus','premium-mini'])assert.equal(freeOnlyEligible(models.find(row=>row.model_id===paid),{nowMs}),false,paid);
}

// --- a model that stops being free is quarantined before the next request ---
{
  const stillFree=zen('ling-3.0-flash-fin-free');
  assert.equal(freeOnlyEligible(stillFree,{nowMs}),true);
  const nowPaid={...stillFree,zero_cost:{...stillFree.zero_cost,price_model:'paid',input_price_per_million:0.2}};
  assert.equal(zeroCostRejection(nowPaid,{nowMs}),'price_model_not_zero_cost');
  // And the survivor is what the planner falls over to, in the same round.
  const selected=selectModelWorkers({profile:'STANDARD',domain:'core',models:[nowPaid,zen('nemotron-3-ultra-free')],nowMs});
  assert.deepEqual(selected.map(row=>row.model_id),['nemotron-3-ultra-free']);
}

// --- stale price evidence is not proof of a current price ------------------
{
  const stale=zen('muse-spark-1.3-contributor-free',{priceVerifiedAt:'2026-09-14T00:00:00Z'});
  assert.equal(zeroCostRejection(stale,{nowMs}),'price_evidence_stale');
  assert.equal(selectModelWorkers({profile:'STANDARD',domain:'core',models:[stale],nowMs}).length,0);
}

// --- Hugging Face: a finite included credit is not recurring-free ----------
{
  const hf=credit=>({...base,provider_id:'huggingface_inference_providers',model_id:'openai/gpt-oss-120b',model_family:'gpt-oss-120b',free_status:'free_quota_hard_stop',zero_cost:{price_model:'finite_free_quota',input_price_per_million:0,output_price_per_million:0,price_verified_at:'2026-09-16T11:00:00Z',quota_model:'finite',hard_stop_verified:true,quota_headroom_ratio:credit,evidence:['https://huggingface.co/docs/inference-providers/pricing']}});
  assert.equal(zeroCostRejection(hf(0.6),{nowMs}),null,'routable while included credit remains');
  assert.equal(zeroCostRejection(hf(0.02),{nowMs}),'free_quota_below_safety_reserve','stops short of the billable boundary');
  const alternative={...base,provider_id:'groq',model_id:'openai/gpt-oss-120b-groq',model_family:'gpt-oss-groq',free_status:'account_specific',zero_cost:{price_model:'account_free',input_price_per_million:0,output_price_per_million:0,price_verified_at:'2026-09-16T11:00:00Z',quota_model:'unknown',hard_stop_verified:false,quota_headroom_ratio:null,evidence:['docs']}};
  const selected=selectModelWorkers({profile:'STANDARD',domain:'core',models:[hf(0.0),alternative],nowMs});
  assert.deepEqual(selected.map(row=>row.provider_id),['groq'],'exhausted credit fails over instead of spilling into paid credit');
}

// --- Alibaba: a finite free quota needs a verified hard stop ---------------
{
  const alibaba=extra=>({...base,provider_id:'alibaba_model_studio',model_id:'qwen3.8-flash',model_family:'qwen3.8-flash',free_status:'free_quota_hard_stop',privacy_class:'restricted',zero_cost:{price_model:'finite_free_quota',input_price_per_million:0,output_price_per_million:0,price_verified_at:'2026-09-16T11:00:00Z',quota_model:'finite',hard_stop_verified:true,quota_headroom_ratio:null,evidence:['https://help.aliyun.com/en/model-studio/new-free-quota'],...extra}});
  assert.equal(zeroCostRejection(alibaba(),{nowMs}),null);
  assert.equal(zeroCostRejection(alibaba({hard_stop_verified:false}),{nowMs}),'finite_free_quota_without_hard_stop','no hard stop means no autonomous use');
  assert.equal(zeroCostRejection(alibaba({quota_headroom_ratio:0.0}),{nowMs}),'free_quota_below_safety_reserve');
  assert.equal(selectionRejection(alibaba({hard_stop_verified:false}),{}),'zero_cost');
  // The console-verified allowance carries an end date. A free quota that has
  // expired is not a free quota, and the identical call past it is billable.
  const dated=alibaba({free_quota_expires_at:'2026-11-21T00:00:00Z'});
  assert.equal(zeroCostRejection(dated,{nowMs}),null,'routable while the quota is live');
  assert.equal(zeroCostRejection(dated,{nowMs:Date.parse('2026-11-21T00:00:01Z')}),'free_quota_expired');
  // On expiry the planner rotates to another zero-cost provider rather than
  // continuing on a now-billable route.
  const zeroCostAlternative={...base,provider_id:'groq',model_id:'gpt-oss-120b',model_family:'gpt-oss-120b',free_status:'account_specific',zero_cost:{price_model:'account_free',input_price_per_million:0,output_price_per_million:0,price_verified_at:'2026-09-16T11:00:00Z',quota_model:'unknown',hard_stop_verified:false,quota_headroom_ratio:null,evidence:['docs']}};
  const afterExpiry=selectModelWorkers({profile:'STANDARD',domain:'core',models:[dated,zeroCostAlternative],nowMs:Date.parse('2026-12-01T00:00:00Z')});
  assert.deepEqual(afterExpiry.map(row=>row.provider_id),['groq'],'expired free quota fails over, never falls through to PAYG');
}

// --- Cerebras: a trial that ran out never falls back to the paid tier ------
{
  const cerebras={...base,provider_id:'cerebras',model_id:'llama-3.3-70b',model_family:'llama-3.3-70b',free_status:'trial_credit',zero_cost:{price_model:'trial_credit',input_price_per_million:0,output_price_per_million:0,price_verified_at:'2026-09-16T11:00:00Z',quota_model:'finite',hard_stop_verified:false,quota_headroom_ratio:0,evidence:['https://www.cerebras.ai/pricing']}};
  assert.equal(freeOnlyEligible(cerebras,{nowMs}),false);
  assert.equal(selectionRejection(cerebras,{}),'free_entitlement');
  const selected=selectModelWorkers({profile:'DEEP',domain:'core',models:[cerebras],nowMs});
  assert.equal(selected.length,0,'an exhausted trial selects nothing rather than a paid route');
}

// --- SECRET never reaches an external free provider ------------------------
assert.equal(selectModelWorkers({profile:'DEEP',domain:'core',dataClass:'SECRET',models:[zen('big-pickle')],nowMs}).length,0);
// --- FAST never uses an external worker, whatever is eligible --------------
assert.equal(selectModelWorkers({profile:'FAST',domain:'core',models:[zen('big-pickle')],nowMs}).length,0);

console.log('model mesh zero-cost admission and failover contracts ok');
