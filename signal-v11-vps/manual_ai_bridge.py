#!/usr/bin/env python3
import json,os,subprocess,time,urllib.request,urllib.error,shutil
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor,as_completed,wait

SECRET=os.environ.get('V11_AI_BRIDGE_SECRET','').strip()
HOST=os.environ.get('V11_AI_BRIDGE_HOST','127.0.0.1')
PORT=int(os.environ.get('V11_AI_BRIDGE_PORT','8789'))
TIMEOUT=int(os.environ.get('V11_AI_TIMEOUT','120'))
SCALP_PROVIDER_TIMEOUT=max(5,min(20,int(os.environ.get('V11_SCALP_PROVIDER_TIMEOUT','18'))))
SCALP_BRIDGE_BUDGET=max(8,min(23,int(os.environ.get('V11_SCALP_BRIDGE_BUDGET','20'))))
CLAUDE_MODEL=os.environ.get('V11_CLAUDE_MODEL','sonnet')
CODEX_MODEL=os.environ.get('V11_CODEX_MODEL','gpt-5.6-sol')
DEEPSEEK_API_KEY=os.environ.get('DEEPSEEK_API_KEY','').strip()
DEEPSEEK_BASE_URL=os.environ.get('DEEPSEEK_BASE_URL','https://api.deepseek.com').rstrip('/')
DEEPSEEK_MODEL=os.environ.get('DEEPSEEK_MODEL','deepseek-chat')
QWEN_API_KEY=os.environ.get('QWEN_API_KEY','').strip()
QWEN_BASE_URL=os.environ.get('QWEN_BASE_URL','').rstrip('/')
QWEN_MODEL=os.environ.get('QWEN_MODEL','qwen3-coder-flash')
OPENROUTER_API_KEY=os.environ.get('OPENROUTER_API_KEY','').strip()
OPENROUTER_BASE_URL=os.environ.get('OPENROUTER_BASE_URL','https://openrouter.ai/api/v1').rstrip('/')
OPENROUTER_MODEL=os.environ.get('OPENROUTER_MODEL','openrouter/auto')
PROVIDERS=('claude','codex','deepseek','qwen','openrouter')
SCALP_PROVIDERS=('claude','codex','deepseek')
LAST={p:{'state':'UNKNOWN','last_seen':None} for p in PROVIDERS}
BYBIT_BASES=('https://api.bybit.com','https://api.bytick.com')
BYBIT_PRIVATE_PATHS=(
    '/v5/account/wallet-balance',
    '/v5/position/list',
    '/v5/order/realtime',
    '/v5/position/closed-pnl',
    '/v5/order/create',
    '/v5/position/set-leverage',
    '/v5/position/trading-stop',
    '/v5/order/cancel-all',
)
TRADING_ROLE='''V11 MANUAL WHOLE-MARKET MARKET HUNTER. Review only supplied fresh candidates. This is an on-demand second opinion, not an automatic signal authority and not execution. Pick immediate MARKET suitability only. Never invent missing data. Return JSON: {"direction":"LONG|SHORT|WAIT","confidence":0-100,"hardRisk":[],"evidence":[],"reason":"..."}. If current evidence is insufficient for immediate MARKET, return WAIT.'''
ENGINEERING_ROLE='''You are one independent lane in the Trading Multi-AI engineering pool. Work only from supplied task/context. Never invent repository/runtime evidence. Do not execute trades or change deployment authority. Return one JSON object: {"verdict":"PASS|REJECT|BLOCKED","findings":[],"proposal":"...","evidence":[]}. Missing evidence means BLOCKED, not assumption.'''
SCALP_ROLE='''You are one independent reviewer for a 1-5 minute Bybit USDT perpetual scalp. Use only the supplied setup/context. Do not change size, leverage, SL or TP. Do not require a daily profit target. Return exactly one JSON object: {"verdict":"PASS|REJECT|BLOCKED","findings":[],"proposal":"...","evidence":[]}. PASS means the supplied direction is reasonable for a scalp, REJECT means the thesis is materially weak/contradictory, BLOCKED means data is unsafe or insufficient.'''

