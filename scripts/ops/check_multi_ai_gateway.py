#!/usr/bin/env python3
"""Fail-closed runtime health validator for the Trading Multi-AI gateway."""
from __future__ import annotations
import json,os,time,urllib.error,urllib.request
URL=os.environ.get('MULTI_AI_GATEWAY_HEALTH_URL','').strip()
TIMEOUT=float(os.environ.get('MULTI_AI_GATEWAY_TIMEOUT_SECONDS','10'))
MAX_AGE_MS=int(os.environ.get('MULTI_AI_GATEWAY_MAX_AGE_MS','300000'))
EXPECTED=('claude','codex','deepseek','qwen','openrouter')
GOOD={'ONLINE','PASS','ACCEPT'}
def fail(message,code=2):print(json.dumps({'ok':False,'error':message},ensure_ascii=False));raise SystemExit(code)
def ms(v):
    try:n=float(v)
    except (TypeError,ValueError):return None
    if n<=0:return None
    return int(n*1000 if n<1e12 else n)
def main():
    if not URL:fail('MULTI_AI_GATEWAY_HEALTH_URL is required')
    if not (URL.startswith('https://') or URL.startswith('http://127.0.0.1') or URL.startswith('http://localhost')):fail('gateway health URL must use HTTPS unless localhost')
    try:
        with urllib.request.urlopen(urllib.request.Request(URL,headers={'Accept':'application/json'}),timeout=TIMEOUT) as r:
            if r.status!=200:fail(f'gateway returned HTTP {r.status}')
            raw=r.read(256_000)
    except (urllib.error.URLError,TimeoutError,OSError) as exc:fail(f'gateway unreachable: {type(exc).__name__}')
    try:p=json.loads(raw)
    except json.JSONDecodeError:fail('gateway returned invalid JSON')
    if not isinstance(p,dict) or not isinstance(p.get('providers'),dict):fail('gateway payload missing providers object')
    now=int(time.time()*1000);bad=[];details={}
    for name in EXPECTED:
        x=p['providers'].get(name)
        if not isinstance(x,dict):bad.append(name+':MISSING');continue
        state=str(x.get('state') or x.get('status') or 'UNKNOWN').upper();seen=ms(x.get('last_seen') or x.get('last_updated') or x.get('timestamp'));age=None if seen is None else max(0,now-seen)
        details[name]={'configured':x.get('configured') is True,'state':state,'age_ms':age}
        if x.get('configured') is not True:bad.append(name+':NOT_CONFIGURED')
        elif state not in GOOD:bad.append(name+':'+state)
        elif seen is None:bad.append(name+':NO_RUNTIME_TIMESTAMP')
        elif seen>now+30000:bad.append(name+':FUTURE_TIMESTAMP')
        elif age>MAX_AGE_MS:bad.append(name+':STALE')
    result={'ok':bool(p.get('ok')) and not bad,'service':str(p.get('service') or 'unknown')[:120],'mode':str(p.get('mode') or 'unknown')[:80],'providers':details,'failures':bad}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result['ok']:raise SystemExit(3)
if __name__=='__main__':main()
