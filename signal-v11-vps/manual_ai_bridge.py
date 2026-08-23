#!/usr/bin/env python3
import json,os,subprocess,time,urllib.request,urllib.error,shutil
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor,as_completed

SECRET=os.environ.get('V11_AI_BRIDGE_SECRET','').strip()
HOST=os.environ.get('V11_AI_BRIDGE_HOST','127.0.0.1')
PORT=int(os.environ.get('V11_AI_BRIDGE_PORT','8789'))
TIMEOUT=int(os.environ.get('V11_AI_TIMEOUT','120'))
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
LAST={p:{'state':'UNKNOWN','last_seen':None} for p in PROVIDERS}

TRADING_ROLE='''V11 MANUAL WHOLE-MARKET MARKET HUNTER. Review only supplied fresh candidates. This is an on-demand second opinion, not an automatic signal authority and not execution. Pick immediate MARKET suitability only. Never invent missing data. Return JSON: {"direction":"LONG|SHORT|WAIT","confidence":0-100,"hardRisk":[],"evidence":[],"reason":"..."}. If current evidence is insufficient for immediate MARKET, return WAIT.'''
ENGINEERING_ROLE='''You are one independent lane in the Trading Multi-AI engineering pool. Work only from supplied task/context. Never invent repository/runtime evidence. Do not execute trades or change deployment authority. Return one JSON object: {"verdict":"PASS|REJECT|BLOCKED","findings":[],"proposal":"...","evidence":[]}. For implementation-oriented roles, proposal may describe a bounded patch; for review roles, identify concrete blockers. Missing evidence means BLOCKED, not assumption.'''

def extract(s):
    s=(s or '').strip();a=s.find('{');b=s.rfind('}')
    if a<0 or b<=a:raise ValueError('JSON_NOT_FOUND')
    x=json.loads(s[a:b+1])
    if not isinstance(x,dict):raise ValueError('JSON_OBJECT_REQUIRED')
    return x

def configured(provider):
    if provider=='claude':return bool(shutil.which('claude'))
    if provider=='codex':return os.path.exists('/usr/bin/codex') or bool(shutil.which('codex'))
    if provider=='deepseek':return bool(DEEPSEEK_API_KEY)
    if provider=='qwen':return bool(QWEN_API_KEY and QWEN_BASE_URL)
    if provider=='openrouter':return bool(OPENROUTER_API_KEY and OPENROUTER_BASE_URL)
    return False

def role_for(evidence):
    return ENGINEERING_ROLE if str(evidence.get('mode') or '').upper()=='MULTI_AI_ENGINEERING_TASK' else TRADING_ROLE

def local_run(cmd,prompt):
    p=subprocess.run(cmd+[prompt],capture_output=True,text=True,timeout=TIMEOUT,cwd='/tmp')
    if p.returncode:raise RuntimeError((p.stderr or p.stdout)[-1000:])
    return extract(p.stdout)

