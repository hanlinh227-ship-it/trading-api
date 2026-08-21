#!/usr/bin/env python3
import json,os,subprocess,sys,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
SECRET=os.environ.get('V11_AI_BRIDGE_SECRET','').strip()
HOST=os.environ.get('V11_AI_BRIDGE_HOST','127.0.0.1')
PORT=int(os.environ.get('V11_AI_BRIDGE_PORT','8789'))
CLAUDE_MODEL=os.environ.get('V11_CLAUDE_MODEL','sonnet')
CODEX_MODEL=os.environ.get('V11_CODEX_MODEL','gpt-5.6-sol')
TIMEOUT=int(os.environ.get('V11_AI_TIMEOUT','60'))
ROLE='''V11 MANUAL WHOLE-MARKET MARKET HUNTER. Review only supplied fresh candidates. This is an on-demand second opinion, not an automatic signal authority and not execution. Pick immediate MARKET suitability only. Never invent missing data. Return JSON: {"direction":"LONG|SHORT|WAIT","confidence":0-100,"hardRisk":[],"evidence":[],"reason":"..."}. If current evidence is insufficient for immediate MARKET, return WAIT.'''
def extract(s):
 s=(s or '').strip();a=s.find('{');b=s.rfind('}')
 if a<0 or b<=a:raise ValueError('JSON_NOT_FOUND')
 return json.loads(s[a:b+1])
def run(cmd,prompt):
 p=subprocess.run(cmd+[prompt],capture_output=True,text=True,timeout=TIMEOUT)
 if p.returncode:raise RuntimeError((p.stderr or p.stdout)[-1000:])
 return extract(p.stdout)
def review(provider,evidence):
 prompt=ROLE+'\nEVIDENCE='+json.dumps(evidence,ensure_ascii=False,separators=(',',':'))
 if provider=='claude':return run(['claude','--model',CLAUDE_MODEL,'-p'],prompt)
 if provider=='codex':return run(['/usr/bin/codex','exec','--model',CODEX_MODEL,'--ephemeral','--sandbox','read-only','--skip-git-repo-check'],prompt)
 raise ValueError('UNKNOWN_PROVIDER')
class H(BaseHTTPRequestHandler):
 def sendj(self,code,obj):
  raw=json.dumps(obj,ensure_ascii=False).encode();self.send_response(code);self.send_header('content-type','application/json');self.send_header('content-length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if self.path!='/health':return self.sendj(404,{'ok':False})
  self.sendj(200,{'ok':True,'service':'V11_MANUAL_AI_BRIDGE','claude':True,'codex':True,'onDemandOnly':True})
 def do_POST(self):
  if self.path!='/review':return self.sendj(404,{'ok':False})
  if not SECRET or self.headers.get('authorization','')!='Bearer '+SECRET:return self.sendj(401,{'ok':False,'error':'UNAUTHORIZED'})
  try:
   n=int(self.headers.get('content-length','0'));body=json.loads(self.rfile.read(n) or b'{}');e=body.get('evidence') or {};out={}
   for provider in ('claude','codex'):
    t=time.time()
    try:out[provider]={'status':'OK','latencySeconds':round(time.time()-t,2),'review':review(provider,e)}
    except subprocess.TimeoutExpired:out[provider]={'status':'TIMEOUT','latencySeconds':round(time.time()-t,2)}
    except Exception as x:out[provider]={'status':'ERROR','latencySeconds':round(time.time()-t,2),'error':str(x)[:300]}
   self.sendj(200,{'ok':all(x['status']=='OK' for x in out.values()),'providers':out})
  except Exception as x:self.sendj(400,{'ok':False,'error':str(x)[:300]})
 def log_message(self,*args):pass
if __name__=='__main__':
 if not SECRET:raise SystemExit('V11_AI_BRIDGE_SECRET required')
 print(f'V11 manual AI bridge listening {HOST}:{PORT}',flush=True);ThreadingHTTPServer((HOST,PORT),H).serve_forever()
