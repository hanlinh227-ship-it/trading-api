#!/usr/bin/env python3
"""Runtime health validator for the Trading Multi-AI gateway.

Claude, Codex and DeepSeek are the required trading core. Qwen/OpenRouter remain
observable optional lanes and may be degraded without marking the trading core down.
"""
from __future__ import annotations
import json,os,subprocess,time
URL=os.environ.get('MULTI_AI_GATEWAY_HEALTH_URL','').strip()
OIDC=os.environ.get('GATEWAY_OIDC','').strip()
TIMEOUT=float(os.environ.get('MULTI_AI_GATEWAY_TIMEOUT_SECONDS','10'))
MAX_AGE_MS=int(os.environ.get('MULTI_AI_GATEWAY_MAX_AGE_MS','300000'))
CORE=('claude','codex','deepseek')
OPTIONAL=('qwen','openrouter')
GOOD={'ONLINE','PASS','ACCEPT'}
def fail(message,code=2):print(json.dumps({'ok':False,'error':message},ensure_ascii=False));raise SystemExit(code)
def ms(v):
    try:n=float(v)
    except (TypeError,ValueError):return None
    if n<=0:return None
    return int(n*1000 if n<1e12 else n)
def fetch_json():
    cmd=['curl','-sS','--max-time',str(TIMEOUT),'-H','Accept: application/json']
    if OIDC: cmd += ['-H','Authorization: Bearer '+OIDC]
    cmd += ['-w','\n%{http_code}',URL]
    try:r=subprocess.run(cmd,capture_output=True,text=True,timeout=TIMEOUT+5)
    except (subprocess.TimeoutExpired,OSError) as exc:fail(f'gateway unreachable: {type(exc).__name__}')
    if r.returncode!=0:fail('gateway curl failed: '+(r.stderr or '').strip()[:500])
    body,sep,status=r.stdout.rpartition('\n')
    if not sep or not status.isdigit():fail('gateway curl response missing HTTP status')
    code=int(status)
    if code!=200:fail(f'gateway returned HTTP {code}: {body[:500]}')
    try:return json.loads(body)
    except json.JSONDecodeError:fail('gateway returned invalid JSON')
def inspect(name,x,now,required):
    if not isinstance(x,dict):return {'configured':False,'state':'MISSING','age_ms':None}, (name+':MISSING' if required else None)
    state=str(x.get('state') or x.get('status') or 'UNKNOWN').upper();seen=ms(x.get('last_seen') or x.get('last_updated') or x.get('timestamp'));age=None if seen is None else max(0,now-seen)
    detail={'configured':x.get('configured') is True,'state':state,'age_ms':age}
    if not required:return detail,None
    if x.get('configured') is not True:return detail,name+':NOT_CONFIGURED'
    if state not in GOOD:return detail,name+':'+state
    if seen is None:return detail,name+':NO_RUNTIME_TIMESTAMP'
    if seen>now+30000:return detail,name+':FUTURE_TIMESTAMP'
    if age>MAX_AGE_MS:return detail,name+':STALE'
    return detail,None
def main():
    if not URL:fail('MULTI_AI_GATEWAY_HEALTH_URL is required')
    if not (URL.startswith('https://') or URL.startswith('http://127.0.0.1') or URL.startswith('http://localhost')):fail('gateway health URL must use HTTPS unless localhost')
    p=fetch_json()
    if not isinstance(p,dict) or not isinstance(p.get('providers'),dict):fail('gateway payload missing providers object')
    now=int(time.time()*1000);bad=[];details={}
    for name in CORE:
        details[name],failure=inspect(name,p['providers'].get(name),now,True)
        if failure:bad.append(failure)
    for name in OPTIONAL:
        details[name],_=inspect(name,p['providers'].get(name),now,False)
    result={'ok':not bad,'service':str(p.get('service') or 'unknown')[:120],'mode':str(p.get('mode') or 'unknown')[:80],'requiredProviders':list(CORE),'optionalProviders':list(OPTIONAL),'providers':details,'failures':bad}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['ok']:raise SystemExit(3)
if __name__=='__main__':main()
