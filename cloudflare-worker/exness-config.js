const on=v=>String(v??'').trim().toLowerCase()==='true';

export const EXNESS_SHADOW_VERSION='EXNESS_SHADOW_V1_READONLY';

export function exnessShadowConfig(env={}){
  const apiKey=String(env.EXNESS_API_KEY||env.EXN_API_KEY||'').trim();
  const privateKey=String(env.EXNESS_API_SECRET||env.EXN_PRIVATE_KEY||'').replace(/\\n/g,'\n').trim();
  const accountId=String(env.EXNESS_ACCOUNT_ID||env.EXN_ACCOUNT_ID||'').trim();
  const baseUrl=String(env.EXNESS_API_BASE_URL||env.EXN_API_BASE_URL||'').trim().replace(/\/$/,'');
  const enabled=on(env.EXNESS_ENABLED);
  const mode=String(env.EXNESS_MODE||'SHADOW').trim().toUpperCase();
  const liveEnabled=on(env.EXNESS_LIVE_ENABLED);
  const liveAck=on(env.EXNESS_LIVE_ACK);
  const blockers=[];
  if(!enabled)blockers.push('EXNESS_ENGINE_DISABLED');
  if(mode!=='SHADOW')blockers.push('EXNESS_SHADOW_MODE_REQUIRED');
  if(liveEnabled)blockers.push('EXNESS_LIVE_ENABLED_MUST_BE_FALSE');
  if(liveAck)blockers.push('EXNESS_LIVE_ACK_MUST_BE_FALSE');
  if(!apiKey)blockers.push('EXNESS_API_KEY_MISSING');
  if(!privateKey)blockers.push('EXNESS_API_SECRET_MISSING');
  if(!accountId)blockers.push('EXNESS_ACCOUNT_ID_MISSING');
  if(!baseUrl)blockers.push('EXNESS_API_BASE_URL_MISSING');
  else {
    try{
      const u=new URL(baseUrl);
      if(u.protocol!=='https:')blockers.push('EXNESS_API_BASE_URL_HTTPS_REQUIRED');
    }catch{
      blockers.push('EXNESS_API_BASE_URL_INVALID');
    }
  }
  return {
    version:EXNESS_SHADOW_VERSION,
    enabled,mode,liveEnabled,liveAck,
    apiKey,privateKey,accountId,baseUrl,
    ready: blockers.length===0,
    blockers,
    readOnly:true,
    writesAllowed:false,
  };
}
