#!/usr/bin/env python3
import json, os, time
from pathlib import Path
from datetime import datetime, timezone
S=Path(os.getenv('CRYPTO_RESEARCH_STATE_DIR','/var/lib/trading/crypto-50d'))
OUT=Path(os.getenv('CRYPTO_PUBLIC_STATUS_PATH','/var/lib/trading/crypto-50d/public-status.json'))
def load(p,default=None):
 try:return json.loads(p.read_text())
 except:return default

def main():
 st=load(S/'state.json',{}) or {}; uni=load(S/'universe.json',{}) or {}
 profiles=[]
 for p in sorted((S/'profiles').glob('*-lineage.json')) if (S/'profiles').exists() else []:
  x=load(p,{}) or {}; cur=x.get('current') or {}; profiles.append({'symbol':x.get('symbol'),'version':x.get('version',0),'status':x.get('status','RESEARCHING'),'devFailures':x.get('devFailures',0),'family':(cur.get('profile') or {}).get('family'),'rr':cur.get('rr'),'lastCouncil':x.get('lastCouncil'),'lastAIError':x.get('lastAIError')})
 council=[]
 cp=S/'ai-learning'/'council.jsonl'
 if cp.exists():
  for line in cp.read_text().splitlines()[-20:]:
   try:
    x=json.loads(line); council.append({'at':x.get('at'),'symbol':x.get('symbol'),'fromRound':x.get('fromRound'),'providersOK':sorted((x.get('providers') or {}).keys()),'providerErrors':sorted((x.get('errors') or {}).keys()),'consensus':x.get('consensus')})
   except:pass
 q=st.get('qualified') or {}; total=len(uni.get('active') or [])
 out={'schema':'CRYPTO-50D-PUBLIC-V1','generatedAt':datetime.now(timezone.utc).isoformat(),'runner':{'version':st.get('version'),'status':st.get('status'),'round':st.get('round'),'currentSymbol':st.get('currentSymbol'),'updatedAt':st.get('updatedAt'),'targetWR':st.get('targetWR'),'windowDays':st.get('windowDays'),'rrAllowed':st.get('rrAllowed'),'aiLearning':st.get('aiLearning'),'lastError':st.get('lastError')},'universe':{'active':total,'unavailable':uni.get('unavailable',[])},'progress':{'qualifiedCount':len(q),'remainingCount':max(0,total-len(q)),'qualified':{k:{'version':v.get('version'),'rr':v.get('rr'),'profile':v.get('profile'),'validation':v.get('validation')} for k,v in q.items()}},'profiles':profiles,'recentCouncil':council}
 tmp=OUT.with_suffix('.tmp'); tmp.write_text(json.dumps(out,indent=2,sort_keys=True)); tmp.replace(OUT)
if __name__=='__main__':main()
