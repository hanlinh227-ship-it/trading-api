#!/usr/bin/env python3
import json, os, random, time, importlib.util, hashlib
from pathlib import Path
from datetime import datetime, timezone
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('base50',HERE/'continuous_crypto_50d.py'); b=importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
from crypto_3ai_learner import learn
ROOT=Path(os.getenv('CRYPTO_V3_STATE_DIR','/var/lib/trading/crypto-50d-v3')); [p.mkdir(parents=True,exist_ok=True) for p in [ROOT,ROOT/'profiles',ROOT/'trades',ROOT/'reports',ROOT/'ai-learning']]
TARGET=float(os.getenv('CRYPTO_TARGET_WR','80')); DAYS=int(os.getenv('CRYPTO_WINDOW_DAYS','50')); MIN_PER_WINDOW=max(DAYS,int(os.getenv('CRYPTO_V3_MIN_TRADES_WINDOW','50'))); VAL_WINDOWS=max(3,int(os.getenv('CRYPTO_V3_VALIDATION_WINDOWS','3'))); WORST=float(os.getenv('CRYPTO_V3_WORST_WR','70')); FEE=float(os.getenv('CRYPTO_FEE_BPS_RT','10'))/10000; SLIP=float(os.getenv('CRYPTO_SLIPPAGE_BPS_RT','4'))/10000
AI_META={'providers':['claude','openai','deepseek'],'rule':'DEV_ONLY','quorum':2}
def now():return datetime.now(timezone.utc).isoformat()
def atomic(p,o): p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+'.tmp'); t.write_text(json.dumps(o,indent=2,sort_keys=True)); t.replace(p)
def append(p,o): p.parent.mkdir(parents=True,exist_ok=True); f=p.open('a'); f.write(json.dumps(o,separators=(',',':'))+'\n'); f.close()
def phash(p):return hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:16]
def quality(rows):
 bad=dup=gaps=0; prev=None
 for x in rows:
  if prev is not None:
   d=x[0]-prev
   if d<=0: dup+=1
   elif d!=900000:gaps+=max(1,d//900000-1)
  if x[2]<x[3] or x[1]<=0 or x[4]<=0:bad+=1
  prev=x[0]
 return {'rows':len(rows),'first':rows[0][0] if rows else None,'last':rows[-1][0] if rows else None,'duplicateOrNonMonotonic':dup,'missingBars':gaps,'badOHLC':bad,'materialGap':gaps>8 or bad>0 or dup>0}
def run(rows,start,end,p,rr,cost_mult=1.0,delay=0):
 c=[x[4] for x in rows];v=[x[5] for x in rows];ef=b.ema(c,p['fast']);es=b.ema(c,p['slow']);at=b.atr(rows);tr=[];i=max(p['slow'],p['lookback'],20)
 while i<len(rows)-3:
  if rows[i][0]<start:i+=1;continue
  if rows[i][0]>=end:break
  hi=max(x[2] for x in rows[i-p['lookback']:i]);lo=min(x[3] for x in rows[i-p['lookback']:i]);av=sum(v[i-20:i])/20;L=S=False;fam=p['family']
  if fam in ('trend_breakout','volatility_breakout'):L=c[i]>hi and ef[i]>es[i];S=c[i]<lo and ef[i]<es[i]
  elif fam in ('pullback','trend_continuation'):L=ef[i]>es[i] and rows[i][3]<=ef[i] and c[i]>ef[i];S=ef[i]<es[i] and rows[i][2]>=ef[i] and c[i]<ef[i]
  elif fam in ('mean_reclaim','regime_hybrid'):L=c[i]>ef[i] and c[i-1]<=ef[i-1] and ef[i]>es[i];S=c[i]<ef[i] and c[i-1]>=ef[i-1] and ef[i]<es[i]
  elif fam=='liquidity_sweep':L=rows[i][3]<lo and c[i]>lo and ef[i]>=es[i];S=rows[i][2]>hi and c[i]<hi and ef[i]<=es[i]
  if v[i]<av*p['vol_mult']:L=S=False
  if p['side']=='long':S=False
  if p['side']=='short':L=False
  side=1 if L else -1 if S else 0
  if not side:i+=1;continue
  ei=i+1+delay
  if ei>=len(rows) or rows[ei][0]>=end:break
  entry=rows[ei][1];risk=max(at[i]*p['atr_mult'],entry*.0015);sl=entry-side*risk;tp=entry+side*risk*rr;gross=None;xi=None;exitpx=None
  for j in range(ei,min(len(rows),ei+96)):
   h,l=rows[j][2],rows[j][3];hs=l<=sl if side==1 else h>=sl;ht=h>=tp if side==1 else l<=tp
   if hs:gross=-1;xi=j;exitpx=sl;break
   if ht:gross=rr;xi=j;exitpx=tp;break
  if gross is None:xi=min(len(rows)-1,ei+95);exitpx=rows[xi][4];gross=side*(exitpx-entry)/risk
  costs=entry*(FEE+SLIP)*cost_mult/risk;net=gross-costs;tr.append({'t':rows[ei][0],'side':'LONG' if side==1 else 'SHORT','entry':entry,'exit':exitpx,'sl':sl,'tp':tp,'grossR':gross,'costR':costs,'netR':net});i=xi+1
 wins=sum(x['netR']>0 for x in tr);n=len(tr);eq=peak=mxdd=streak=mxstreak=0
 for x in tr:
  eq+=x['netR'];peak=max(peak,eq);mxdd=max(mxdd,peak-eq);streak=streak+1 if x['netR']<=0 else 0;mxstreak=max(mxstreak,streak)
 pos=sum(x['netR'] for x in tr if x['netR']>0);neg=-sum(x['netR'] for x in tr if x['netR']<0)
 return {'trades':tr,'n':n,'wins':wins,'losses':n-wins,'wr':100*wins/n if n else 0,'netR':sum(x['netR'] for x in tr),'expectancy':sum(x['netR'] for x in tr)/n if n else 0,'profitFactor':pos/neg if neg else (999 if pos else 0),'maxDrawdownR':mxdd,'maxConsecutiveLosses':mxstreak,'entriesPerDay':n/DAYS}
def gate(z):return z['n']>=MIN_PER_WINDOW and z['wr']>=TARGET and z['expectancy']>0 and z['netR']>0
def perturb(p):
 out=[]
 for k,m in [('fast',1),('slow',2),('lookback',1)]:
  for d in (-m,m):q=dict(p);q[k]=max(5,int(q[k])+d);q['slow']=max(q['fast']+5,q['slow']);out.append(q)
 for k,m in [('atr_mult',.1),('vol_mult',.1)]:
  for d in (-m,m):q=dict(p);q[k]=max(.5,float(q[k])+d);out.append(q)
 return out
def loadlin(s):
 p=ROOT/'profiles'/f'{s}-lineage.json';return json.loads(p.read_text()) if p.exists() else {'symbol':s,'version':0,'current':None,'rejected':[]}
def stamp(state,sp,s=None,status='RESEARCH_RUNNING_V3'):
 state.update(status=status,currentSymbol=s,updatedAt=now(),targetWR=TARGET,minTradesPer50d=MIN_PER_WINDOW,validationWindows=VAL_WINDOWS,worstWindowWR=WORST,rrAllowed=[1,2],aiLearning=AI_META);atomic(sp,state);atomic(ROOT/'reports'/'current.json',state)
def main():
 valid=b.exchange_symbols();configured=b.SYMBOLS;active=[s for s in configured if s in valid];excluded=[{'symbol':s,'reason':'NO_BINANCE_USDT_PERPETUAL'} for s in configured if s not in valid];atomic(ROOT/'universe.json',{'configured':configured,'active':active,'excluded':excluded,'at':now()})
 sp=ROOT/'state.json';state=json.loads(sp.read_text()) if sp.exists() else {'version':'CRYPTO-50D-V3','epochStartedAt':now(),'round':0,'qualified':{},'history':[]};state.setdefault('qualified',{});state.setdefault('history',[]);stamp(state,sp,None,'INITIALIZING_V3')
 while True:
  unresolved=[s for s in active if s not in state['qualified']]
  if not unresolved:stamp(state,sp,None,'TARGET_ACHIEVED_ALL_USABLE_SYMBOLS');atomic(ROOT/'reports'/'final.json',state);time.sleep(3600);continue
  s=unresolved[state['round']%len(unresolved)];state['round']+=1;stamp(state,sp,s);seed=random.SystemRandom().randrange(1,2**31);lin=loadlin(s);p=(lin.get('current') or {}).get('profile') or b.profile(seed);rr0=(lin.get('current') or {}).get('rr')
  try:
   rows=b.klines(s);q=quality(rows);span=DAYS*86400000
   if len(rows)<DAYS*96*4 or q['materialGap']:raise RuntimeError('DATA_QUALITY_FAIL '+json.dumps(q))
   first,last=rows[0][0],rows[-1][0];split=first+int((last-first)*.60);vstart=split
   if split-first<span or last-span-vstart<VAL_WINDOWS*span:raise RuntimeError('INSUFFICIENT_DISJOINT_HISTORY')
   ds=random.Random(seed).randrange(first,split-span,900000);rrs=(rr0,) if rr0 in (1,2) else (1,2);devs=[]
   for rr in rrs:z=run(rows,ds,ds+span,p,rr);devs.append((gate(z),z['expectancy'],z['wr'],rr,z))
   _,_,_,rr,dev=max(devs,key=lambda x:(x[0],x[1],x[2]));passed=False;vals=[];stress={}
   if gate(dev):
    pool=[];x=vstart
    while x+span<=last:pool.append(x);x+=span
    rng=random.Random(seed^0xA55A);rng.shuffle(pool);starts=sorted(pool[:VAL_WINDOWS]);vals=[run(rows,x,x+span,p,rr) for x in starts]
    aggN=sum(x['n'] for x in vals);aggW=sum(x['wins'] for x in vals);aggR=sum(x['netR'] for x in vals);aggWR=100*aggW/aggN if aggN else 0
    baseok=len(vals)==VAL_WINDOWS and all(x['n']>=MIN_PER_WINDOW and x['netR']>0 for x in vals) and aggN>=MIN_PER_WINDOW*VAL_WINDOWS and aggWR>=TARGET and min(x['wr'] for x in vals)>=WORST and aggR>0
    if baseok:
     stress['cost1_5x']=[run(rows,x,x+span,p,rr,1.5) for x in starts];stress['cost2x']=[run(rows,x,x+span,p,rr,2.0) for x in starts];stress['delay1']=[run(rows,x,x+span,p,rr,1,1) for x in starts];stressok=all(sum(z['netR'] for z in arr)>0 for arr in stress.values());neigh=[]
     for pp in perturb(p):neigh.append(sum(z['netR'] for z in [run(rows,x,x+span,pp,rr) for x in starts]))
     stress['neighborNetR']=neigh;passed=stressok and sum(x>0 for x in neigh)>=max(1,int(len(neigh)*.6))
   rec={'round':state['round'],'at':now(),'symbol':s,'seed':seed,'profileVersion':lin['version'],'profileHash':phash(p),'profile':p,'rr':rr,'dataQuality':q,'dev':{k:v for k,v in dev.items() if k!='trades'},'validation':[{k:v for k,v in x.items() if k!='trades'} for x in vals],'stress':{k:([{kk:vv for kk,vv in z.items() if kk!='trades'} for z in v] if isinstance(v,list) and v and isinstance(v[0],dict) else v) for k,v in stress.items()},'pass':passed};append(ROOT/'trials.jsonl',rec);atomic(ROOT/'trades'/f'{s}-{state["round"]}-dev.json',dev['trades'])
   if passed:lock={'symbol':s,'version':lin['version'],'profile':p,'profileHash':phash(p),'rr':rr,'lockedAt':now(),'validation':rec['validation'],'stress':rec['stress']};state['qualified'][s]=lock;atomic(ROOT/'profiles'/f'{s}.json',lock);lin['status']='LOCKED'
   else:
    package={'symbol':s,'round':state['round'],'profile':p,'rr':rr,'targetWR':TARGET,'minTrades':MIN_PER_WINDOW,'windowDays':DAYS,'metrics':rec['dev'],'long':{},'short':{},'recentTrades':dev['trades'][-30:]}
    try:council=learn(package);lin['version']+=1;lin['current']={'version':lin['version'],'profile':council['consensus']['profile'],'rr':council['consensus']['rr'],'parentRound':state['round']};lin['lastCouncil']=council['consensus']
    except Exception as e:lin['lastAIError']={'at':now(),'error':repr(e)}
   atomic(ROOT/'profiles'/f'{s}-lineage.json',lin);state['history']=(state['history']+[rec])[-500:];stamp(state,sp,s)
  except Exception as e:
   er={'round':state['round'],'at':now(),'symbol':s,'error':repr(e),'pass':False};append(ROOT/'trials.jsonl',er);state['lastError']=er;stamp(state,sp,s,'RESEARCH_RUNNING_V3_WITH_LAST_ERROR');time.sleep(5)
  time.sleep(float(os.getenv('CRYPTO_ROUND_PAUSE_SECONDS','2')))
if __name__=='__main__':main()
