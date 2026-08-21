#!/usr/bin/env python3
import hashlib
import hmac
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ORIGIN=os.environ.get('SIGNAL_V10_ORIGIN','').rstrip('/')
SECRET=(os.environ.get('SIGNAL_V10_BRIDGE_SECRET') or os.environ.get('TELEGRAM_BOT_TOKEN') or '').strip()
POLL_SECONDS=max(3,int(os.environ.get('SIGNAL_V10_POLL_SECONDS','7')))
BATCH_LIMIT=max(1,min(3,int(os.environ.get('SIGNAL_V10_BATCH_LIMIT','3'))))
CLAUDE_MODEL=os.environ.get('SIGNAL_V10_CLAUDE_MODEL','sonnet')
DEEPSEEK_MODEL=os.environ.get('SIGNAL_V10_DEEPSEEK_MODEL',os.environ.get('DEEPSEEK_MODEL','deepseek-chat'))
CODEX_MODEL=os.environ.get('SIGNAL_V10_CODEX_MODEL','gpt-5.6-sol')
CLAUDE_TIMEOUT=int(os.environ.get('SIGNAL_V10_CLAUDE_TIMEOUT','48'))
DEEPSEEK_TIMEOUT=int(os.environ.get('SIGNAL_V10_DEEPSEEK_TIMEOUT','35'))
CODEX_TIMEOUT=int(os.environ.get('SIGNAL_V10_CODEX_TIMEOUT','48'))
CACHE_TTL=120
CACHE={}

COMMON='''SIGNAL ONLY V10. Review only supplied candidates. No execution authority. Return every candidateId exactly once. LONG/SHORT means the candidate is good enough to publish now in that direction. WAIT means do not publish. Confidence is confidence in your action. Missing evidence => WAIT. Normally WAIT rather than reversing scanner side. JSON only: {"reviews":[{"candidateId":"...","action":"LONG|SHORT|WAIT","confidence":0-100,"reason":"short factual reason"}]}'''
ROLES={
 'claude':'You are Claude, context/regime/timing specialist. Judge higher-timeframe coherence, session/regime fit, exhaustion/chase risk and whether the current trigger makes sense.',
 'deepseek':'You are DeepSeek, adversarial edge/risk specialist. Attack fake breakout, weak participation, spread/cost drag, crowding, volatility mismatch and stop/target geometry.',
 'codex':'You are Codex, quantitative/logical verifier. Check numerical consistency, plan geometry, RR, quality evidence, internal contradictions and execution logic. Do not invent data.'
}

def utc(): return datetime.now(timezone.utc).isoformat()
def sign(method,path,ts,raw=''):
    return hmac.new(SECRET.encode(),f'{method}\n{path}\n{ts}\n{raw}'.encode(),hashlib.sha256).hexdigest()
def request(method,path,payload=None,query=None,timeout=30):
    raw='' if payload is None else json.dumps(payload,separators=(',',':'),ensure_ascii=False)
    ts=str(int(time.time()));headers={'x-signal-v10-timestamp':ts,'x-signal-v10-signature':sign(method,path,ts,raw),'user-agent':'SIGNAL-V10-3AI-VPS'}
    url=ORIGIN+path
    if query:url+='?'+urllib.parse.urlencode(query)
    data=raw.encode() if method=='POST' else None
    if data is not None:headers['content-type']='application/json'
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())
def extract_json(text):
    text=(text or '').strip();a=text.find('{');b=text.rfind('}')
    if a<0 or b<=a:raise ValueError('JSON_NOT_FOUND')
    return json.loads(text[a:b+1])
def normalize(obj,candidates):
    ids={str(x['id']) for x in candidates};out={}
    for r in obj.get('reviews',[]) if isinstance(obj,dict) else []:
        cid=str(r.get('candidateId',''));action=str(r.get('action','WAIT')).upper()
        if cid not in ids or action not in {'LONG','SHORT','WAIT'}:continue
        try:conf=float(r.get('confidence',0));conf=conf*100 if 0<=conf<=1 else conf
        except Exception:conf=0
        out[cid]={'action':action,'confidence':round(max(0,min(100,conf)),1),'reason':str(r.get('reason',''))[:220]}
    missing=ids-set(out)
    if missing:raise ValueError('INCOMPLETE_OUTPUT:'+','.join(sorted(missing)))
    return out
def prompt(provider,candidates):
    payload=[{'candidateId':x['id'],**(x.get('candidate') or {})} for x in candidates]
    return ROLES[provider]+'\n\n'+COMMON+'\n\nCANDIDATES='+json.dumps(payload,ensure_ascii=False,separators=(',',':'))
def cached(provider,key):
    x=CACHE.get((provider,key));return x['value'] if x and time.time()-x['at']<CACHE_TTL else None
