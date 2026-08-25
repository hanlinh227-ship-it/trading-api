#!/usr/bin/env python3
import json,os,subprocess,time,urllib.request,urllib.error,shutil
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor,as_completed,wait,FIRST_COMPLETED

SECRET=os.environ.get('V11_AI_BRIDGE_SECRET','').strip()
HOST=os.environ.get('V11_AI_BRIDGE_HOST','127.0.0.1')
PORT=int(os.environ.get('V11_AI_BRIDGE_PORT','8789'))
TIMEOUT=int(os.environ.get('V11_AI_TIMEOUT','120'))
SCALP_PROVIDER_TIMEOUT=max(5,min(15,int(os.environ.get('V11_SCALP_PROVIDER_TIMEOUT','12'))))
CLAUDE_SCALP_TIMEOUT=max(SCALP_PROVIDER_TIMEOUT,min(30,int(os.environ.get('V11_CLAUDE_SCALP_TIMEOUT','30'))))
SCALP_BRIDGE_BUDGET=max(6,min(15,int(os.environ.get('V11_SCALP_BRIDGE_BUDGET','12'))))
SCALP_FAST_FIRST_GRACE=max(0.2,min(3.0,float(os.environ.get('V11_SCALP_FAST_FIRST_GRACE','1.5'))))
CLAUDE_MODEL=os.environ.get('V11_CLAUDE_MODEL','sonnet')
CODEX_MODEL=os.environ.get('V11_CODEX_MODEL','gpt-5.6-sol')
DEEPSEEK_API_KEY=os.environ.get('DEEPSEEK_API_KEY','').strip()
DEEPSEEK_BASE_URL=os.environ.get('DEEPSEEK_BASE_URL','https://api.deepseek.com').rstrip('/')
DEEPSEEK_MODEL=os.environ.get('DEEPSEEK_MODEL','deepseek-chat')
QWEN_API_KEY=os.environ.get('QWEN_API_KEY','').strip();QWEN_BASE_URL=os.environ.get('QWEN_BASE_URL','').rstrip('/');QWEN_MODEL=os.environ.get('QWEN_MODEL','qwen3-coder-flash')
OPENROUTER_API_KEY=os.environ.get('OPENROUTER_API_KEY','').strip();OPENROUTER_BASE_URL=os.environ.get('OPENROUTER_BASE_URL','https://openrouter.ai/api/v1').rstrip('/');OPENROUTER_MODEL=os.environ.get('OPENROUTER_MODEL','openrouter/auto')
PROVIDERS=('claude','codex','deepseek','qwen','openrouter');SCALP_PROVIDERS=('claude','codex','deepseek')
LAST={p:{'state':'UNKNOWN','last_seen':None} for p in PROVIDERS}
BYBIT_BASES=('https://api.bybit.com','https://api.bytick.com')
BYBIT_PRIVATE_PATHS=('/v5/account/wallet-balance','/v5/position/list','/v5/order/realtime','/v5/position/closed-pnl','/v5/order/create','/v5/position/set-leverage','/v5/position/trading-stop','/v5/order/cancel-all')
BYBIT_PUBLIC_PATHS=('/v5/market/time','/v5/market/instruments-info','/v5/market/tickers','/v5/market/kline')
BYBIT_PROXY_PATHS=BYBIT_PRIVATE_PATHS+BYBIT_PUBLIC_PATHS
TRADING_ROLE='''V11 MANUAL WHOLE-MARKET MARKET HUNTER. Review only supplied fresh candidates. Never invent missing data. Return JSON: {"direction":"LONG|SHORT|WAIT","confidence":0-100,"hardRisk":[],"evidence":[],"reason":"..."}.'''
ENGINEERING_ROLE='''You are one independent lane in the Trading Multi-AI engineering pool. Work only from supplied task/context. Return one JSON object: {"verdict":"PASS|REJECT|BLOCKED","findings":[],"proposal":"...","evidence":[]}.'''
SCALP_ROLE='''You are one independent reviewer for a 1-5 minute Bybit USDT perpetual scalp. Use only supplied setup/context. Do not change size, leverage, SL or TP. Do not require a daily target. Return exactly one JSON object: {"verdict":"PASS|REJECT|BLOCKED","findings":[],"proposal":"...","evidence":[]}. PASS=direction reasonable, REJECT=materially weak/contradictory, BLOCKED=data unsafe/insufficient.'''

