#!/usr/bin/env python3
import json,os,subprocess,time,urllib.request,urllib.error,shutil,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor,as_completed
SECRET=os.environ.get('V11_AI_BRIDGE_SECRET','').strip(); HOST=os.environ.get('V11_AI_BRIDGE_HOST','127.0.0.1'); PORT=int(os.environ.get('V11_AI_BRIDGE_PORT','8789')); TIMEOUT=max(10,min(120,int(os.environ.get('V11_AI_TIMEOUT','60'))))
CLAUDE_MODEL=os.environ.get('V11_CLAUDE_MODEL','sonnet'); CODEX_MODEL=os.environ.get('V11_CODEX_MODEL','gpt-5.6-sol')
PROVIDERS=('claude','codex'); LAST={p:{'state':'UNKNOWN','last_seen':None,'project':None,'error':None} for p in PROVIDERS}
LANE_WAIT=max(.1,min(15,float(os.environ.get('V11_AI_LANE_WAIT_SEC','2.5')))); HEALTH_STALE_MS=max(60000,min(3600000,int(float(os.environ.get('V11_AI_HEALTH_STALE_SEC','900'))*1000)))
PROJECTS=('BYBIT','FOREX','OTHER')
LANES={p:{project:threading.BoundedSemaphore(1) for project in PROJECTS} for p in PROVIDERS}
GLOBAL={p:threading.BoundedSemaphore(2) for p in PROVIDERS}
ACTIVE={p:{project:0 for project in PROJECTS} for p in PROVIDERS}; ACTIVE_LOCK=threading.Lock()
BYBIT_BASES=tuple(dict.fromkeys([x.rstrip('/') for x in [os.environ.get('BYBIT_API_BASE_URL','').strip(),'https://api.bybit.com','https://api.bytick.com'] if x.strip()]))
BYBIT_ALLOWED_PREFIXES=('/v5/account/','/v5/position/','/v5/order/','/v5/market/')
BYBIT_ALLOWED_METHODS=('GET','POST')
REVIEW_ROLE='''You are one independent reviewer in the Unified Trading 2AI council. Use only supplied evidence. Never invent missing data. Return exactly one JSON object: {"verdict":"PASS|REJECT|BLOCKED","findings":[],"proposal":"...","evidence":[]}.'''
FOREX_ROLE='''You are one independent autonomous discretionary Forex trader. You receive raw MT5 broker evidence and must make your own trading decision without any precomputed signal, score, indicator gate, or deterministic trade manager. Respect the required BUY/SELL alternation side without forcing a trade. Never invent broker prices. Return exactly one JSON object: {"entry":{"decision":"ENTER|WAIT","symbol":"SYMBOL|NONE","side":"BUY|SELL|NONE","orderType":"MARKET|LIMIT|STOP","entryPrice":number,"requestedRiskPct":0-1,"sl":number,"tp":number,"technicalAnalysis":"concrete M5/M15/H1/H4 reasoning","economicAnalysis":"current macro/rates/news/risk reasoning","thesis":"short synthesis","invalidation":"short","riskFlags":[]},"entryCandidates":[{"decision":"ENTER","symbol":"SYMBOL","side":"BUY|SELL","orderType":"MARKET|LIMIT|STOP","entryPrice":number,"requestedRiskPct":0-1,"sl":number,"tp":number,"technicalAnalysis":"reasoning","economicAnalysis":"reasoning","thesis":"short","invalidation":"short","riskFlags":[]}],"management":[{"ticket":"ticket","action":"HOLD|CLOSE|MODIFY_SLTP","sl":number,"tp":number,"reason":"AI reasoning"}],"portfolioView":"short"}. entryCandidates may contain up to 3 genuinely tradable candidates respecting requiredSide. For MARKET orderType, entryPrice may be 0 because broker quote is authority. For LIMIT/STOP, entryPrice must be the intended trigger price. Think deeply but output only JSON.'''
def extract(s):
 d=json.JSONDecoder()
 for i,c in enumerate((s or '').strip()):
  if c!='{':continue
  try:x,_=d.raw_decode((s or '').strip()[i:])
  except json.JSONDecodeError:continue
  if isinstance(x,dict):return x
 raise ValueError('JSON_OBJECT_REQUIRED')
def configured(p):
 return bool(shutil.which('claude')) if p=='claude' else (os.path.exists('/usr/bin/codex') or bool(shutil.which('codex'))) if p=='codex' else False
def project_of(e):
 mode=str(e.get('mode') or '').upper()
 if mode in ('FOREX_AUTONOMOUS_TRADER','PURE_AI_FOREX_2AI_FAST') or mode.startswith('FOREX_'):return 'FOREX'
 if mode.startswith('BYBIT_'):return 'BYBIT'
 return 'OTHER'
def compact_process_error(r):
 raw=((r.stderr or '')+'\n'+(r.stdout or '')).strip()
 if len(raw)<=1400:return f'PROVIDER_EXIT_{r.returncode}: '+raw
 return f'PROVIDER_EXIT_{r.returncode}: HEAD='+raw[:500]+' ... TAIL='+raw[-850:]
