export const MODEL_MESH_MODE='FREE_ONLY';
export const MODEL_MESH_LIMITS=Object.freeze({FAST:0,STANDARD:2,DEEP:4});
export const EXTERNAL_SECRET_CLASSES=new Set(['SECRET']);
export function sanitizeDataClass(value){const v=String(value||'PUBLIC').toUpperCase();return ['PUBLIC','INTERNAL','CONFIDENTIAL','SECRET'].includes(v)?v:'PUBLIC';}
export function eligibleModel(model,dataClass='PUBLIC'){
  if(!model||!['recurring','limited_time','account_specific'].includes(String(model.free_status||'')))return false;
  if(String(model.health||'healthy')!=='healthy')return false;
  if(sanitizeDataClass(dataClass)==='SECRET')return false;
  if(['INTERNAL','CONFIDENTIAL'].includes(sanitizeDataClass(dataClass))&&!['internal_safe','confidential_safe'].includes(String(model.privacy_class||'')))return false;
  return true;
}
