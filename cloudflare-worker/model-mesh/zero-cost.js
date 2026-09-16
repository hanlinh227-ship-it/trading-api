// Zero-cost eligibility at execution time.
//
// FREE_ONLY does not mean "this provider is free forever"; it means the model
// costs nothing at the moment the request is made AND cannot spill into billable
// usage. Two classes need more than a class label to prove that:
//
//   temporary_zero_price  - priced at zero for now, so the price must be
//                           re-proven on a timer or the model is quarantined.
//   free_quota_hard_stop  - a finite free allowance, usable only while a
//                           verified hard stop makes a charge impossible.
//
// A recorded price above zero vetoes a model whatever its class says: the class
// is a claim, the price is evidence.
import {FREE_ONLY_POLICY} from '../generated/free-only-policy.js';

const REQUIREMENTS=Object.freeze({...(FREE_ONLY_POLICY.requirements||{})});
const GUARDS=Object.freeze({...(FREE_ONLY_POLICY.zero_cost_guards||{})});
const REVALIDATED_STATUSES=new Set(['temporary_zero_price']);
const FINITE_QUOTA_STATUSES=new Set(['free_quota_hard_stop']);
const NON_ZERO_PRICE_MODELS=new Set(['paid','trial_credit']);
const DEFAULT_REVALIDATE_HOURS=Number(GUARDS.price_revalidate_after_hours)||24;
const DEFAULT_RESERVE=Number.isFinite(Number(GUARDS.quota_safety_reserve_ratio))?Number(GUARDS.quota_safety_reserve_ratio):0.1;

// Number(null) and Number('') are 0, so a coerce-first helper would read an
// unknown headroom as an exhausted one and refuse a model that is fine. Absent
// evidence is absent, not zero.
const finiteNumber=value=>{
  if(value===null||value===undefined||value===''||typeof value==='boolean')return null;
  const n=Number(value);
  return Number.isFinite(n)?n:null;
};

/**
 * Why this model is not provably zero-cost right now, or null when it is.
 * Returned as a reason string so the caller can log a cause without a body.
 */
export function zeroCostRejection(model,{nowMs=Date.now()}={}){
  if(!model||typeof model!=='object')return 'not_a_model';
  const zeroCost=(model.zero_cost&&typeof model.zero_cost==='object')?model.zero_cost:{};

  if(NON_ZERO_PRICE_MODELS.has(String(zeroCost.price_model||'')))return 'price_model_not_zero_cost';
  for(const field of ['input_price_per_million','output_price_per_million']){
    const price=finiteNumber(zeroCost[field]);
    if(price!==null&&price>0)return 'nonzero_price';
  }

  const status=String(model.free_status||'');
  if(REVALIDATED_STATUSES.has(status)&&REQUIREMENTS.price_revalidation_required_for_temporary_zero_price!==false){
    const verifiedMs=Date.parse(String(zeroCost.price_verified_at||''));
    if(!Number.isFinite(verifiedMs))return 'price_evidence_missing';
    const hours=Number(zeroCost.price_revalidate_after_hours)>0?Number(zeroCost.price_revalidate_after_hours):DEFAULT_REVALIDATE_HOURS;
    if(nowMs-verifiedMs>hours*3600*1000)return 'price_evidence_stale';
  }

  const finite=FINITE_QUOTA_STATUSES.has(status)||String(zeroCost.quota_model||'')==='finite';
  if(finite){
    if(REQUIREMENTS.hard_stop_required_for_finite_free_quota!==false&&zeroCost.hard_stop_verified!==true)return 'finite_free_quota_without_hard_stop';
    if(REQUIREMENTS.quota_headroom_required_when_finite!==false){
      const headroom=finiteNumber(zeroCost.quota_headroom_ratio);
      if(headroom!==null&&headroom<=DEFAULT_RESERVE)return 'free_quota_below_safety_reserve';
    }
    // A free allowance with an end date stops being free on that date. Past it
    // the identical call is billable, so the model leaves the pool on the clock
    // rather than on the first charge.
    const expiresMs=Date.parse(String(zeroCost.free_quota_expires_at||''));
    if(Number.isFinite(expiresMs)&&nowMs>=expiresMs)return 'free_quota_expired';
  }
  return null;
}

export function zeroCostEligible(model,options={}){return zeroCostRejection(model,options)===null;}
export const ZERO_COST_GUARDS=GUARDS;
export const ZERO_COST_REQUIREMENTS=REQUIREMENTS;
