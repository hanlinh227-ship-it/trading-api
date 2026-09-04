from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
p=ROOT/'cloudflare-worker/bybit-android-monitor.js'
s=p.read_text()

old="const TOKEN_KEY='bybit:android:monitor:token:v1';"
new="const TOKEN_KEY='bybit:android:monitor:token:v1';\nconst PAIR_CODE_KEY='bybit:android:monitor:pair-code:v1';"
if old not in s: raise SystemExit('TOKEN_KEY_PATTERN_MISSING')
s=s.replace(old,new,1)

old="function actionBootstrapAuth(req,env){const expected=String(env.GPT_5AI_ACTION_KEY||'').trim(),got=String(req.headers.get('x-action-key')||'').trim();return !!expected&&secureEq(got,expected);}" 
new="function actionBootstrapAuth(req,env){const got=String(req.headers.get('x-action-key')||req.headers.get('authorization')||'').replace(/^Bearer\\s+/i,'').trim(),action=String(env.GPT_5AI_ACTION_KEY||'').trim(),bridge=String(env.V11_AI_BRIDGE_SECRET||env.BYBIT_VPS_BRIDGE_SECRET||'').trim();return !!got&&((!!action&&secureEq(got,action))||(!!bridge&&secureEq(got,bridge)));}"
if old not in s: raise SystemExit('ADMIN_AUTH_PATTERN_MISSING')
s=s.replace(old,new,1)

start=s.index('async function pairMonitor(req,env){')
end=s.index('\n\nasync function cached(',start)
replacement=r'''async function pairMonitor(req,env){
  if(!env.TRADING_STATE)return json({ok:false,error:'TRADING_STATE_KV_REQUIRED'},503);
  let body={};try{body=await req.json()}catch{}
  let authorized=actionBootstrapAuth(req,env),authSource=authorized?'ADMIN_SECRET':null;
  if(!authorized){
    const code=String(body?.pairingCode||'').trim().toUpperCase(),state=await kvGet(env,PAIR_CODE_KEY,null),now=Date.now();
    if(!code||!state?.sha256)return json({ok:false,error:'PAIRING_CODE_REQUIRED',readOnly:true},401);
    if(num(state.expiresAt)<=now){try{await env.TRADING_STATE.delete(PAIR_CODE_KEY)}catch{}return json({ok:false,error:'PAIRING_CODE_EXPIRED',readOnly:true},401);}
    const hash=await sha256Hex(code);if(!secureEq(hash,String(state.sha256||'')))return json({ok:false,error:'PAIRING_CODE_INVALID',readOnly:true},401);
    authorized=true;authSource='ONE_TIME_PAIR_CODE';try{await env.TRADING_STATE.delete(PAIR_CODE_KEY)}catch{}
  }
  if(!authorized)return json({ok:false,error:'PAIR_UNAUTHORIZED',readOnly:true},401);
  const deviceName=String(body?.deviceName||'Android Monitor').replace(/[\r\n\t]/g,' ').slice(0,80),token=randomToken(),sha256=await sha256Hex(token),at=Date.now();
  await env.TRADING_STATE.put(TOKEN_KEY,JSON.stringify({sha256,createdAt:at,rotatedAt:at,deviceName,schemaVersion:BYBIT_ANDROID_MONITOR_SCHEMA_VERSION,scope:'TELEMETRY_READ_ONLY'}));
  return json({ok:true,readOnly:true,schemaVersion:BYBIT_ANDROID_MONITOR_SCHEMA_VERSION,token,tokenType:'Bearer',scope:'TELEMETRY_READ_ONLY',deviceName,authSource,createdAt:new Date(at).toISOString(),warning:'TOKEN_IS_SHOWN_ONCE_STORE_IN_ANDROID_KEYSTORE'});
}
async function configurePairCode(req,env){
  if(!actionBootstrapAuth(req,env))return json({ok:false,error:'PAIR_CODE_ADMIN_AUTH_REQUIRED',readOnly:true},401);
  if(!env.TRADING_STATE)return json({ok:false,error:'TRADING_STATE_KV_REQUIRED'},503);
  let body={};try{body=await req.json()}catch{}
  const sha=String(body?.sha256||'').toLowerCase(),now=Date.now(),expiresAt=num(body?.expiresAt);
  if(!/^[a-f0-9]{64}$/.test(sha))return json({ok:false,error:'PAIR_CODE_SHA256_INVALID'},400);
  if(!(expiresAt>now&&expiresAt<=now+30*24*60*60*1000))return json({ok:false,error:'PAIR_CODE_EXPIRY_INVALID'},400);
  await env.TRADING_STATE.put(PAIR_CODE_KEY,JSON.stringify({sha256:sha,createdAt:now,expiresAt,schemaVersion:BYBIT_ANDROID_MONITOR_SCHEMA_VERSION,scope:'ONE_TIME_PAIRING_ONLY'}));
  return json({ok:true,readOnly:true,configured:true,expiresAt:new Date(expiresAt).toISOString(),plaintextCodeReturned:false});
}
'''
s=s[:start]+replacement+s[end:]

old="  if(p===BYBIT_ANDROID_MONITOR_ROUTES.authHealth&&req.method==='GET')return json(await authHealth(env));\n  if(p===BYBIT_ANDROID_MONITOR_ROUTES.pair&&req.method==='POST')return pairMonitor(req,env);"
new="  if(p===BYBIT_ANDROID_MONITOR_ROUTES.authHealth&&req.method==='GET')return json(await authHealth(env));\n  if(p==='/bybit/monitor/pair-code'&&req.method==='POST')return configurePairCode(req,env);\n  if(p===BYBIT_ANDROID_MONITOR_ROUTES.pair&&req.method==='POST')return pairMonitor(req,env);"
if old not in s: raise SystemExit('HANDLER_PAIR_PATTERN_MISSING')
s=s.replace(old,new,1)
p.write_text(s)

p=ROOT/'cloudflare-worker/bybit-android-monitor-contract.js'
s=p.read_text()
old="  pair:'/bybit/monitor/pair',"
new="  pair:'/bybit/monitor/pair',\n  pairCodeAdmin:'/bybit/monitor/pair-code',"
if old not in s: raise SystemExit('CONTRACT_PAIR_PATTERN_MISSING')
s=s.replace(old,new,1)
p.write_text(s)
print('BYBIT_ANDROID_MONITOR_ONE_TIME_PAIRING_PATCHED')