def remember(provider,key,value):CACHE[(provider,key)]={'at':time.time(),'value':value}
def batch_key(candidates):return hashlib.sha256('|'.join(sorted(str(x['id']) for x in candidates)).encode()).hexdigest()

def run_cli(cmd,timeout):
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
    if p.returncode!=0:raise RuntimeError((p.stderr or p.stdout)[-800:])
    return p.stdout

def review_claude(candidates):return normalize(extract_json(run_cli(['claude','--model',CLAUDE_MODEL,'-p',prompt('claude',candidates)],CLAUDE_TIMEOUT)),candidates)
def review_codex(candidates):return normalize(extract_json(run_cli(['/usr/bin/codex','exec','--model',CODEX_MODEL,'--ephemeral','--sandbox','read-only',prompt('codex',candidates)],CODEX_TIMEOUT)),candidates)
def review_deepseek(candidates):
    key=os.environ.get('DEEPSEEK_API_KEY','').strip()
    if not key:raise RuntimeError('DEEPSEEK_API_KEY_MISSING')
    body={'model':DEEPSEEK_MODEL,'messages':[{'role':'system','content':ROLES['deepseek']+'\n\n'+COMMON},{'role':'user','content':'CANDIDATES='+json.dumps([{'candidateId':x['id'],**(x.get('candidate') or {})} for x in candidates],ensure_ascii=False,separators=(',',':'))}],'response_format':{'type':'json_object'},'temperature':0.05,'max_tokens':900,'stream':False}
    req=urllib.request.Request('https://api.deepseek.com/chat/completions',data=json.dumps(body).encode(),headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(req,timeout=DEEPSEEK_TIMEOUT) as r:data=json.loads(r.read().decode())
    except urllib.error.HTTPError as e:raise RuntimeError(f'DEEPSEEK_HTTP_{e.code}:{e.read().decode(errors="replace")[-500:]}')
    return normalize(extract_json(data['choices'][0]['message']['content']),candidates)

def one_provider(name,candidates,key):
    hit=cached(name,key)
    if hit is not None:return {'status':'OK','latencySeconds':0,'cached':True,'reviews':hit}
    t=time.time()
    try:
        value={'claude':review_claude,'deepseek':review_deepseek,'codex':review_codex}[name](candidates);remember(name,key,value)
        return {'status':'OK','latencySeconds':round(time.time()-t,2),'cached':False,'reviews':value}
    except subprocess.TimeoutExpired:return {'status':'TIMEOUT','latencySeconds':round(time.time()-t,2),'error':'TIMEOUT'}
    except Exception as e:return {'status':'ERROR','latencySeconds':round(time.time()-t,2),'error':str(e)[:300]}

def report_health(providers,status='ONLINE'):
    try:request('POST','/signal-v10/worker-health',{'status':status,'worker':'signal-only-v10-vps','reportedAtIso':utc(),'providers':{k:{x:y for x,y in v.items() if x!='reviews'} for k,v in providers.items()}})
    except Exception:pass

def cycle():
    data=request('GET','/signal-v10/candidates',query={'limit':BATCH_LIMIT});candidates=data.get('items') or []
    if not candidates:
        report_health({},'IDLE');return 0
    key=batch_key(candidates);providers={}
    # Sequential calls avoid CPU/process spikes on small VPS; successful calls are cached for retry.
    for name in ('deepseek','claude','codex'):
        providers[name]=one_provider(name,candidates,key)
        print(utc(),'AI',name,providers[name]['status'],providers[name].get('latencySeconds'),flush=True)
    report_health(providers,'ONLINE' if all(x['status']=='OK' for x in providers.values()) else 'DEGRADED')
    if not all(x['status']=='OK' for x in providers.values()):return len(candidates)
    for c in candidates:
        cid=str(c['id']);reviewers={name:{'status':'OK',**providers[name]['reviews'][cid]} for name in providers}
        out=request('POST','/signal-v10/review',{'candidateId':cid,'worker':{'name':'signal-only-v10-vps','at':utc()},'reviewers':reviewers})
        print(utc(),'REVIEW',cid,out.get('accepted'),(out.get('consensus') or {}).get('reason'),flush=True)
    return len(candidates)

def main():
    if not ORIGIN or not SECRET:raise SystemExit('SIGNAL_V10_ORIGIN and SIGNAL_V10_BRIDGE_SECRET/TELEGRAM_BOT_TOKEN required')
    print(utc(),'SIGNAL ONLY V10 3-AI WORKER START',ORIGIN,flush=True)
    while True:
        try:cycle();time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:break
        except Exception as e:
            print(utc(),'WORKER_ERROR',repr(e),flush=True);report_health({},'ERROR');time.sleep(max(5,POLL_SECONDS))

if __name__=='__main__':main()