def api_run(base,key,model,prompt):
    if not base or not key:raise RuntimeError('PROVIDER_NOT_CONFIGURED')
    url=base if base.endswith('/chat/completions') else base+'/chat/completions'
    payload=json.dumps({'model':model,'messages':[{'role':'user','content':prompt}],'temperature':0.1,'max_tokens':1400}).encode()
    req=urllib.request.Request(url,data=payload,method='POST',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Accept':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=TIMEOUT) as r: raw=r.read(2_000_000)
    except urllib.error.HTTPError as e:
        raise RuntimeError('HTTP_'+str(e.code)+':'+e.read(1000).decode(errors='replace'))
    j=json.loads(raw);content=((j.get('choices') or [{}])[0].get('message') or {}).get('content') or ''
    return extract(content)

def review(provider,evidence):
    prompt=role_for(evidence)+'\nPROVIDER_ROLE='+provider+'\nEVIDENCE='+json.dumps(evidence,ensure_ascii=False,separators=(',',':'))
    if provider=='claude':
        # Claude is a reviewer lane, never a source writer. Restrict tool access
        # explicitly and run outside the repository workspace to contain prompt injection.
        return local_run(['claude','--model',CLAUDE_MODEL,'-p','--allowedTools','Read,Grep,Glob','--disallowedTools','Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch'],prompt)
    if provider=='codex':
        exe='/usr/bin/codex' if os.path.exists('/usr/bin/codex') else 'codex'
        return local_run([exe,'exec','--model',CODEX_MODEL,'--ephemeral','--sandbox','read-only'],prompt)
    if provider=='deepseek':return api_run(DEEPSEEK_BASE_URL,DEEPSEEK_API_KEY,DEEPSEEK_MODEL,prompt)
    if provider=='qwen':return api_run(QWEN_BASE_URL,QWEN_API_KEY,QWEN_MODEL,prompt)
    if provider=='openrouter':return api_run(OPENROUTER_BASE_URL,OPENROUTER_API_KEY,OPENROUTER_MODEL,prompt)
    raise ValueError('UNKNOWN_PROVIDER')

def run_provider(provider,evidence):
    t=time.time()
    if not configured(provider):return provider,{'status':'UNAVAILABLE','latencySeconds':0}
    try:
        result=review(provider,evidence);now=int(time.time()*1000);LAST[provider]={'state':'ONLINE','last_seen':now}
        return provider,{'status':'OK','latencySeconds':round(time.time()-t,2),'review':result,'last_seen':now}
    except subprocess.TimeoutExpired:
        LAST[provider]={'state':'DEGRADED','last_seen':int(time.time()*1000)}
        return provider,{'status':'TIMEOUT','latencySeconds':round(time.time()-t,2)}
    except Exception as x:
        LAST[provider]={'state':'DEGRADED','last_seen':int(time.time()*1000)}
        return provider,{'status':'ERROR','latencySeconds':round(time.time()-t,2),'error':str(x)[:300]}

class H(BaseHTTPRequestHandler):
    def sendj(self,code,obj):
        raw=json.dumps(obj,ensure_ascii=False).encode();self.send_response(code);self.send_header('content-type','application/json');self.send_header('cache-control','no-store');self.send_header('content-length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path!='/health':return self.sendj(404,{'ok':False})
        now=int(time.time()*1000);providers={}
        meta={'claude':(CLAUDE_MODEL,'architecture_reasoning'),'codex':(CODEX_MODEL,'technical_review'),'deepseek':(DEEPSEEK_MODEL,'implementation_repair'),'qwen':(QWEN_MODEL,'independent_repair_test'),'openrouter':(OPENROUTER_MODEL,'adversarial_fallback')}
        for p in PROVIDERS:
            model,role=meta[p];last=LAST[p]
            providers[p]={'configured':configured(p),'model':model,'role':role,'state':last['state'] if configured(p) else 'OFFLINE','last_seen':last['last_seen']}
        self.sendj(200,{'ok':True,'service':'V11_MULTI_AI_BRIDGE','mode':'PARALLEL','providerCount':sum(1 for p in PROVIDERS if configured(p)),'onDemandOnly':True,'timestamp':now,'providers':providers})
    def do_POST(self):
        if self.path!='/review':return self.sendj(404,{'ok':False})
        if not SECRET or self.headers.get('authorization','')!='Bearer '+SECRET:return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})
        try:
            n=int(self.headers.get('content-length','0'))
            if n<=0 or n>1_000_000:return self.sendj(413,{'ok':False,'error':'BODY_SIZE'})
            body=json.loads(self.rfile.read(n));e=body.get('evidence') or {}
            if not isinstance(e,dict):return self.sendj(400,{'ok':False,'error':'EVIDENCE_OBJECT_REQUIRED'})
            out={}
            with ThreadPoolExecutor(max_workers=5) as pool:
                futures=[pool.submit(run_provider,p,e) for p in PROVIDERS]
                for f in as_completed(futures):
                    p,r=f.result();out[p]=r
            ordered={p:out.get(p,{'status':'UNAVAILABLE'}) for p in PROVIDERS}
            ok=all(x.get('status')=='OK' for x in ordered.values())
            self.sendj(200 if ok else 502,{'ok':ok,'providers':ordered,'timestamp':int(time.time()*1000)})
        except Exception as x:self.sendj(400,{'ok':False,'error':str(x)[:300]})
    def log_message(self,*args):pass

if __name__=='__main__':
    if not SECRET:raise SystemExit('V11_AI_BRIDGE_SECRET required')
    print(f'V11 multi-AI bridge listening {HOST}:{PORT} providers={",".join(PROVIDERS)}',flush=True)
    ThreadingHTTPServer((HOST,PORT),H).serve_forever()
