const TRUST=Object.freeze({
  issuer:'https://token.actions.githubusercontent.com',
  audience:'bybit-demo-smoke',
  repository:'hanlinh227-ship-it/trading-api',
  repositoryId:'1335593524',
  owner:'hanlinh227-ship-it',
  ref:'refs/heads/main',
  eventName:'push',
});
function b64u(v){const p=v.replace(/-/g,'+').replace(/_/g,'/')+'='.repeat((4-v.length%4)%4),b=atob(p),o=new Uint8Array(b.length);for(let i=0;i<b.length;i++)o[i]=b.charCodeAt(i);return o;}
function dec(v){return JSON.parse(new TextDecoder().decode(b64u(v)));}
let cache=null,cacheAt=0;
async function jwks(){if(cache&&Date.now()-cacheAt<300000)return cache;const c=await fetch(TRUST.issuer+'/.well-known/openid-configuration',{cf:{cacheTtl:300}});if(!c.ok)throw new Error('oidc_config_unavailable');const cj=await c.json();const r=await fetch(cj.jwks_uri,{cf:{cacheTtl:300}});if(!r.ok)throw new Error('oidc_jwks_unavailable');cache=await r.json();cacheAt=Date.now();return cache;}
export async function verifyBybitDemoSmokeOidc(token){
  if(!token)throw new Error('oidc_token_missing');
  const parts=String(token).split('.');if(parts.length!==3)throw new Error('invalid_jwt');
  const [h,p,s]=parts,head=dec(h),claims=dec(p);if(head.alg!=='RS256'||!head.kid)throw new Error('unsupported_jwt_header');
  const keys=await jwks(),jwk=(keys.keys||[]).find(k=>k.kid===head.kid&&k.kty==='RSA');if(!jwk)throw new Error('oidc_signing_key_not_found');
  const key=await crypto.subtle.importKey('jwk',jwk,{name:'RSASSA-PKCS1-v1_5',hash:'SHA-256'},false,['verify']);
  const ok=await crypto.subtle.verify({name:'RSASSA-PKCS1-v1_5'},key,b64u(s),new TextEncoder().encode(h+'.'+p));if(!ok)throw new Error('invalid_oidc_signature');
  const now=Math.floor(Date.now()/1000),aud=Array.isArray(claims.aud)?claims.aud:[claims.aud];
  if(claims.iss!==TRUST.issuer||!aud.includes(TRUST.audience)||claims.repository!==TRUST.repository||String(claims.repository_id)!==TRUST.repositoryId||claims.repository_owner!==TRUST.owner||claims.ref!==TRUST.ref||claims.event_name!==TRUST.eventName)throw new Error('invalid_oidc_claims');
  if(Number(claims.exp||0)<=now)throw new Error('token_expired');
  return claims;
}