def local(cmd,prompt):
 r=subprocess.run(cmd,capture_output=True,text=True,input=prompt,timeout=TIMEOUT,cwd='/tmp')
 if r.returncode:raise RuntimeError(compact_process_error(r))
 try:return extract(r.stdout)
 except Exception as e:
  raw=(r.stdout or '').strip(); tail=raw[-900:] if len(raw)>900 else raw
  raise RuntimeError('PROVIDER_OUTPUT_JSON_INVALID: '+tail) from e
def one(p,e):
 st=time.time(); project=project_of(e)
 if not configured(p):return p,{'status':'UNAVAILABLE','error':'PROVIDER_NOT_CONFIGURED','latencySeconds':0,'project':project}
 lane=LANES[p][project]
 if not lane.acquire(timeout=LANE_WAIT):
  return p,{'status':'BUSY','error':'PROVIDER_PROJECT_LANE_BUSY','latencySeconds':round(time.time()-st,2),'project':project,'retryable':True}
 got_global=False
 try:
  got_global=GLOBAL[p].acquire(timeout=LANE_WAIT)
  if not got_global:
   return p,{'status':'BUSY','error':'PROVIDER_GLOBAL_CAPACITY_BUSY','latencySeconds':round(time.time()-st,2),'project':project,'retryable':True}
  with ACTIVE_LOCK:ACTIVE[p][project]+=1
  forex=project=='FOREX'; role=FOREX_ROLE if forex else REVIEW_ROLE; instruction=str(e.get('instruction') or '').strip(); prompt=role+'\nPROVIDER_ROLE='+p+('\nINSTRUCTION='+instruction if instruction else '')+'\nEVIDENCE='+json.dumps(e,ensure_ascii=False,separators=(',',':'))
  try:
   if p=='claude':
    cmd=['claude','--model',CLAUDE_MODEL,'-p'] if forex else ['claude','--model',CLAUDE_MODEL,'-p','--disallowedTools','Read,Grep,Glob,Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch']; x=local(cmd,prompt)
   else:x=local(['/usr/bin/codex' if os.path.exists('/usr/bin/codex') else 'codex','exec','--model',CODEX_MODEL,'--ephemeral','--sandbox','read-only','--skip-git-repo-check','-'],prompt)
   now=int(time.time()*1000); LAST[p]={'state':'ONLINE','last_seen':now,'project':project,'error':None}; return p,{'status':'OK','review':x,'latencySeconds':round(time.time()-st,2),'last_seen':now,'project':project}
  except subprocess.TimeoutExpired:
   now=int(time.time()*1000);LAST[p]={'state':'DEGRADED','last_seen':now,'project':project,'error':'PROVIDER_TIMEOUT'};return p,{'status':'TIMEOUT','error':'PROVIDER_TIMEOUT','latencySeconds':round(time.time()-st,2),'project':project}
  except Exception as z:
   now=int(time.time()*1000);err=str(z);safe=err if len(err)<=1200 else err[:450]+' ... '+err[-700:];LAST[p]={'state':'DEGRADED','last_seen':now,'project':project,'error':safe};return p,{'status':'ERROR','error':safe,'latencySeconds':round(time.time()-st,2),'project':project}
 finally:
  if got_global:
   with ACTIVE_LOCK:ACTIVE[p][project]=max(0,ACTIVE[p][project]-1)
   GLOBAL[p].release()
  lane.release()
def run(e):
 out={}
 with ThreadPoolExecutor(max_workers=2) as pool:
  for f in as_completed([pool.submit(one,p,e) for p in PROVIDERS]):p,r=f.result();out[p]=r
 return out
def bybit_proxy(body):
 method=str(body.get('method') or '').upper(); path=str(body.get('path') or ''); query=str(body.get('query') or ''); raw=str(body.get('body') or ''); headers=body.get('headers') or {}
 if method not in BYBIT_ALLOWED_METHODS:return 405,{'ok':False,'error':'BYBIT_METHOD_NOT_ALLOWED','transport':'VPS_BYBIT_PRIVATE_PROXY'}
 if not path.startswith(BYBIT_ALLOWED_PREFIXES):return 403,{'ok':False,'error':'BYBIT_PATH_NOT_ALLOWED','path':path,'transport':'VPS_BYBIT_PRIVATE_PROXY'}
 safe_headers={k:str(v) for k,v in headers.items() if str(k).lower() in ('x-bapi-api-key','x-bapi-timestamp','x-bapi-recv-window','x-bapi-sign','content-type','accept','x-trading-runtime-contract')}
 if not all(k in {x.lower() for x in safe_headers} for k in ('x-bapi-api-key','x-bapi-timestamp','x-bapi-recv-window','x-bapi-sign')):return 400,{'ok':False,'error':'BYBIT_SIGNED_HEADERS_MISSING','transport':'VPS_BYBIT_PRIVATE_PROXY'}
 attempts=[]; last_status=502; last_body=None
 for base in BYBIT_BASES:
  attempts.append(base); url=base+path+(('?'+query) if method=='GET' and query else ''); data=None if method=='GET' else raw.encode(); req=urllib.request.Request(url,data=data,method=method,headers=safe_headers)
  try:
   with urllib.request.urlopen(req,timeout=25) as r:status=r.status; txt=r.read(2000000).decode(errors='replace')
  except urllib.error.HTTPError as e:status=e.code; txt=e.read(2000000).decode(errors='replace')
  except Exception as e:last_status=502; last_body={'retCode':None,'retMsg':'UPSTREAM_FETCH_FAILED:'+str(e)[:180]}; continue
  try:payload=json.loads(txt)
  except Exception:payload={'retCode':None,'retMsg':txt[:300] or ('HTTP_'+str(status))}
  last_status=status; last_body=payload
  if status not in (403,429):return 200,{'ok':status>=200 and status<300 and int(payload.get('retCode',-1))==0,'httpStatus':status,'upstream':payload,'base':base,'attempts':attempts,'transport':'VPS_BYBIT_PRIVATE_PROXY'}
 return 200,{'ok':False,'httpStatus':last_status,'upstream':last_body,'base':attempts[-1] if attempts else None,'attempts':attempts,'transport':'VPS_BYBIT_PRIVATE_PROXY'}