def extract(s):
    s=(s or '').strip()
    if not s:raise ValueError('JSON_NOT_FOUND')
    dec=json.JSONDecoder();saw_non_object=False
    for i,ch in enumerate(s):
        if ch!='{':continue
        try:x,_=dec.raw_decode(s[i:])
        except json.JSONDecodeError:continue
        if isinstance(x,dict):return x
        saw_non_object=True
    if saw_non_object:raise ValueError('JSON_OBJECT_REQUIRED')
    raise ValueError('JSON_NOT_FOUND')

def mode(e):return str(e.get('mode') or '').upper()
def engineering(e):return mode(e)=='MULTI_AI_ENGINEERING_TASK'
def scalp(e):return mode(e)=='BYBIT_SCALP_DECISION'
def role_for(e):return ENGINEERING_ROLE if engineering(e) else SCALP_ROLE if scalp(e) else TRADING_ROLE

def requested_providers(e):
    raw=e.get('requestedProviders') if isinstance(e,dict) else None
    if not isinstance(raw,list):return SCALP_PROVIDERS if scalp(e) else PROVIDERS
    out=[]
    for p in raw:
        p=str(p or '').lower().strip()
        if p in PROVIDERS and p not in out:out.append(p)
    return tuple(out) if out else (SCALP_PROVIDERS if scalp(e) else PROVIDERS)

def validate_result(x,e):
    if engineering(e) or scalp(e):
        if x.get('verdict') not in ('PASS','REJECT','BLOCKED'):raise ValueError('VERDICT_REQUIRED')
        if not isinstance(x.get('findings'),list) or not isinstance(x.get('evidence'),list) or not isinstance(x.get('proposal'),str):raise ValueError('VERDICT_SCHEMA_INVALID')
    else:
        if x.get('direction') not in ('LONG','SHORT','WAIT'):raise ValueError('TRADING_DIRECTION_REQUIRED')
        if not isinstance(x.get('confidence'),(int,float)):raise ValueError('TRADING_CONFIDENCE_INVALID')
    return x

def configured(p):
    if p=='claude':return bool(shutil.which('claude'))
    if p=='codex':return os.path.exists('/usr/bin/codex') or bool(shutil.which('codex'))
    if p=='deepseek':return bool(DEEPSEEK_API_KEY)
    if p=='qwen':return bool(QWEN_API_KEY and QWEN_BASE_URL)
    if p=='openrouter':return bool(OPENROUTER_API_KEY and OPENROUTER_BASE_URL)
    return False

def local_run(cmd,prompt,cwd='/tmp',timeout=None):
    p=subprocess.run(cmd,capture_output=True,text=True,input=prompt,timeout=max(1,int(timeout or TIMEOUT)),cwd=cwd)
    if p.returncode:raise RuntimeError((p.stderr or p.stdout)[-1000:])
    return extract(p.stdout)

def api_run(base,key,model,prompt,timeout=None):
    if not base or not key:raise RuntimeError('PROVIDER_NOT_CONFIGURED')
    url=base if base.endswith('/chat/completions') else base+'/chat/completions'
    payload=json.dumps({'model':model,'messages':[{'role':'user','content':prompt}],'temperature':0.05,'max_tokens':900}).encode()
    req=urllib.request.Request(url,data=payload,method='POST',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=max(1,int(timeout or TIMEOUT))) as r:raw=r.read(1_000_000)
    except urllib.error.HTTPError as e:raise RuntimeError('HTTP_'+str(e.code)+':'+e.read(700).decode(errors='replace'))
    j=json.loads(raw);return extract(((j.get('choices') or [{}])[0].get('message') or {}).get('content') or '')

def review(p,e):
    prompt=role_for(e)+'\nPROVIDER_ROLE='+p+'\nEVIDENCE='+json.dumps(e,ensure_ascii=False,separators=(',',':'))
    if scalp(e):t=CLAUDE_SCALP_TIMEOUT if p=='claude' else SCALP_PROVIDER_TIMEOUT
    else:t=TIMEOUT
    if p=='claude':r=local_run(['claude','--model',CLAUDE_MODEL,'-p','--disallowedTools','Read,Grep,Glob,Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch'],prompt,'/tmp',t)
    elif p=='codex':
        exe='/usr/bin/codex' if os.path.exists('/usr/bin/codex') else 'codex';r=local_run([exe,'exec','--model',CODEX_MODEL,'--ephemeral','--sandbox','read-only','--skip-git-repo-check','-'],prompt,'/tmp',t)
    elif p=='deepseek':r=api_run(DEEPSEEK_BASE_URL,DEEPSEEK_API_KEY,DEEPSEEK_MODEL,prompt,t)
    elif p=='qwen':r=api_run(QWEN_BASE_URL,QWEN_API_KEY,QWEN_MODEL,prompt,t)
    elif p=='openrouter':r=api_run(OPENROUTER_BASE_URL,OPENROUTER_API_KEY,OPENROUTER_MODEL,prompt,t)
    else:raise ValueError('UNKNOWN_PROVIDER')
    return validate_result(r,e)

