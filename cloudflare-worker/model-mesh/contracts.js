import {FREE_ONLY_POLICY} from '../generated/free-only-policy.js';
import {quotaAvailable} from './quota-state.js';
import {MODEL_MESH_POLICY} from '../generated/model-mesh-policy.js';
import {zeroCostRejection} from './zero-cost.js';

export const MODEL_MESH_MODE=MODEL_MESH_POLICY.mode;
export const MODEL_MESH_LIMITS=Object.freeze({...MODEL_MESH_POLICY.max_parallel});
export const MODEL_MESH_SELECTION_FILTERS=Object.freeze([...MODEL_MESH_POLICY.selection_filters]);
export const MODEL_MESH_PRIVACY_POLICY=Object.freeze({...MODEL_MESH_POLICY.privacy});
export const EXTERNAL_SECRET_CLASSES=new Set(['SECRET']);
export const FREE_ONLY_ELIGIBLE_STATUSES=Object.freeze([...FREE_ONLY_POLICY.eligible_statuses]);
export const PROVIDER_FAILURE_CATEGORIES=Object.freeze(['AUTH_FAILED','MODEL_NOT_FOUND','MODEL_GONE','RATE_LIMITED','FREE_ENTITLEMENT_INVALID','PRICING_CHANGED','REQUEST_INVALID','REGION_UNAVAILABLE','TIMEOUT','PROVIDER_5XX','PARSE_FAILED','UNKNOWN_SANITIZED']);
// What the mesh does with each failure, from the canonical FREE_ONLY policy.
// 404/410 mean the model id is stale, so the fix is to discover and probe a
// replacement rather than to write the provider off.
export const PROVIDER_FAILURE_ACTIONS=Object.freeze({AUTH_FAILED:'credential_scope_failure_no_paid_fallback',MODEL_NOT_FOUND:'discover_probe_replacement',MODEL_GONE:'discover_probe_replacement',RATE_LIMITED:'cooldown_and_failover',FREE_ENTITLEMENT_INVALID:'quarantine_model_and_failover',PRICING_CHANGED:'quarantine_before_next_request',PROVIDER_5XX:'degrade_and_failover',TIMEOUT:'degrade_and_failover'});
export const REPLACEMENT_DISCOVERY_CATEGORIES=Object.freeze(['MODEL_NOT_FOUND','MODEL_GONE']);
export function sanitizeDataClass(value){if(value===undefined||value===null||String(value).trim()==='')return 'PUBLIC';const v=String(value).trim().toUpperCase();return ['PUBLIC','INTERNAL','CONFIDENTIAL','SECRET'].includes(v)?v:'SECRET';}
export function freeOnlyEligible(model,options={}){
  if(!model||!FREE_ONLY_ELIGIBLE_STATUSES.includes(String(model.free_status||''))||!String(model.free_verified_at||'').trim())return false;
  return zeroCostRejection(model,options)===null;
}
export function classifyProviderFailure({status=0,code=''}={}){
  const c=String(code||'').toUpperCase();
  if(c==='TIMEOUT'||c==='PARSE_FAILED')return c;
  const s=Number(status)||0;
  if(s===401||s===403)return 'AUTH_FAILED';
  if(s===404)return 'MODEL_NOT_FOUND';
  if(s===410)return 'MODEL_GONE';
  if(s===429)return 'RATE_LIMITED';
  if(s===402)return 'FREE_ENTITLEMENT_INVALID';
  if(s===400||s===405||s===409||s===415||s===422)return 'REQUEST_INVALID';
  if(s===451)return 'REGION_UNAVAILABLE';
  if(s>=500&&s<=599)return 'PROVIDER_5XX';
  return 'UNKNOWN_SANITIZED';
}
const PRODUCTION_USAGE_TERMS=new Set(['production_allowed']);
const SAFE_PRIVACY_CLASSES=new Set(['internal_safe','confidential_safe']);

/**
 * Apply the canonical filter-before-score chain.
 *
 * Provider-declared capability support preserves the current production gate.
 * Phase A measured evidence becomes an additional veto only when the compiled
 * Active Candidate Index explicitly enables a hard gate for that capability.
 */
export function selectionRejection(model,{dataClass='PUBLIC',requiredCapability='text_reasoning',contextTokens=0,hardCapabilityGate=false,nowMs=Date.now()}={}){
  const cls=sanitizeDataClass(dataClass);

  if(!FREE_ONLY_ELIGIBLE_STATUSES.includes(String(model?.free_status||''))||!String(model?.free_verified_at||'').trim())return 'free_entitlement';
  if(zeroCostRejection(model,{nowMs})!==null)return 'zero_cost';
  if(!PRODUCTION_USAGE_TERMS.has(String(model.usage_terms||'')))return 'usage_terms';

  const capability=model?.capabilities?.[requiredCapability];
  if(!capability||capability.supported!==true)return 'capability';
  if(hardCapabilityGate===true&&model?.capability_evidence?.[requiredCapability]?.state!=='VERIFIED')return 'capability';

  if(MODEL_MESH_PRIVACY_POLICY[cls]==='deny_external_free')return 'permission_ceiling';
  if(['INTERNAL','CONFIDENTIAL'].includes(cls)&&!SAFE_PRIVACY_CLASSES.has(String(model.privacy_class||'')))return 'privacy';
  if(String(model.health||'healthy')!=='healthy')return 'health';
  if(!quotaAvailable(model.quota_state??{state:model.runtimeState==='COOLDOWN'?'COOLDOWN_QUOTA':'AVAILABLE',resetAt:model.liveEvidence?.cooldownUntil??null}))return 'quota';

  const window=Number(model.context_window||0);
  if(contextTokens>0&&window>0&&contextTokens>window)return 'context_fit';

  return null;
}

export function eligibleModel(model,dataClass='PUBLIC',options={}){
  return selectionRejection(model,{...options,dataClass})===null;
}

const STATIC_FILTERS=new Set(['free_entitlement','zero_cost','usage_terms','capability','permission_ceiling','privacy']);

export function selectionCandidate(model,dataClass='PUBLIC',{nowMs=Date.now()}={}){
  const rejection=selectionRejection(model,{dataClass,nowMs});
  return rejection===null||!STATIC_FILTERS.has(rejection);
}
