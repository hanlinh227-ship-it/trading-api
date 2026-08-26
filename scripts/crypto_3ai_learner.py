#!/usr/bin/env python3
import json, os, re, urllib.request
from datetime import datetime, timezone
from pathlib import Path

STATE=Path(os.getenv('CRYPTO_RESEARCH_STATE_DIR','/var/lib/trading/crypto-50d'))
TIMEOUT=int(os.getenv('CRYPTO_AI_TIMEOUT_SECONDS','60'))
MODELS={
 'claude':os.getenv('CRYPTO_CLAUDE_MODEL','claude-sonnet-4-20250514'),
 'openai':os.getenv('CRYPTO_OPENAI_MODEL','gpt-5.2'),
 'deepseek':os.getenv('CRYPTO_DEEPSEEK_MODEL','deepseek-chat')}
ALLOWED_FAMILIES=['trend_breakout','pullback','mean_reclaim','trend_continuation','liquidity_sweep','volatility_breakout','regime_hybrid']

def now(): return datetime.now(timezone.utc).isoformat()
def post(url,headers,body):
 req=urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers,method='POST')
 with urllib.request.urlopen(req,timeout=TIMEOUT) as r:return json.load(r)
def text_json(s):
 s=s.strip(); s=re.sub(r'^```(?:json)?\s*|\s*```$','',s,flags=re.I|re.S)
 a=s.find('{'); b=s.rfind('}');
 if a<0 or b<a: raise ValueError('AI_NO_JSON')
 return json.loads(s[a:b+1])
def claude(prompt):
 key=os.getenv('ANTHROPIC_API_KEY');
 if not key: raise RuntimeError('ANTHROPIC_API_KEY_MISSING')
 b=post('https://api.anthropic.com/v1/messages',{'content-type':'application/json','x-api-key':key,'anthropic-version':'2023-06-01'}, {'model':MODELS['claude'],'max_tokens':1200,'system':'You are a quantitative crypto strategy researcher. Never optimize on validation data. Return JSON only.','messages':[{'role':'user','content':prompt}]})
 return text_json(''.join(x.get('text','') for x in b.get('content',[]) if x.get('type')=='text'))
def openai(prompt):
 key=os.getenv('OPENAI_API_KEY');
 if not key: raise RuntimeError('OPENAI_API_KEY_MISSING')
 b=post(os.getenv('OPENAI_API_URL','https://api.openai.com/v1/chat/completions'),{'content-type':'application/json','authorization':'Bearer '+key},{'model':MODELS['openai'],'messages':[{'role':'system','content':'You are a quantitative crypto strategy researcher. Never optimize on validation data. Return JSON only.'},{'role':'user','content':prompt}]})
 return text_json(b['choices'][0]['message']['content'])
def deepseek(prompt):
 key=os.getenv('DEEPSEEK_API_KEY');
 if not key: raise RuntimeError('DEEPSEEK_API_KEY_MISSING')
 b=post(os.getenv('DEEPSEEK_API_URL','https://api.deepseek.com/chat/completions'),{'content-type':'application/json','authorization':'Bearer '+key},{'model':MODELS['deepseek'],'messages':[{'role':'system','content':'You are a quantitative crypto strategy researcher. Never optimize on validation data. Return JSON only.'},{'role':'user','content':prompt}],'temperature':0.2})
 return text_json(b['choices'][0]['message']['content'])
def sanitize(p,old):
 q=dict(old); q.update({k:v for k,v in p.items() if k in {'family','fast','slow','lookback','atr_mult','vol_mult','side'}})
 if q.get('family') not in ALLOWED_FAMILIES:q['family']=old.get('family','trend_breakout')
 q['fast']=max(5,min(40,int(q.get('fast',12)))); q['slow']=max(q['fast']+5,min(160,int(q.get('slow',50))))
 q['lookback']=max(5,min(64,int(q.get('lookback',20)))); q['atr_mult']=max(.5,min(3,float(q.get('atr_mult',1.2))))
 q['vol_mult']=max(.5,min(2.5,float(q.get('vol_mult',1)))); q['side']=q.get('side') if q.get('side') in ['both','long','short'] else 'both'; return q
def learn(package):
 prompt='''Analyze ONLY this DEV failure package. Propose the next profile for this symbol. Do not use or infer unseen validation. Target is robust >=80% win rate at RR exactly 1 or 2, but never fabricate performance. You may change strategy family. Return JSON: {"diagnosis":"brief","confidence":0..1,"rr":1_or_2,"profile":{"family":"...","fast":int,"slow":int,"lookback":int,"atr_mult":number,"vol_mult":number,"side":"both|long|short"}}. Package:\n'''+json.dumps(package,separators=(',',':'))
 votes={}; errors={}
 for name,fn in [('claude',claude),('openai',openai),('deepseek',deepseek)]:
  try:votes[name]=fn(prompt)
  except Exception as e:errors[name]=repr(e)
 if len(votes)<2: raise RuntimeError('AI_QUORUM_FAILED '+json.dumps(errors))
 old=package['profile']; proposals=[]
 for name,v in votes.items():
  proposals.append((float(v.get('confidence',0)),name,sanitize(v.get('profile',{}),old),1 if int(v.get('rr',package.get('rr',1)))==1 else 2))
 # consensus by family+RR when possible; otherwise highest-confidence proposal. Backtester remains authority.
 groups={}
 for x in proposals:groups.setdefault((x[2]['family'],x[3]),[]).append(x)
 bestgroup=max(groups.values(),key=lambda g:(len(g),sum(x[0] for x in g)))
 chosen=max(bestgroup,key=lambda x:x[0]) if len(bestgroup)>=2 else max(proposals,key=lambda x:x[0])
 out={'at':now(),'symbol':package['symbol'],'fromRound':package['round'],'providers':votes,'errors':errors,'consensus':{'quorum':len(votes),'familyAgreement':len(bestgroup),'chosenProvider':chosen[1],'profile':chosen[2],'rr':chosen[3]},'antiOverfit':'DEV_ONLY'}
 (STATE/'ai-learning').mkdir(parents=True,exist_ok=True)
 with (STATE/'ai-learning'/'council.jsonl').open('a') as f:f.write(json.dumps(out,separators=(',',':'))+'\n')
 return out

if __name__=='__main__':
 print(json.dumps(learn(json.load(__import__('sys').stdin)),indent=2))
