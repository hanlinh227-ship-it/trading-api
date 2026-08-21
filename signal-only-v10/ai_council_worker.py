#!/usr/bin/env python3
import hashlib
import hmac
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT=Path('/opt/trading/trading-api')
AI_DIR=ROOT/'auto-futures-v1'/'ai'
sys.path.insert(0,str(AI_DIR))
from ai_budget_governor import allow, record_call, record_deepseek_cost

TOKEN=os.environ.get('TELEGRAM_BOT_TOKEN','').strip()
DEEPSEEK_KEY=os.environ.get('DEEPSEEK_API_KEY','').strip()
ORIGIN=os.environ.get('SIGNAL_V10_HUB_ORIGIN','').strip().rstrip('/')
WORKER='V10_VPS_3AI_BATCH_COUNCIL'
BATCH_SIZE=max(1,min(3,int(os.environ.get('SIGNAL_V10_AI_BATCH_SIZE','3'))))
POLL_SECONDS=max(5,int(os.environ.get('SIGNAL_V10_POLL_SECONDS','10')))
TIMEOUT=int(os.environ.get('SIGNAL_V10_AI_TIMEOUT_SECONDS','45'))
DEEPSEEK_MODEL=os.environ.get('DEEPSEEK_MODEL','deepseek-v4-flash')
CODEX_MODEL=os.environ.get('CODEX_MODEL','gpt-5.6-sol')
CLAUDE_MODEL=os.environ.get('CLAUDE_MODEL','sonnet')

ROLE_COMMON='''SIGNAL ONLY V10. Review only supplied candidates. Never invent missing facts. LONG/SHORT means the candidate is good enough NOW in that direction; WAIT means do not promote. Confidence is confidence in your returned action. Normally WAIT instead of reversing the proposed side. Return every candidateId exactly once. JSON only: {"reviews":[{"candidateId":"...","action":"LONG|SHORT|WAIT","confidence":0-100,"reason":"<=18 words"}]}'''
ROLES={
 'claude':'You are Claude. Focus on market context, regime coherence, timing, session/context fit, and chase/exhaustion risk.',
 'deepseek':'You are DeepSeek. Be adversarial: attack weak edge, fake breakout, spread/cost, crowding, volatility mismatch, and fragile geometry.',
 'codex':'You are Codex. Verify numerical/logical consistency: entry/SL/TP/RR, direction, quality, sample-stat usage, and execution plausibility. Historical WR is weak evidence only.'
}

def request_json(url,data=None,headers=None,method=None,timeout=30):
    req=urllib.request.Request(url,data=data,headers=headers or {},method=method)
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.loads(r.read().decode())

def discover_origin():
    global ORIGIN
    if ORIGIN:return ORIGIN
    if not TOKEN:raise RuntimeError('TELEGRAM_BOT_TOKEN_MISSING')
    x=request_json(f'https://api.telegram.org/bot{TOKEN}/getWebhookInfo',timeout=20)
    u=str(((x.get('result') or {}).get('url') or '')).strip()
    if not u:raise RuntimeError('TELEGRAM_WEBHOOK_NOT_CONFIGURED')
    p=urllib.parse.urlparse(u);ORIGIN=f'{p.scheme}://{p.netloc}';return ORIGIN

def sign(method,path,ts,raw=''):
    return hmac.new(TOKEN.encode(),f'{method}\n{path}\n{ts}\n{raw}'.encode(),hashlib.sha256).hexdigest()

def control(method,path,payload=None,query=None):
    origin=discover_origin();raw='' if payload is None else json.dumps(payload,separators=(',',':'),ensure_ascii=False);ts=str(int(time.time()));url=origin+path
    if query:url+='?'+urllib.parse.urlencode(query)
    headers={'x-signal-v10-timestamp':ts,'x-signal-v10-signature':sign(method,path,ts,raw),'user-agent':WORKER}
    data=raw.encode() if method=='POST' else None
    if method=='POST':headers['content-type']='application/json'
    return request_json(url,data=data,headers=headers,method=method,timeout=30)

def compact(items):
    out=[]
    for x in items:
        c=x.get('candidate') or {}
        out.append({'candidateId':x.get('id'),'symbol':c.get('symbol'),'market':c.get('market'),'proposedSide':c.get('side'),'qualityScore':c.get('qualityScore'),'entry':c.get('entry'),'sl':c.get('sl'),'tp':c.get('tp'),'rr':c.get('rr'),'quote':c.get('quote'),'method':c.get('method'),'context':c.get('context'),'symbolStats':c.get('symbolStats'),'entryIntelligence':c.get('entryIntelligence')})
    return out

def parse(text,items):
    ids={x.get('id') for x in items};a=text.find('{');b=text.rfind('}')
    if a<0 or b<=a:return {},'INVALID_JSON'
    try:o=json.loads(text[a:b+1])
    except Exception:return {},'INVALID_JSON'
    reviews={}
    for r in o.get('reviews',[]):
        cid=str(r.get('candidateId',''))
        if cid not in ids:continue
        action=str(r.get('action','WAIT')).upper()
        if action not in {'LONG','SHORT','WAIT'}:action='WAIT'
        try:conf=max(0,min(100,float(r.get('confidence',0) or 0)))
        except Exception:conf=0
        reviews[cid]={'status':'OK','action':action,'confidence':round(conf,1),'reason':str(r.get('reason',''))[:180]}
    missing=ids-set(reviews)
    for cid in missing:reviews[cid]={'status':'INCOMPLETE_OUTPUT','action':'WAIT','confidence':0,'reason':'provider omitted candidate'}
    return reviews,('OK' if not missing else 'INCOMPLETE_OUTPUT')