def extract(s):
    s=(s or '').strip();a=s.find('{');b=s.rfind('}')
    if a<0 or b<=a:raise ValueError('JSON_NOT_FOUND')
    x=json.loads(s[a:b+1])
    if not isinstance(x,dict):raise ValueError('JSON_OBJECT_REQUIRED')
    return x

def mode(evidence):return str(evidence.get('mode') or '').upper()
def engineering(evidence):return mode(evidence)=='MULTI_AI_ENGINEERING_TASK'
def scalp(evidence):return mode(evidence)=='BYBIT_SCALP_DECISION'
def verdict_mode(evidence):return engineering(evidence) or scalp(evidence)
def role_for(evidence):
    if engineering(evidence):return ENGINEERING_ROLE
    if scalp(evidence):return SCALP_ROLE
    return TRADING_ROLE

def requested_providers(evidence):
    raw=evidence.get('requestedProviders') if isinstance(evidence,dict) else None
    if not isinstance(raw,list):return SCALP_PROVIDERS if scalp(evidence) else PROVIDERS
    out=[]
    for p in raw:
        p=str(p or '').lower().strip()
        if p in PROVIDERS and p not in out:out.append(p)
    return tuple(out) if out else (SCALP_PROVIDERS if scalp(evidence) else PROVIDERS)

def validate_result(x,evidence):
    if verdict_mode(evidence):
        if x.get('verdict') not in ('PASS','REJECT','BLOCKED'):raise ValueError('VERDICT_REQUIRED')
        if not isinstance(x.get('findings'),list) or not isinstance(x.get('evidence'),list) or not isinstance(x.get('proposal'),str):raise ValueError('VERDICT_SCHEMA_INVALID')
    else:
        if x.get('direction') not in ('LONG','SHORT','WAIT'):raise ValueError('TRADING_DIRECTION_REQUIRED')
        if not isinstance(x.get('confidence'),(int,float)) or not 0<=x['confidence']<=100:raise ValueError('TRADING_CONFIDENCE_INVALID')
        if not isinstance(x.get('hardRisk'),list) or not isinstance(x.get('evidence'),list) or not isinstance(x.get('reason'),str):raise ValueError('TRADING_SCHEMA_INVALID')
    return x

def configured(provider):
    if provider=='claude':return bool(shutil.which('claude'))
    if provider=='codex':return os.path.exists('/usr/bin/codex') or bool(shutil.which('codex'))
    if provider=='deepseek':return bool(DEEPSEEK_API_KEY)
    if provider=='qwen':return bool(QWEN_API_KEY and QWEN_BASE_URL)
    if provider=='openrouter':return bool(OPENROUTER_API_KEY and OPENROUTER_BASE_URL)
    return False

def local_run(cmd,prompt,cwd='/tmp',timeout=None):
    t=max(1,int(timeout or TIMEOUT))
    p=subprocess.run(cmd,capture_output=True,text=True,input=prompt,timeout=t,cwd=cwd)
    if p.returncode:raise RuntimeError((p.stderr or p.stdout)[-1000:])
    return extract(p.stdout)

def api_run(base,key,model,prompt,timeout=None):
    if not base or not key:raise RuntimeError('PROVIDER_NOT_CONFIGURED')
    t=max(1,int(timeout or TIMEOUT))
    url=base if base.endswith('/chat/completions') else base+'/chat/completions'
    payload=json.dumps({'model':model,'messages':[{'role':'user','content':prompt}],'temperature':0.1,'max_tokens':1400}).encode()
    req=urllib.request.Request(url,data=payload,method='POST',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=t) as r:raw=r.read(2_000_000)
    except urllib.error.HTTPError as e:raise RuntimeError('HTTP_'+str(e.code)+':'+e.read(1000).decode(errors='replace'))
    j=json.loads(raw);return extract(((j.get('choices') or [{}])[0].get('message') or {}).get('content') or '')

