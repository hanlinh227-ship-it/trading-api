#!/usr/bin/env python3
import json,os,subprocess,time,urllib.request,urllib.error,shutil
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor,as_completed
SECRET=os.environ.get('V11_AI_BRIDGE_SECRET','').strip(); HOST=os.environ.get('V11_AI_BRIDGE_HOST','127.0.0.1'); PORT=int(os.environ.get('V11_AI_BRIDGE_PORT','8789')); TIMEOUT=max(10,min(120,int(os.environ.get('V11_AI_TIMEOUT','60'))))
CLAUDE_MODEL=os.environ.get('V11_CLAUDE_MODEL','sonnet'); CODEX_MODEL=os.environ.get('V11_CODEX_MODEL','gpt-5.6-sol'); DEEPSEEK_API_KEY=os.environ.get('DEEPSEEK_API_KEY','').strip(); DEEPSEEK_BASE_URL=os.environ.get('DEEPSEEK_BASE_URL','https://api.deepseek.com').rstrip('/'); DEEPSEEK_MODEL=os.environ.get('DEEPSEEK_MODEL','deepseek-chat')
PROVIDERS=('claude','codex','deepseek'); LAST={p:{'state':'UNKNOWN','last_seen':None} for p in PROVIDERS}
ROLE='''You are one independent reviewer in the Unified Trading 3AI council. Use only supplied evidence. Never invent missing data. Return exactly one JSON object: {"verdict":"PASS|REJECT|BLOCKED","findings":[],"proposal":"...","evidence":[]}.'''
def extract(s):
 d=json.JSONDecoder()
 for i,c in enumerate((s or '').strip()):
  if c!='{':continue
  try:x,_=d.raw_decode((s or '').strip()[i:])
  except json.JSONDecodeError:continue
  if isinstance(x,dict):return x
 raise ValueError('JSON_OBJECT_REQUIRED')
def configured(p):
 return bool(shutil.which('claude')) if p=='claude' else (os.path.exists('/usr/bin/codex') or bool(shutil.which('codex'))) if p=='codex' else bool(DEEPSEEK_API_KEY) if p=='deepseek' else False
def local(cmd,prompt):
 r=subprocess.run(cmd,capture_output=True,text=True,input=prompt,timeout=TIMEOUT,cwd='/tmp')
 if r.returncode:raise RuntimeError((r.stderr or r.stdout)[-1000:])
 return extract(r.stdout)
def api(prompt):
 if not DEEPSEEK_API_KEY:raise RuntimeError('PROVIDER_NOT_CONFIGURED')
 data=json.dumps({'model':DEEPSEEK_MODEL,'messages':[{'role':'user','content':prompt}],'temperature':0.05,'max_tokens':900}).encode(); req=urllib.request.Request(DEEPSEEK_BASE_URL+'/chat/completions',data=data,method='POST',headers={'Authorization':'Bearer '+DEEPSEEK_API_KEY,'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=TIMEOUT) as r:j=json.loads(r.read(1000000))
 except urllib.error.HTTPError as e:raise RuntimeError('HTTP_'+str(e.code)+':'+e.read(700).decode(errors='replace'))
 return extract(((j.get('choices') or [{}])[0].get('message') or {}).get('content') or '')
def one(p,e):
 st=time.time()
 if not configured(p):return p,{'status':'UNAVAILABLE','error':'PROVIDER_NOT_CONFIGURED','latencySeconds':0}
 prompt=ROLE+'\nPROVIDER_ROLE='+p+'\nEVIDENCE='+json.dumps(e,ensure_ascii=False,separators=(',',':'))
 try:
  if p=='claude':x=local(['claude','--model',CLAUDE_MODEL,'-p','--disallowedTools','Read,Grep,Glob,Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch'],prompt)
  elif p=='codex':x=local(['/usr/bin/codex' if os.path.exists('/usr/bin/codex') else 'codex','exec','--model',CODEX_MODEL,'--ephemeral','--sandbox','read-only','--skip-git-repo-check','-'],prompt)
  else:x=api(prompt)
  now=int(time.time()*1000); LAST[p]={'state':'ONLINE','last_seen':now}; return p,{'status':'OK','review':x,'latencySeconds':round(time.time()-st,2),'last_seen':now}
 except subprocess.TimeoutExpired:LAST[p]={'state':'DEGRADED','last_seen':int(time.time()*1000)};return p,{'status':'TIMEOUT','error':'PROVIDER_TIMEOUT','latencySeconds':round(time.time()-st,2)}
 except Exception as z:LAST[p]={'state':'DEGRADED','last_seen':int(time.time()*1000)};return p,{'status':'ERROR','error':str(z)[:300],'latencySeconds':round(time.time()-st,2)}
def run(e):
 out={}
 with ThreadPoolExecutor(max_workers=3) as pool:
  for f in as_completed([pool.submit(one,p,e) for p in PROVIDERS]):p,r=f.result();out[p]=r
 return out
class H(BaseHTTPRequestHandler):
 def sendj(self,c,o):
  b=json.dumps(o,ensure_ascii=False).encode();self.send_response(c);self.send_header('content-type','application/json');self.send_header('cache-control','no-store');self.send_header('content-length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path!='/health':return self.sendj(404,{'ok':False})
  meta={'claude':CLAUDE_MODEL,'codex':CODEX_MODEL,'deepseek':DEEPSEEK_MODEL};p={n:{'configured':configured(n),'model':meta[n],'state':LAST[n]['state'] if configured(n) else 'OFFLINE','last_seen':LAST[n]['last_seen']} for n in PROVIDERS};q=sum(1 for n in PROVIDERS if configured(n));self.sendj(200,{'ok':q>=2,'service':'UNIFIED_3AI_BRIDGE','mode':'PARALLEL_QUORUM','providerCount':q,'requiredQuorum':2,'timestamp':int(time.time()*1000),'providers':p})
 def do_POST(self):
  if self.path!='/review':return self.sendj(404,{'ok':False})
  if not SECRET or self.headers.get('authorization','')!='Bearer '+SECRET:return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})
  try:
   n=int(self.headers.get('content-length','0'));body=json.loads(self.rfile.read(n));e=body.get('evidence') or {};bad=set(str(x).lower() for x in (e.get('requestedProviders') or PROVIDERS))-set(PROVIDERS)
   if bad:return self.sendj(400,{'ok':False,'error':'ONLY_CANONICAL_3AI_ALLOWED','rejectedProviders':sorted(bad)})
   st=time.time();p=run(e);q=sum(1 for n in PROVIDERS if p.get(n,{}).get('status')=='OK');self.sendj(200 if q>=2 else 502,{'ok':q>=2,'service':'UNIFIED_3AI_BRIDGE','task_id':e.get('task_id'),'quorum':q,'requiredQuorum':2,'providers':p,'decisionLatencyMs':round((time.time()-st)*1000)})
  except Exception as z:self.sendj(500,{'ok':False,'error':str(z)[:500]})
 def log_message(self,*_):pass
if __name__=='__main__':
 if not SECRET:raise SystemExit('V11_AI_BRIDGE_SECRET_REQUIRED')
 ThreadingHTTPServer((HOST,PORT),H).serve_forever()