def run_cli(provider,items):
    ok,reason=allow(provider,'NORMAL')
    if not ok:return provider,{x['id']:{'status':'BUDGET_BLOCKED','action':'WAIT','confidence':0,'reason':reason} for x in items}
    payload=ROLES[provider]+'\n'+ROLE_COMMON+'\nDATA='+json.dumps(compact(items),ensure_ascii=False,separators=(',',':'))
    cmd=['claude','--model',CLAUDE_MODEL,'-p',payload] if provider=='claude' else ['/usr/bin/codex','exec','--model',CODEX_MODEL,'--ephemeral','--sandbox','read-only',payload]
    started=time.time()
    try:p=subprocess.run(cmd,capture_output=True,text=True,timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        record_call(provider,purpose='SIGNAL_V10_TIMEOUT',meta={'elapsed':round(time.time()-started,2)});return provider,{x['id']:{'status':'TIMEOUT','action':'WAIT','confidence':0,'reason':'timeout'} for x in items}
    except Exception as e:
        record_call(provider,purpose='SIGNAL_V10_ERROR',meta={'error':type(e).__name__});return provider,{x['id']:{'status':'ERROR','action':'WAIT','confidence':0,'reason':repr(e)[:120]} for x in items}
    record_call(provider,purpose='SIGNAL_V10_REVIEW',meta={'returncode':p.returncode,'elapsed':round(time.time()-started,2),'batch':len(items)})
    if p.returncode!=0:return provider,{x['id']:{'status':'ERROR','action':'WAIT','confidence':0,'reason':p.stderr[-160:]} for x in items}
    reviews,status=parse(p.stdout.strip(),items)
    if status!='OK':
        for r in reviews.values():r['status']=status if r['status']=='OK' else r['status']
    return provider,reviews

def run_deepseek(items):
    provider='deepseek';ok,reason=allow(provider,'NORMAL')
    if not ok:return provider,{x['id']:{'status':'BUDGET_BLOCKED','action':'WAIT','confidence':0,'reason':reason} for x in items}
    if not DEEPSEEK_KEY:return provider,{x['id']:{'status':'UNAVAILABLE','action':'WAIT','confidence':0,'reason':'DEEPSEEK_API_KEY_MISSING'} for x in items}
    system=ROLES[provider]+'\n'+ROLE_COMMON
    body={'model':DEEPSEEK_MODEL,'messages':[{'role':'system','content':system},{'role':'user','content':'DATA='+json.dumps(compact(items),ensure_ascii=False,separators=(',',':'))}],'response_format':{'type':'json_object'},'thinking':{'type':'disabled'},'temperature':0.05,'max_tokens':900,'stream':False}
    req=urllib.request.Request('https://api.deepseek.com/chat/completions',data=json.dumps(body).encode(),method='POST',headers={'Authorization':f'Bearer {DEEPSEEK_KEY}','Content-Type':'application/json','User-Agent':WORKER})
    try:
        with urllib.request.urlopen(req,timeout=TIMEOUT) as r:data=json.loads(r.read().decode())
    except Exception as e:return provider,{x['id']:{'status':'TIMEOUT' if 'timed out' in repr(e).lower() else 'ERROR','action':'WAIT','confidence':0,'reason':repr(e)[:140]} for x in items}
    usage=data.get('usage') or {};pt=int(usage.get('prompt_tokens',0) or 0);ct=int(usage.get('completion_tokens',0) or 0);hit=int(usage.get('prompt_cache_hit_tokens',0) or 0);miss=int(usage.get('prompt_cache_miss_tokens',max(0,pt-hit)) or 0);record_deepseek_cost(pt,ct,int(usage.get('total_tokens',pt+ct) or pt+ct),hit,miss,DEEPSEEK_MODEL)
    try:text=data['choices'][0]['message']['content'].strip()
    except Exception as e:return provider,{x['id']:{'status':'INVALID_RESPONSE','action':'WAIT','confidence':0,'reason':repr(e)[:120]} for x in items}
    reviews,status=parse(text,items)
    if status!='OK':
        for r in reviews.values():r['status']=status if r['status']=='OK' else r['status']
    return provider,reviews

def review_batch(items):
    results={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        fs=[pool.submit(run_cli,'claude',items),pool.submit(run_deepseek,items),pool.submit(run_cli,'codex',items)]
        for f in as_completed(fs):
            provider,reviews=f.result();results[provider]=reviews
    for item in items:
        cid=item['id'];payload={'candidateId':cid,'worker':WORKER,'reviewers':{p:(results.get(p,{}).get(cid) or {'status':'ERROR','action':'WAIT','confidence':0,'reason':'missing provider result'}) for p in ('claude','deepseek','codex')}}
        try:r=control('POST','/signal-v10/review',payload=payload);print('SUBMIT',cid,r.get('accepted'),(r.get('consensus') or {}).get('reason'),flush=True)
        except Exception as e:print('SUBMIT_ERROR',cid,repr(e),flush=True)

def main():
    if not TOKEN:raise SystemExit('TELEGRAM_BOT_TOKEN missing')
    print(WORKER,'START',discover_origin(),flush=True)
    while True:
        try:
            feed=control('GET','/signal-v10/candidates',query={'limit':BATCH_SIZE});items=feed.get('items') or []
            if items:review_batch(items);time.sleep(2)
            else:time.sleep(POLL_SECONDS)
        except KeyboardInterrupt:break
        except Exception as e:
            print('WORKER_ERROR',repr(e),flush=True);globals()['ORIGIN']='';time.sleep(max(5,POLL_SECONDS))

if __name__=='__main__':main()
