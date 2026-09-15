import {FREE_ONLY_POLICY} from '../generated/free-only-policy.js';

export const MODEL_MESH_MODE='FREE_ONLY';
export const MODEL_MESH_LIMITS=Object.freeze({FAST:0,STANDARD:2,DEEP:4});
export const EXTERNAL_SECRET_CLASSES=new Set(['SECRET']);
export const FREE_ONLY_ELIGIBLE_STATUSES=Object.freeze([...FREE_ONLY_POLICY.eligible_statuses]);
export const PROVIDER_FAILURE_CATEGORIES=Object.freeze(['AUTH_FAILED','MODEL_NOT_FOUND','RATE_LIMITED','FREE_ENTITLEMENT_INVALID','REQUEST_INVALID','REGION_UNAVAILABLE','TIMEOUT','PROVIDER_5XX','PARSE_FAILED','UNKNOWN_SANITIZED']);
export function sanitizeDataClass(value){const v=String(value||'PUBLIC').toUpperCase();return ['PUBLIC','INTERNAL','CONFIDENTIAL','SECRET'].includes(v)?v:'PUBLIC';}
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
export function eligibleModel(model,dataClass='PUBLIC'){
  if(!freeOnlyEligible(model))return false;
  if(String(model.health||'healthy')!=='healthy')return false;
  if(sanitizeDataClass(dataClass)==='SECRET')return false;
  if(['INTERNAL','CONFIDENTIAL'].includes(sanitizeDataClass(dataClass))&&!['internal_safe','confidential_safe'].includes(String(model.privacy_class||'')))return false;
  return true;
}
