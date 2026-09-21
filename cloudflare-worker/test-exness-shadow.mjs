import assert from 'node:assert/strict';
import {generateKeyPairSync,verify,createHash} from 'node:crypto';
import {Buffer} from 'node:buffer';
import fs from 'node:fs';
import {exnessShadowConfig} from './exness-config.js';
import {buildExnessSignedHeaders} from './exness-signing.js';
import {createExnessReadonlyClient} from './exness-client.js';

{
  const cfg=exnessShadowConfig({});
  assert.equal(cfg.ready,false);
  assert.ok(cfg.blockers.includes('EXNESS_API_KEY_MISSING'));
  assert.ok(cfg.blockers.includes('EXNESS_ACCOUNT_ID_MISSING'));
  assert.ok(cfg.blockers.includes('EXNESS_API_BASE_URL_MISSING'));
}
{
  const cfg=exnessShadowConfig({
    EXNESS_ENABLED:'true',EXNESS_MODE:'SHADOW',EXNESS_LIVE_ENABLED:'true',EXNESS_LIVE_ACK:'false',
    EXNESS_API_KEY:'public',EXNESS_API_SECRET:'secret',EXNESS_ACCOUNT_ID:'123',EXNESS_API_BASE_URL:'https://api.exness.com'
  });
  assert.equal(cfg.ready,false);
  assert.ok(cfg.blockers.includes('EXNESS_LIVE_ENABLED_MUST_BE_FALSE'));
}
{
  const {privateKey,publicKey}=generateKeyPairSync('ed25519');
  const pem=privateKey.export({format:'pem',type:'pkcs8'}).toString();
  const path='/v1/configuration/accounts/123/account';
  const h=buildExnessSignedHeaders({apiKey:'exnsk_test',privateKey:pem,pathWithQuery:path,timestamp:1773656070123});
  const payload=Buffer.from(h['EXN-DATA'].replace(/-/g,'+').replace(/_/g,'/'),'base64');
  const sig=Buffer.from(h['EXN-SIGN'].replace(/-/g,'+').replace(/_/g,'/'),'base64');
  assert.equal(verify(null,payload,publicKey,sig),true);
  const decoded=JSON.parse(payload.toString('utf8'));
  assert.equal(decoded.method,'GET');
  assert.equal(decoded.path,path);
  assert.equal(decoded.idempotency_key,'');
  assert.equal(decoded.body_hash,createHash('sha256').update('').digest('base64url'));
}
{
  const {privateKey}=generateKeyPairSync('ed25519');
  const pem=privateKey.export({format:'pem',type:'pkcs8'}).toString();
  const calls=[];
  const fetchImpl=async (url,init={})=>{
    calls.push({url,method:init.method,headers:init.headers});
    if(url.endsWith('/account'))return new Response(JSON.stringify({account_status:'active',trade_mode:'enabled',currency:'USD'}),{status:200});
    if(url.endsWith('/instruments'))return new Response(JSON.stringify({instruments:['EURUSD','XAUUSD']}),{status:200});
    if(url.endsWith('/limits'))return new Response(JSON.stringify({rest:{}}),{status:200});
    return new Response('{}',{status:404});
  };
  const env={
    EXNESS_ENABLED:'true',EXNESS_MODE:'SHADOW',EXNESS_LIVE_ENABLED:'false',EXNESS_LIVE_ACK:'false',
    EXNESS_API_KEY:'exnsk_test',EXNESS_API_SECRET:pem,EXNESS_ACCOUNT_ID:'123',EXNESS_API_BASE_URL:'https://api.exness.com'
  };
  const api=createExnessReadonlyClient(env,{fetchImpl});
  await Promise.all([api.account(),api.instruments(),api.limits()]);
  assert.equal(calls.length,3);
  assert.ok(calls.every(x=>x.method==='GET'));
  assert.ok(calls.every(x=>String(x.headers['EXN-API-KEY'])==='exnsk_test'));
}

for(const file of ['exness-config.js','exness-signing.js','exness-client.js','exness-readonly-health.js']){
  const code=fs.readFileSync(file,'utf8');
  assert.doesNotMatch(code,/method\s*:\s*['"]POST['"]/i,`${file} must remain GET-only`);
  assert.doesNotMatch(code,/\/v1\/trading\/accounts\//i,`${file} must not reference trading write endpoints`);
}

console.log('exness shadow read-only contracts ok');
