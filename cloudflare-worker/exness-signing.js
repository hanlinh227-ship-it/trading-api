import {Buffer} from 'node:buffer';
import {createHash,createPrivateKey,sign as nodeSign} from 'node:crypto';

const b64url=value=>Buffer.from(value).toString('base64').replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
const sha256=value=>createHash('sha256').update(value).digest();

function loadPrivateKey(value=''){
  const raw=String(value||'').replace(/\\n/g,'\n').trim();
  if(!raw)throw new Error('EXNESS_PRIVATE_KEY_MISSING');
  try{
    if(raw.startsWith('-----BEGIN'))return createPrivateKey(raw);
    return createPrivateKey({key:Buffer.from(raw,'base64'),format:'der',type:'pkcs8'});
  }catch{
    throw new Error('EXNESS_PRIVATE_KEY_FORMAT_UNSUPPORTED');
  }
}

export function exnessBodyHash(body=''){
  return b64url(sha256(Buffer.from(String(body),'utf8')));
}

export function buildExnessSignedHeaders({apiKey,privateKey,method='GET',pathWithQuery,body='',idempotencyKey='',timestamp=Date.now()}={}){
  const verb=String(method||'GET').toUpperCase();
  if(verb!=='GET')throw new Error('EXNESS_SHADOW_READONLY_METHOD_REQUIRED');
  const path=String(pathWithQuery||'');
  if(!path.startsWith('/'))throw new Error('EXNESS_SIGNED_PATH_REQUIRED');
  const ts=Number(timestamp);
  if(!Number.isFinite(ts)||ts<=0)throw new Error('EXNESS_TIMESTAMP_INVALID');
  const payload={
    api_key:String(apiKey||''),
    idempotency_key:'',
    timestamp:Math.trunc(ts),
    sign_version:1,
    method:'GET',
    path,
    body_hash:exnessBodyHash(body),
  };
  const payloadBytes=Buffer.from(JSON.stringify(payload),'utf8');
  const key=loadPrivateKey(privateKey);
  const signature=nodeSign(null,payloadBytes,key);
  return {
    'EXN-API-KEY':payload.api_key,
    'EXN-IDEMPOTENCY-KEY':'',
    'EXN-TIMESTAMP':String(payload.timestamp),
    'EXN-SIGN-VERSION':'1',
    'EXN-DATA':b64url(payloadBytes),
    'EXN-SIGN':b64url(signature),
  };
}
