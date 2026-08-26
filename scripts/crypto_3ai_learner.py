#!/usr/bin/env python3
import json, os, re, urllib.request, math
from datetime import datetime, timezone
from pathlib import Path
STATE=Path(os.getenv('CRYPTO_V3_STATE_DIR',os.getenv('CRYPTO_RESEARCH_STATE_DIR','/var/lib/trading/crypto-50d-v3')))
TIMEOUT=int(os.getenv('CRYPTO_AI_TIMEOUT_SECONDS','60'))
MODELS={'claude':os.getenv('CRYPTO_CLAUDE_MODEL','claude-sonnet-4-20250514'),'openai':os.getenv('CRYPTO_OPENAI_MODEL','gpt-5.2'),'deepseek':os.getenv('CRYPTO_DEEPSEEK_MODEL','deepseek-chat')}
ALLOWED_FAMILIES=['trend_breakout','pullback','mean_reclaim','trend_continuation','liquidity_sweep','volatility_breakout','regime_hybrid']
BOUNDS={'fast':(5,40),'slow':(15,160),'lookback':(5,64),'atr_mult':(.5,3.0),'vol_mult':(.5,2.5),'rsi_long':(45,70),'rsi_short':(30,55),'body_min':(.0,1.5),'cooldown':(0,16),'max_hold':(8,192)}
def now():return datetime.now(timezone.utc).isoformat()
def post(url,headers,body):
 req=urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers,method='POST')
 with urllib.request.urlopen(req,timeout=TIMEOUT) as r:return json.load(r)
def text_json(s):
 s=re.sub(r'^```(?:json)?\s*|\s*```$','',str(s).strip(),flags=re.I|re.S);a=s.find('{');z=s.rfind('}')
 if a<0 or z<a:raise ValueError('AI_NO_JSON')
 return json.loads(s[a:z+1])
def claude(prompt):
 key=os.getenv('ANTHROPIC_API_KEY');
 if not key:raise RuntimeError('ANTHROPIC_API_KEY_MISSING')
 x=post('https://api.anthropic.com/v1/messages',{'content-type':'application/json','x-api-key':key,'anthropic-version':'2023-06-01'},{'model':MODELS['claude'],'max_tokens':1600,'system':'Quant crypto researcher. DEV evidence only. JSON only. Never invent performance.','messages':[{'role':'user','content':prompt}]});return text_json(''.join(y.get('text','') for y in x.get('content',[]) if y.get('type')=='text'))
def openai(prompt):
 key=os.getenv('OPENAI_API_KEY');
 if not key:raise RuntimeError('OPENAI_API_KEY_MISSING')
 x=post(os.getenv('OPENAI_API_URL','https://api.openai.com/v1/chat/completions'),{'content-type':'application/json','authorization':'Bearer '+key},{'model':MODELS['openai'],'messages':[{'role':'system','content':'Quant crypto researcher. DEV evidence only. JSON only. Never invent performance.'},{'role':'user','content':prompt}]});return text_json(x['choices'][0]['message']['content'])
def deepseek(prompt):
 key=os.getenv('DEEPSEEK_API_KEY');
 if not key:raise RuntimeError('DEEPSEEK_API_KEY_MISSING')
 x=post(os.getenv('DEEPSEEK_API_URL','https://api.deepseek.com/chat/completions'),{'content-type':'application/json','authorization':'Bearer '+key},{'model':MODELS['deepseek'],'messages':[{'role':'system','content':'Quant crypto researcher. DEV evidence only. JSON only. Never invent performance.'},{'role':'user','content':prompt}],'temperature':.2});return text_json(x['choices'][0]['message']['content'])
def finite(v,f):
 try:x=float(v);return x if math.isfinite(x) else f
 except:return f
def sanitize(p,old):
 q=dict(old);allowed={'family','fast','slow','lookback','atr_mult','vol_mult','side','rsi_long','rsi_short','body_min','cooldown','max_hold'};q.update({k:v for k,v in (p or {}).items() if k in allowed})
 if q.get('family') not in ALLOWED_FAMILIES:q['family']=old.get('family','trend_breakout')
 for k,(lo,hi) in BOUNDS.items():
  base=old.get(k,{'fast':12,'slow':50,'lookback':20,'atr_mult':1.2,'vol_mult':1,'rsi_long':52,'rsi_short':48,'body_min':0,'cooldown':0,'max_hold':96}[k]);x=max(lo,min(hi,finite(q.get(k),base)));q[k]=int(round(x)) if k in ('fast','slow','lookback','cooldown','max_hold') else x
 q['slow']=max(q['fast']+5,q['slow']);q['side']=q.get('side') if q.get('side') in ('both','long','short') else 'both';return q
def learn(package):
 prompt='''Analyze ONLY the supplied DEV failure. This is V3 research inheriting V77 bounded adaptive-tuning principles: diagnose regime mismatch, direction asymmetry, signal frequency, false breakouts, volatility/volume filters, momentum confirmation, cooldown and holding horizon before proposing changes. Target >=1 resolved trade/day average, robust WR >=80%, RR exactly 1 or 2. Do not optimize on or infer validation. Never fabricate results. Return JSON only: {"diagnosis":"...","failureModes":["..."],"confidence":0..1,"rr":1_or_2,"profile":{"family":"trend_breakout|pullback|mean_reclaim|trend_continuation|liquidity_sweep|volatility_breakout|regime_hybrid","fast":int,"slow":int,"lookback":int,"atr_mult":number,"vol_mult":number,"rsi_long":number,"rsi_short":number,"body_min":number,"cooldown":int,"max_hold":int,"side":"both|long|short"}}. DEV package:\n'''+json.dumps(package,separators=(',',':'))
 votes={};errors={}
 for name,fn in [('claude',claude),('openai',openai),('deepseek',deepseek)]:
  try:votes[name]=fn(prompt)
  except Exception as e:errors[name]=repr(e)
 if len(votes)<2:raise RuntimeError('AI_QUORUM_FAILED '+json.dumps(errors))
 old=package['profile'];props=[]
 for name,v in votes.items():
  conf=max(0,min(1,finite(v.get('confidence'),0)));rr=1 if int(finite(v.get('rr',package.get('rr',1)),1))==1 else 2;props.append((conf,name,sanitize(v.get('profile'),old),rr))
 groups={}
 for x in props:groups.setdefault((x[2]['family'],x[3]),[]).append(x)
 best=max(groups.values(),key=lambda g:(len(g),sum(x[0] for x in g)));chosen=max(best,key=lambda x:x[0]) if len(best)>=2 else max(props,key=lambda x:x[0])
 out={'at':now(),'symbol':package['symbol'],'fromRound':package['round'],'providers':votes,'errors':errors,'consensus':{'quorum':len(votes),'familyAgreement':len(best),'chosenProvider':chosen[1],'profile':chosen[2],'rr':chosen[3]},'guardrails':{'boundedAdaptiveTuning':True,'validationVisible':False,'tradeAuthority':False,'deployAuthority':False},'antiOverfit':'DEV_ONLY'}
 (STATE/'ai-learning').mkdir(parents=True,exist_ok=True)
 with (STATE/'ai-learning'/'council.jsonl').open('a') as f:f.write(json.dumps(out,separators=(',',':'))+'\n')
 return out
if __name__=='__main__':print(json.dumps(learn(json.load(__import__('sys').stdin)),indent=2))