def review(provider,evidence):
    prompt=role_for(evidence)+'\nPROVIDER_ROLE='+provider+'\nEVIDENCE='+json.dumps(evidence,ensure_ascii=False,separators=(',',':'))
    t=SCALP_PROVIDER_TIMEOUT if scalp(evidence) else TIMEOUT
    if provider=='claude':result=local_run(['claude','--model',CLAUDE_MODEL,'-p','--disallowedTools','Read,Grep,Glob,Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch'],prompt,'/tmp',t)
    elif provider=='codex':
        exe='/usr/bin/codex' if os.path.exists('/usr/bin/codex') else 'codex'
        result=local_run([exe,'exec','--model',CODEX_MODEL,'--ephemeral','--sandbox','read-only','--skip-git-repo-check','-'],prompt,'/tmp',t)
    elif provider=='deepseek':result=api_run(DEEPSEEK_BASE_URL,DEEPSEEK_API_KEY,DEEPSEEK_MODEL,prompt,t)
    elif provider=='qwen':result=api_run(QWEN_BASE_URL,QWEN_API_KEY,QWEN_MODEL,prompt,t)
    elif provider=='openrouter':result=api_run(OPENROUTER_BASE_URL,OPENROUTER_API_KEY,OPENROUTER_MODEL,prompt,t)
    else:raise ValueError('UNKNOWN_PROVIDER')
    return validate_result(result,evidence)

def run_provider(provider,evidence):
    t=time.time()
    if not configured(provider):return provider,{'status':'UNAVAILABLE','latencySeconds':0,'error':'PROVIDER_NOT_CONFIGURED'}
    try:
        result=review(provider,evidence);now=int(time.time()*1000);LAST[provider]={'state':'ONLINE','last_seen':now};return provider,{'status':'OK','latencySeconds':round(time.time()-t,2),'review':result,'last_seen':now}
    except subprocess.TimeoutExpired:
        LAST[provider]={'state':'DEGRADED','last_seen':int(time.time()*1000)};return provider,{'status':'TIMEOUT','latencySeconds':round(time.time()-t,2),'error':'LOCAL_PROVIDER_TIMEOUT'}
    except TimeoutError:
        LAST[provider]={'state':'DEGRADED','last_seen':int(time.time()*1000)};return provider,{'status':'TIMEOUT','latencySeconds':round(time.time()-t,2),'error':'PROVIDER_TIMEOUT'}
    except Exception as x:
        LAST[provider]={'state':'DEGRADED','last_seen':int(time.time()*1000)};return provider,{'status':'ERROR','latencySeconds':round(time.time()-t,2),'error':str(x)[:300]}

def run_selected(selected,evidence):
    out={}
    pool=ThreadPoolExecutor(max_workers=max(1,len(selected)))
    futures={pool.submit(run_provider,p,evidence):p for p in selected}
    try:
        if scalp(evidence):
            done,pending=wait(tuple(futures),timeout=SCALP_BRIDGE_BUDGET)
            for f in done:
                p,r=f.result();out[p]=r
            for f in pending:
                p=futures[f]
                out[p]={'status':'TIMEOUT','latencySeconds':SCALP_BRIDGE_BUDGET,'error':'BRIDGE_BUDGET_EXCEEDED'}
                f.cancel()
            return out
        for f in as_completed(tuple(futures)):
            p,r=f.result();out[p]=r
        return out
    finally:
        pool.shutdown(wait=False,cancel_futures=True)

