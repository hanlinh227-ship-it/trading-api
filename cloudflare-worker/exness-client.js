import {buildExnessSignedHeaders} from './exness-signing.js';
import {exnessShadowConfig} from './exness-config.js';

function safeJson(text=''){
  try{return JSON.parse(text);}catch{return {raw:String(text||'').slice(0,300)};}
}

export function createExnessReadonlyClient(env={},opts={}){
  const cfg=exnessShadowConfig(env);
  const fetchImpl=opts.fetchImpl||fetch;
  async function get(path){
    if(!cfg.ready){
      const error=new Error('EXNESS_SHADOW_CONFIG_BLOCKED');
      error.exness={blockers:[...cfg.blockers]};
      throw error;
    }
    const headers=buildExnessSignedHeaders({
      apiKey:cfg.apiKey,
      privateKey:cfg.privateKey,
      method:'GET',
      pathWithQuery:path,
      body:'',
      idempotencyKey:'',
    });
    const response=await fetchImpl(cfg.baseUrl+path,{method:'GET',headers,cache:'no-store'});
    const text=await response.text();
    const body=safeJson(text);
    if(!response.ok){
      const error=new Error('EXNESS_READONLY_REQUEST_FAILED');
      error.exness={
        path,
        httpStatus:response.status,
        errorCode:body?.error_code??body?.code??null,
        errorMessage:String(body?.error_message||body?.message||body?.raw||'').slice(0,220),
      };
      throw error;
    }
    return body;
  }
  const id=encodeURIComponent(cfg.accountId);
  return {
    config:cfg,
    account:()=>get(`/v1/configuration/accounts/${id}/account`),
    instruments:()=>get(`/v1/configuration/accounts/${id}/instruments`),
    limits:()=>get(`/v1/configuration/accounts/${id}/limits`),
  };
}