def health_payload():
 now=int(time.time()*1000);meta={'claude':CLAUDE_MODEL,'codex':CODEX_MODEL};p={};configured_count=0;online_recent=0;unknown=0
 with ACTIVE_LOCK:active={n:dict(ACTIVE[n]) for n in PROVIDERS}
 for n in PROVIDERS:
  conf=configured(n);configured_count+=int(conf);last=LAST[n];seen=last.get('last_seen');fresh=bool(seen and now-int(seen)<=HEALTH_STALE_MS);state=last.get('state') if conf else 'OFFLINE'
  if conf and state=='ONLINE' and fresh:online_recent+=1
  if conf and state=='UNKNOWN':unknown+=1
  p[n]={'configured':conf,'model':meta[n],'state':state,'last_seen':seen,'fresh':fresh,'lastProject':last.get('project'),'lastError':last.get('error'),'active':active[n]}
 if configured_count<2:health='BLOCKED'
 elif online_recent==2:health='READY'
 elif unknown>0 and all((p[n]['state'] in ('UNKNOWN','ONLINE')) for n in PROVIDERS):health='WARMING'
 else:health='DEGRADED'
 return {'ok':configured_count>=2,'ready':health=='READY','healthState':health,'service':'UNIFIED_2AI_BRIDGE','legacyServiceAlias':'UNIFIED_3AI_BRIDGE','mode':'PARALLEL_2AI_PROJECT_ISOLATED','isolationMode':'PROJECT_LANES_V1','providerCount':configured_count,'onlineRecentCount':online_recent,'requiredQuorum':2,'deepseekDisabled':True,'forexAutonomousMode':True,'bybitPrivateProxy':True,'laneWaitSeconds':LANE_WAIT,'healthStaleMs':HEALTH_STALE_MS,'timestamp':now,'providers':p}
class H(BaseHTTPRequestHandler):
 def sendj(self,c,o):
  b=json.dumps(o,ensure_ascii=False).encode();self.send_response(c);self.send_header('content-type','application/json');self.send_header('cache-control','no-store');self.send_header('content-length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  if self.path!='/health':return self.sendj(404,{'ok':False})
  self.sendj(200,health_payload())
 def do_POST(self):
  if not SECRET or self.headers.get('authorization','')!='Bearer '+SECRET:return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})
  try:
   n=int(self.headers.get('content-length','0')); body=json.loads(self.rfile.read(n) or b'{}')
   if self.path=='/bybit/private':code,out=bybit_proxy(body); return self.sendj(code,out)
   if self.path!='/review':return self.sendj(404,{'ok':False})
   e=body.get('evidence') or {};requested=[str(x).lower() for x in (e.get('requestedProviders') or PROVIDERS)];bad=set(requested)-set(PROVIDERS)
   if bad:return self.sendj(400,{'ok':False,'error':'ONLY_CLAUDE_CODEX_ALLOWED','rejectedProviders':sorted(bad),'deepseekDisabled':True})
   st=time.time();p=run(e);q=sum(1 for n in PROVIDERS if p.get(n,{}).get('status')=='OK');busy=any(p.get(n,{}).get('status')=='BUSY' for n in PROVIDERS);self.sendj(200 if q>=2 else (503 if busy else 502),{'ok':q>=2,'service':'UNIFIED_2AI_BRIDGE','legacyServiceAlias':'UNIFIED_3AI_BRIDGE','task_id':e.get('task_id'),'project':project_of(e),'quorum':q,'requiredQuorum':2,'providers':p,'decisionLatencyMs':round((time.time()-st)*1000),'deepseekDisabled':True,'isolationMode':'PROJECT_LANES_V1','retryable':busy})
  except Exception as z:self.sendj(500,{'ok':False,'error':str(z)[:500]})
 def log_message(self,*_):pass
if __name__=='__main__':
 if not SECRET:raise SystemExit('V11_AI_BRIDGE_SECRET_REQUIRED')
 ThreadingHTTPServer((HOST,PORT),H).serve_forever()