def run_provider(p,e):
    started=time.time()
    if not configured(p):return p,{'status':'UNAVAILABLE','latencySeconds':0,'error':'PROVIDER_NOT_CONFIGURED'}
    try:
        r=review(p,e);now=int(time.time()*1000);LAST[p]={'state':'ONLINE','last_seen':now};return p,{'status':'OK','latencySeconds':round(time.time()-started,2),'review':r,'last_seen':now}
    except subprocess.TimeoutExpired:
        LAST[p]={'state':'DEGRADED','last_seen':int(time.time()*1000)};return p,{'status':'TIMEOUT','latencySeconds':round(time.time()-started,2),'error':'LOCAL_PROVIDER_TIMEOUT'}
    except TimeoutError:
        LAST[p]={'state':'DEGRADED','last_seen':int(time.time()*1000)};return p,{'status':'TIMEOUT','latencySeconds':round(time.time()-started,2),'error':'PROVIDER_TIMEOUT'}
    except Exception as x:
        LAST[p]={'state':'DEGRADED','last_seen':int(time.time()*1000)};return p,{'status':'ERROR','latencySeconds':round(time.time()-started,2),'error':str(x)[:300]}

def run_selected(selected,e):
    if not scalp(e):
        out={}
        with ThreadPoolExecutor(max_workers=max(1,len(selected))) as pool:
            for f in as_completed([pool.submit(run_provider,p,e) for p in selected]):p,r=f.result();out[p]=r
        return out,False,None
    if len(selected)==1:
        started=time.monotonic();p=selected[0];_,r=run_provider(p,e)
        return {p:r},False,round((time.monotonic()-started)*1000)
    started=time.monotonic();out={};pool=ThreadPoolExecutor(max_workers=max(1,len(selected)));futures={pool.submit(run_provider,p,e):p for p in selected};pending=set(futures);first_ok_at=None;returned_early=False
    try:
        while pending:
            elapsed=time.monotonic()-started
            remaining=SCALP_BRIDGE_BUDGET-elapsed
            if remaining<=0:break
            timeout=remaining if first_ok_at is None else min(remaining,max(0,SCALP_FAST_FIRST_GRACE-(time.monotonic()-first_ok_at)))
            if timeout<=0:returned_early=True;break
            done,pending=wait(pending,timeout=timeout,return_when=FIRST_COMPLETED)
            if not done:
                if first_ok_at is not None:returned_early=True
                break
            for f in done:
                p,r=f.result();out[p]=r
                if r.get('status')=='OK' and first_ok_at is None:first_ok_at=time.monotonic()
            if first_ok_at is not None and time.monotonic()-first_ok_at>=SCALP_FAST_FIRST_GRACE:
                returned_early=True;break
        for f in list(pending):
            p=futures[f];out[p]={'status':'UNAVAILABLE','latencySeconds':round(time.monotonic()-started,2),'error':'FAST_FIRST_NOT_WAITED'};f.cancel()
        return out,returned_early,round((time.monotonic()-started)*1000)
    finally:
        pool.shutdown(wait=False,cancel_futures=True)

def bybit_proxy(body):
    method=str(body.get('method') or 'GET').upper();path=str(body.get('path') or '');query=str(body.get('query') or '');raw_body=body.get('body');hdr=body.get('headers') or {}
    if method not in ('GET','POST'):return 400,{'ok':False,'error':'BYBIT_METHOD_NOT_ALLOWED'}
    if path not in BYBIT_PROXY_PATHS:return 403,{'ok':False,'error':'BYBIT_PATH_NOT_ALLOWED','path':path}
    is_public=path in BYBIT_PUBLIC_PATHS
    signed_headers={k:str(hdr[k]) for k in ('X-BAPI-API-KEY','X-BAPI-TIMESTAMP','X-BAPI-RECV-WINDOW','X-BAPI-SIGN','Content-Type','Accept') if k in hdr}
    if not is_public and not all(signed_headers.get(k) for k in ('X-BAPI-API-KEY','X-BAPI-TIMESTAMP','X-BAPI-RECV-WINDOW','X-BAPI-SIGN')):return 400,{'ok':False,'error':'BYBIT_SIGNED_HEADERS_MISSING'}
    allowed={'Accept':'application/json'} if is_public else signed_headers
    data=None if method=='GET' else str(raw_body or '').encode();attempts=[]
    transport='VPS_BYBIT_MARKET_PROXY' if is_public else 'VPS_BYBIT_PRIVATE_PROXY'
    for base in BYBIT_BASES:
        url=base+path+(('?'+query) if method=='GET' and query else '');req=urllib.request.Request(url,data=data,method=method,headers=allowed)
        try:
            with urllib.request.urlopen(req,timeout=12) as r:raw=r.read(1_000_000).decode(errors='replace');status=r.status
        except urllib.error.HTTPError as e:status=e.code;raw=e.read(1_000_000).decode(errors='replace')
        except Exception as e:attempts.append({'base':base,'error':str(e)[:200]});continue
        attempts.append({'base':base,'httpStatus':status})
        try:upstream=json.loads(raw)
        except Exception:upstream={'retCode':None,'retMsg':raw[:400]}
        if status!=403:return 200,{'ok':200<=status<300,'transport':transport,'base':base,'httpStatus':status,'upstream':upstream,'attempts':attempts}
    return 502,{'ok':False,'error':'BYBIT_PROXY_ALL_BASES_FAILED','transport':transport,'attempts':attempts}

