#!/usr/bin/env python3
import json, os
from pathlib import Path
from datetime import datetime, timezone
ROOT=Path(os.getenv('CRYPTO_V3_STATE_DIR','/var/lib/trading/crypto-50d-v3'))
def load(p,d):
 try:return json.loads(p.read_text())
 except:return d
def main():
 state=load(ROOT/'state.json',{}); uni=load(ROOT/'universe.json',{})
 trials=[]
 try:
  for line in (ROOT/'trials.jsonl').read_text().splitlines():
   try:trials.append(json.loads(line))
   except:pass
 except:pass
 completed=[x for x in trials if isinstance(x.get('dev'),dict) and 'n' in x['dev']]
 rejected=[x for x in trials if x.get('error')]
 ai=0
 try:ai=sum(1 for x in (ROOT/'ai-learning'/'council.jsonl').read_text().splitlines() if x.strip())
 except:pass
 latest={}
 for x in completed:latest[x.get('symbol')]=x
 report={'generatedAt':datetime.now(timezone.utc).isoformat(),'mode':'BACKTEST_ONLY_3AI_RESEARCH','version':state.get('version'),'status':state.get('status'),'round':state.get('round',0),'currentSymbol':state.get('currentSymbol'),'universe':{'configured':len(uni.get('configured',[])),'active':len(uni.get('active',[])),'excluded':uni.get('excluded',[])},'counts':{'attempts':len(trials),'devCompleted':len(completed),'dataOrRuntimeRejected':len(rejected),'aiCouncilRuns':ai,'qualified':len(state.get('qualified',{}))},'qualified':state.get('qualified',{}),'latestBySymbol':{s:{'round':x.get('round'),'rr':x.get('rr'),'pass':x.get('pass'),'dev':x.get('dev'),'validation':x.get('validation'),'stress':x.get('stress'),'profileHash':x.get('profileHash')} for s,x in latest.items()},'lastError':state.get('lastError')}
 print(json.dumps(report,indent=2,sort_keys=True))
if __name__=='__main__':main()