def bybit_proxy(body):
    method=str(body.get('method') or 'GET').upper()
    path=str(body.get('path') or '')
    query=str(body.get('query') or '')
    raw_body=body.get('body')
    hdr=body.get('headers') or {}
    if method not in ('GET','POST'):return 400,{'ok':False,'error':'BYBIT_METHOD_NOT_ALLOWED'}
    if path not in BYBIT_PRIVATE_PATHS:return 403,{'ok':False,'error':'BYBIT_PATH_NOT_ALLOWED','path':path}
    allowed_headers={}
    for k in ('X-BAPI-API-KEY','X-BAPI-TIMESTAMP','X-BAPI-RECV-WINDOW','X-BAPI-SIGN','Content-Type','Accept'):
        if k in hdr:allowed_headers[k]=str(hdr[k])
    if not all(allowed_headers.get(k) for k in ('X-BAPI-API-KEY','X-BAPI-TIMESTAMP','X-BAPI-RECV-WINDOW','X-BAPI-SIGN')):
        return 400,{'ok':False,'error':'BYBIT_SIGNED_HEADERS_MISSING'}
    data=None if method=='GET' else str(raw_body or '').encode()
    attempts=[]
    for base in BYBIT_BASES:
        url=base+path+(('?'+query) if method=='GET' and query else '')
        req=urllib.request.Request(url,data=data,method=method,headers=allowed_headers)
        try:
            with urllib.request.urlopen(req,timeout=15) as r:
                raw=r.read(2_000_000).decode(errors='replace');status=r.status
        except urllib.error.HTTPError as e:
            status=e.code;raw=e.read(2_000_000).decode(errors='replace')
        except Exception as e:
            attempts.append({'base':base,'error':str(e)[:300]});continue
        attempts.append({'base':base,'httpStatus':status})
        try:upstream=json.loads(raw)
        except Exception:upstream={'retCode':None,'retMsg':raw[:500]}
        if status!=403:
            return 200,{'ok':200<=status<300,'transport':'VPS_BYBIT_PRIVATE_PROXY','base':base,'httpStatus':status,'upstream':upstream,'attempts':attempts}
    return 502,{'ok':False,'error':'BYBIT_PRIVATE_PROXY_ALL_BASES_FAILED','transport':'VPS_BYBIT_PRIVATE_PROXY','attempts':attempts}

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
        now=int(time.time()*1000);providers={};meta={'claude':(CLAUDE_MODEL,'architecture_reasoning'),'codex':(CODEX_MODEL,'technical_review'),'deepseek':(DEEPSEEK_MODEL,'implementation_repair'),'qwen':(QWEN_MODEL,'independent_repair_test'),'openrouter':(OPENROUTER_MODEL,'adversarial_fallback')}
        for p in PROVIDERS:
            model,role=meta[p];last=LAST[p];providers[p]={'configured':configured(p),'model':model,'role':role,'state':last['state'] if configured(p) else 'OFFLINE','last_seen':last['last_seen']}
        self.sendj(200,{'ok':True,'service':'V11_MULTI_AI_BRIDGE','mode':'PARALLEL','providerCount':sum(1 for p in PROVIDERS if configured(p)),'onDemandOnly':True,'bybitPrivateProxy':True,'bybitBases':list(BYBIT_BASES),'scalpProviderTimeoutSec':SCALP_PROVIDER_TIMEOUT,'scalpBridgeBudgetSec':SCALP_BRIDGE_BUDGET,'timestamp':now,'providers':providers})
    def do_POST(self):
        if not self.authorized():return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})
        try:
            body=self.read_json()
            if self.path=='/bybit/private':
                code,obj=bybit_proxy(body);return self.sendj(code,obj)
            if self.path!='/review':return self.sendj(404,{'ok':False})
            e=body.get('evidence') or {}
            if not isinstance(e,dict):return self.sendj(400,{'ok':False,'error':'EVIDENCE_OBJECT_REQUIRED'})
            selected=requested_providers(e);out=run_selected(selected,e)
            ordered={p:out.get(p,{'status':'UNAVAILABLE'}) for p in selected};usable=sum(1 for x in ordered.values() if x.get('status')=='OK')
            if scalp(e):ok=usable>=1
            else:ok=usable==len(selected)
            self.sendj(200 if ok else 502,{'ok':ok,'requestedProviders':list(selected),'usableProviderCount':usable,'providers':ordered,'timestamp':int(time.time()*1000),'mode':mode(e)})
        except Exception as x:self.sendj(400,{'ok':False,'error':str(x)[:300]})
    def log_message(self,*args):pass

if __name__=='__main__':
    if not SECRET:raise SystemExit('V11_AI_BRIDGE_SECRET required')
    print(f'V11 multi-AI + Bybit private bridge listening {HOST}:{PORT} providers={",".join(PROVIDERS)} scalpBudget={SCALP_BRIDGE_BUDGET}s',flush=True);ThreadingHTTPServer((HOST,PORT),H).serve_forever()