class H(BaseHTTPRequestHandler):
    def sendj(self,code,obj):
        raw=json.dumps(obj,ensure_ascii=False).encode();self.send_response(code);self.send_header('content-type','application/json');self.send_header('cache-control','no-store');self.send_header('content-length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def authorized(self):return bool(SECRET and self.headers.get('authorization','')=='Bearer '+SECRET)
    def read_json(self,limit=1_000_000):
        n=int(self.headers.get('content-length','0'))
        if n<=0 or n>limit:raise ValueError('BODY_SIZE')
        return json.loads(self.rfile.read(n))
    def do_GET(self):
        if self.path!='/health':return self.sendj(404,{'ok':False})
        meta={'claude':(CLAUDE_MODEL,'architecture_reasoning'),'codex':(CODEX_MODEL,'technical_review'),'deepseek':(DEEPSEEK_MODEL,'implementation_repair'),'qwen':(QWEN_MODEL,'independent_repair_test'),'openrouter':(OPENROUTER_MODEL,'adversarial_fallback')};providers={}
        for p in PROVIDERS:
            model,role=meta[p];last=LAST[p];providers[p]={'configured':configured(p),'model':model,'role':role,'state':last['state'] if configured(p) else 'OFFLINE','last_seen':last['last_seen']}
        self.sendj(200,{'ok':True,'service':'V11_MULTI_AI_BRIDGE','mode':'FAST_FIRST_PARALLEL','providerCount':sum(configured(p) for p in PROVIDERS),'onDemandOnly':True,'bybitPrivateProxy':True,'bybitMarketProxy':True,'bybitBases':list(BYBIT_BASES),'bybitPublicPaths':list(BYBIT_PUBLIC_PATHS),'scalpProviderTimeoutSec':SCALP_PROVIDER_TIMEOUT,'claudeScalpTimeoutSec':CLAUDE_SCALP_TIMEOUT,'scalpBridgeBudgetSec':SCALP_BRIDGE_BUDGET,'scalpFastFirstGraceSec':SCALP_FAST_FIRST_GRACE,'timestamp':int(time.time()*1000),'providers':providers})
    def do_POST(self):
        if not self.authorized():return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})
        try:
            body=self.read_json()
            if self.path=='/bybit/private':code,obj=bybit_proxy(body);return self.sendj(code,obj)
            if self.path!='/review':return self.sendj(404,{'ok':False})
            e=body.get('evidence') or {}
            if not isinstance(e,dict):return self.sendj(400,{'ok':False,'error':'EVIDENCE_OBJECT_REQUIRED'})
            selected=requested_providers(e);out,returned_early,decision_ms=run_selected(selected,e);ordered={p:out.get(p,{'status':'UNAVAILABLE'}) for p in selected};usable=sum(1 for x in ordered.values() if x.get('status')=='OK');ok=usable>=1 if scalp(e) else usable==len(selected)
            self.sendj(200 if ok else 502,{'ok':ok,'requestedProviders':list(selected),'usableProviderCount':usable,'providers':ordered,'fastFirst':bool(scalp(e) and len(selected)>1),'returnedEarly':returned_early,'decisionLatencyMs':decision_ms,'timestamp':int(time.time()*1000),'mode':mode(e)})
        except Exception as x:self.sendj(400,{'ok':False,'error':str(x)[:300]})
    def log_message(self,*args):pass

if __name__=='__main__':
    if not SECRET:raise SystemExit('V11_AI_BRIDGE_SECRET required')
    print(f'V11 fast-first AI + Bybit bridge {HOST}:{PORT}',flush=True)
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()