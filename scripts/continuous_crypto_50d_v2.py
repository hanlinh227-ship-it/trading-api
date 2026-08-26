#!/usr/bin/env python3
# CRYPTO-50D-V2: persistent symbol-specific research with DEV-only 3AI learning.
import json, os, random, time, importlib.util
from pathlib import Path
BASEFILE=Path(__file__).with_name('continuous_crypto_50d.py')
spec=importlib.util.spec_from_file_location('base50',BASEFILE); b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
from crypto_3ai_learner import learn
STATE=b.STATE; TARGET=b.TARGET; MIN_TRADES=b.MIN_TRADES; WINDOW_DAYS=b.WINDOW_DAYS; PAUSE=b.PAUSE

def load_lineage(s):
 p=STATE/'profiles'/f'{s}-lineage.json'; return json.loads(p.read_text()) if p.exists() else {'symbol':s,'version':0,'current':None,'rejected':[],'devFailures':0}
def save_lineage(s,x): b.atomic(STATE/'profiles'/f'{s}-lineage.json',x)
def failure_package(symbol,roundno,p,rr,dev):
 ts=dev['trades']; longs=[x for x in ts if x['side']=='LONG']; shorts=[x for x in ts if x['side']=='SHORT']
 def stat(a):
  n=sum(1 for x in a if x['grossR']!=0); w=sum(1 for x in a if x['grossR']>0); return {'n':n,'wr':100*w/n if n else 0,'netR':sum(x['netR'] for x in a)}
 return {'symbol':symbol,'round':roundno,'profile':p,'rr':rr,'targetWR':TARGET,'minTrades':MIN_TRADES,'windowDays':WINDOW_DAYS,'metrics':{k:v for k,v in dev.items() if k!='trades'},'long':stat(longs),'short':stat(shorts),'recentTrades':ts[-30:]}
def main():
 valid=b.exchange_symbols(); universe=[s for s in b.SYMBOLS if s in valid]; unavailable=[s for s in b.SYMBOLS if s not in valid]
 statep=STATE/'state.json'; old=json.loads(statep.read_text()) if statep.exists() else {}
 state={'version':'CRYPTO-50D-V2','round':int(old.get('round',0)),'qualified':old.get('qualified',{}),'history':old.get('history',[]),'migratedFrom':old.get('version')}
 b.atomic(STATE/'universe.json',{'configured':b.SYMBOLS,'active':universe,'unavailable':unavailable,'checkedAt':b.now()})
 while True:
  unresolved=[s for s in universe if s not in state['qualified']]
  if not unresolved:
   state['status']='TARGET_ACHIEVED_ALL_SYMBOLS'; state['updatedAt']=b.now(); b.atomic(statep,state); b.atomic(STATE/'reports'/'final.json',state); time.sleep(3600); continue
  symbol=unresolved[state['round']%len(unresolved)]; state['round']+=1; seed=random.SystemRandom().randrange(1,2**31); lin=load_lineage(symbol)
  # Use council's previous DEV-only hypothesis; bootstrap randomly only once.
  p=(lin.get('current') or {}).get('profile') or b.profile(seed); forced_rr=(lin.get('current') or {}).get('rr')
  try:
   rows=b.klines(symbol); first,last=rows[0][0],rows[-1][0]; span=WINDOW_DAYS*86400000; split=first+int((last-first)*.75); maxdev=split-span
   if maxdev<=first: raise RuntimeError('insufficient history')
   ds=random.Random(seed).randrange(first,maxdev,900000); de=ds+span
   rrs=(forced_rr,) if forced_rr in (1,2) else (1,2); candidates=[]
   for rr0 in rrs:
    z=b.run(rows,ds,de,p,rr0); candidates.append((z['wr']>=TARGET and z['n']>=MIN_TRADES and z['expectancy']>0,z['expectancy'],z['wr'],rr0,z))
   _,_,_,rr,dev=max(candidates,key=lambda x:(x[0],x[1],x[2])); frozen=dev['n']>=MIN_TRADES and dev['wr']>=TARGET and dev['expectancy']>0
   val=None; passed=False; council=None
   if frozen:
    vmax=last-span; vs=random.Random(seed^0x5A5A5A5A).randrange(split,vmax,900000) if vmax>split else split
    val=b.run(rows,vs,vs+span,p,rr); passed=val['n']>=MIN_TRADES and val['wr']>=TARGET and val['expectancy']>0
   rec={'round':state['round'],'at':b.now(),'symbol':symbol,'seed':seed,'profileVersion':lin['version'],'profile':p,'rr':rr,'dev':{k:v for k,v in dev.items() if k!='trades'},'validation':({k:v for k,v in val.items() if k!='trades'} if val else None),'pass':passed}
   b.append(STATE/'trials.jsonl',rec); b.atomic(STATE/'trades'/f'{symbol}-{state["round"]}-dev.json',dev['trades'])
   if val:b.atomic(STATE/'trades'/f'{symbol}-{state["round"]}-val.json',val['trades'])
   if passed:
    locked={'symbol':symbol,'version':lin['version'],'lockedAt':b.now(),'profile':p,'rr':rr,'validation':rec['validation']}; state['qualified'][symbol]=locked; b.atomic(STATE/'profiles'/f'{symbol}.json',locked); lin['status']='LOCKED'
   else:
    if frozen and val:
     lin['rejected'].append({'version':lin['version'],'at':b.now(),'reason':'UNSEEN_VALIDATION_FAIL','validation':rec['validation']})
    # AI receives DEV only, even when validation failed. Validation is never included in package.
    package=failure_package(symbol,state['round'],p,rr,dev)
    try:
     council=learn(package); lin['version']+=1; lin['current']={'version':lin['version'],'parentRound':state['round'],'profile':council['consensus']['profile'],'rr':council['consensus']['rr'],'councilAt':council['at']}; lin['devFailures']=int(lin.get('devFailures',0))+1; lin['lastCouncil']={'at':council['at'],'quorum':council['consensus']['quorum'],'familyAgreement':council['consensus']['familyAgreement']}
    except Exception as aierr:
     lin['lastAIError']={'at':b.now(),'error':repr(aierr)}
   save_lineage(symbol,lin)
   rec['aiCouncil']=({'at':council['at'],'consensus':council['consensus']} if council else None)
   state['history']=(state.get('history',[])+[rec])[-500:]; state.update({'status':'RESEARCH_RUNNING_3AI','currentSymbol':symbol,'updatedAt':b.now(),'targetWR':TARGET,'windowDays':WINDOW_DAYS,'rrAllowed':[1,2],'aiLearning':{'providers':['claude','openai','deepseek'],'rule':'DEV_ONLY','quorum':2}}); b.atomic(statep,state); b.atomic(STATE/'reports'/'current.json',state)
  except Exception as e:
   er={'round':state['round'],'at':b.now(),'symbol':symbol,'error':repr(e),'pass':False}; b.append(STATE/'trials.jsonl',er); state['lastError']=er; state['updatedAt']=b.now(); b.atomic(statep,state); time.sleep(10)
  time.sleep(PAUSE)
if __name__=='__main__':main()
