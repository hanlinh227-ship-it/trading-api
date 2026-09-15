import {FREE_ONLY_POLICY} from '../generated/free-only-policy.js';
import {quotaAvailable} from './quota-state.js';
import {MODEL_MESH_POLICY} from '../generated/model-mesh-policy.js';

export const MODEL_MESH_MODE=MODEL_MESH_POLICY.mode;
// Compiled from the canonical policy.yaml -- never hard-coded here. The same
// contract feeds the /brain/mesh/health response and the CI assertion, so the
// canonical policy is the single authority for parallelism.
export const MODEL_MESH_LIMITS=Object.freeze({...MODEL_MESH_POLICY.max_parallel});
export const MODEL_MESH_SELECTION_FILTERS=Object.freeze([...MODEL_MESH_POLICY.selection_filters]);
export const MODEL_MESH_PRIVACY_POLICY=Object.freeze({...MODEL_MESH_POLICY.privacy});
export const EXTERNAL_SECRET_CLASSES=new Set(['SECRET']);
export const FREE_ONLY_ELIGIBLE_STATUSES=Object.freeze([...FREE_ONLY_POLICY.eligible_statuses]);
export const PROVIDER_FAILURE_CATEGORIES=Object.freeze(['AUTH_FAILED','MODEL_NOT_FOUND','RATE_LIMITED','FREE_ENTITLEMENT_INVALID','REQUEST_INVALID','REGION_UNAVAILABLE','TIMEOUT','PROVIDER_5XX','PARSE_FAILED','UNKNOWN_SANITIZED']);
export function sanitizeDataClass(value){if(value===undefined||value===null||String(value).trim()==='')return 'PUBLIC';const v=String(value).trim().toUpperCase();return ['PUBLIC','INTERNAL','CONFIDENTIAL','SECRET'].includes(v)?v:'SECRET';}
export function freeOnlyEligible(model){return Boolean(model&&FREE_ONLY_ELIGIBLE_STATUSES.includes(String(model.free_status||''))&&String(model.free_verified_at||'').trim());}
export function classifyProviderFailure({status=0,code=''}={}){
  const c=String(code||'').toUpperCase();
  if(c==='TIMEOUT'||c==='PARSE_FAILED')return c;
  const s=Number(status)||0;
  if(s===401||s===403)return 'AUTH_FAILED';
  if(s===404)return 'MODEL_NOT_FOUND';
  if(s===429)return 'RATE_LIMITED';
  if(s===402)return 'FREE_ENTITLEMENT_INVALID';
  if(s===400||s===405||s===409||s===415||s===422)return 'REQUEST_INVALID';
  if(s===451)return 'REGION_UNAVAILABLE';
  if(s>=500&&s<=599)return 'PROVIDER_5XX';
  return 'UNKNOWN_SANITIZED';
}
// Production usage terms. A model offered only for evaluation/trial may be
// discoverable but must never be selected to serve a real request.
const PRODUCTION_USAGE_TERMS=new Set(['production_allowed']);
const SAFE_PRIVACY_CLASSES=new Set(['internal_safe','confidential_safe']);

/**
 * Apply the canonical policy's `selection.filter_before_score` chain.
 *
 * Every filter named in policy.yaml is implemented here. Returns the name of
 * the first filter that rejects the model, or null when the model is eligible,
 * so callers can report *why* a model was excluded instead of silently
 * producing an empty worker set.
 */
export function selectionRejection(model,{dataClass='PUBLIC',requiredCapability='text_reasoning',contextTokens=0}={}){
  const cls=sanitizeDataClass(dataClass);

  // free_entitlement: FREE_ONLY eligibility with a verified observation.
  if(!freeOnlyEligible(model))return 'free_entitlement';

  // usage_terms: evaluation/trial offerings are not production capacity.
  if(!PRODUCTION_USAGE_TERMS.has(String(model.usage_terms||'')))return 'usage_terms';

  // capability: the model must actually support what the request needs.
  const capability=model?.capabilities?.[requiredCapability];
  if(!capability||capability.supported!==true)return 'capability';

  // permission_ceiling: the request's data class may never be widened.
  if(MODEL_MESH_PRIVACY_POLICY[cls]==='deny_external_free')return 'permission_ceiling';

  // privacy: non-public classes need an explicitly safe privacy class.
  if(['INTERNAL','CONFIDENTIAL'].includes(cls)&&!SAFE_PRIVACY_CLASSES.has(String(model.privacy_class||'')))return 'privacy';

  // health: only fresh LIVE_HEALTHY evidence admits a model.
  if(String(model.health||'healthy')!=='healthy')return 'health';

  // quota: a model inside its own cooldown/disabled window is not capacity.
  if(!quotaAvailable(model.quota_state??{state:model.runtimeState==='COOLDOWN'?'COOLDOWN_QUOTA':'AVAILABLE',resetAt:model.liveEvidence?.cooldownUntil??null}))return 'quota';

  // context_fit: the request must fit the model's context window.
  const window=Number(model.context_window||0);
  if(contextTokens>0&&window>0&&contextTokens>window)return 'context_fit';

  return null;
}

export function eligibleModel(model,dataClass='PUBLIC',options={}){
  return selectionRejection(model,{...options,dataClass})===null;
}

// Filters that depend only on the registry, not on live runtime state.
const STATIC_FILTERS=new Set(['free_entitlement','usage_terms','capability','permission_ceiling','privacy']);

/**
 * Can this model EVER be selected, ignoring current health and quota?
 *
 * Used to decide what is worth probing and what counts toward the runtime
 * provider inventory. A model the selection chain can never admit (an
 * evaluation-only offering, say) must not be probed -- probing it spends free
 * quota to produce evidence nothing will read -- and must not be reported as
 * ACTIVE, or the health overlay disagrees with the planner.
 */
export function selectionCandidate(model,dataClass='PUBLIC'){
  const rejection=selectionRejection(model,{dataClass});
  return rejection===null||!STATIC_FILTERS.has(rejection);
}
