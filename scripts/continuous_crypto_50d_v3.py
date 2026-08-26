#!/usr/bin/env python3
import json,os,random,time,importlib.util,hashlib,math
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('base50',HERE/'continuous_crypto_50d.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
from crypto_3ai_learner import learn
ROOT=Path(os.getenv('CRYPTO_V3_STATE_DIR','/var/lib/trading/crypto-50d-v3'));[p.mkdir(parents=True,exist_ok=True) for p in [ROOT,ROOT/'profiles',ROOT/'trades',ROOT/'reports',ROOT/'ai-learning']]
TARGET=float(os.getenv('CRYPTO_TARGET_WR','80'));MAX_DAYS=int(os.getenv('CRYPTO_WINDOW_DAYS','50'));MIN_DAYS=max(7,int(os.getenv('CRYPTO_V3_MIN_WINDOW_DAYS','14')));MIN_PER_DAY=float(os.getenv('CRYPTO_V3_MIN_TRADES_PER_DAY','1'));VAL_WINDOWS=max(3,int(os.getenv('CRYPTO_V3_VALIDATION_WINDOWS','3')));WORST=float(os.getenv('CRYPTO_V3_WORST_WR','70'));FEE=float(os.getenv('CRYPTO_FEE_BPS_RT','10'))/10000;SLIP=float(os.getenv('CRYPTO_SLIPPAGE_BPS_RT','4'))/10000;AI_META={'providers':['claude','openai','deepseek'],'rule':'DEV_ONLY','quorum':2}
def now():return datetime.now(timezone.utc).isoformat()
def atomic(p,o):p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(o,indent=2,sort_keys=True));t.replace(p)
def append(p,o):p.parent.mkdir(parents=True,exist_ok=True);f=p.open('a');f.write(json.dumps(o,separators=(',',':'))+'\n');f.close()
def phash(p):return hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:16]
def defaults(p):
 q=dict(p or {});q.setdefault('family','trend_breakout');q.setdefault('fast',12);q.setdefault('slow',50);q.setdefault('lookback',20);q.setdefault('atr_mult',1.2);q.setdefault('vol_mult',1);q.setdefault('side','both');q.setdefault('rsi_long',52);q.setdefault('rsi_short',48);q.setdefault('body_min',0);q.setdefault('cooldown',0);q.setdefault('max_hold',96);return q
def quality(rows):
 bad=dup=gaps=0;prev=None
 for x in rows:
  if prev is not None:
   d=x[0]-prev
   if d<=0:dup+=1
   elif d!=900000:gaps+=max(1,d//900000-1)
  if x[2]<x[3] or min(x[1],x[4])<=0:bad+=1
  prev=x[0]
 return {'rows':len(rows),'first':rows[0][0] if rows else None,'last':rows[-1][0] if rows else None,'duplicateOrNonMonotonic':dup,'missingBars':gaps,'badOHLC':bad,'materialGap':bad>0 or dup>0 or gaps>max(8,int(len(rows)*.001))}
def choose_days(rows):
 if not rows:return 0
 hist=max(0,(rows[-1][0]-rows[0][0])//86400000)
 # Need 1 DEV + VAL_WINDOWS disjoint windows plus reserve. Prefer longest possible up to MAX_DAYS.
 usable=int(hist//(VAL_WINDOWS+2));return min(MAX_DAYS,max(0,usable))
def rsi(vals,n=14):
 out=[50.0]*len(vals);ag=al=0
 for i in range(1,len(vals)):
  d=vals[i]-vals[i-1];g=max(d,0);l=max(-d,0)
  if i<=n:ag+=g;al+=l
  if i==n:ag/=n;al/=n
  elif i>n:ag=(ag*(n-1)+g)/n;al=(al*(n-1)+l)/n
  if i>=n:out[i]=100 if al==0 else 100-100/(1+ag/al)
 return out
def run(rows,start,end,p,rr,days,cost_mult=1,delay=0):
 p=defaults(p);c=[x[4] for x in rows];v=[x[5] for x in rows];ef=b.ema(c,p['fast']);es=b.ema(c,p['slow']);at=b.atr(rows);rs=rsi(c);tr=[];i=max(p['slow'],p['lookback'],20);last_exit=-999999
 while i<len(rows)-3:
  if rows[i][0]<start:i+=1;continue
  if rows[i][0]>=end:break
  if i-last_exit<int(p['cooldown']):i+=1;continue
  hi=max(x[2] for x in rows[i-p['lookback']:i]);lo=min(x[3] for x in rows[i-p['lookback']:i]);av=sum(v[i-20:i])/20;body=abs(c[i]-rows[i][1]);bodyatr=body/max(at[i],1e-12);L=S=False;fam=p['family']
  if fam in ('trend_breakout','volatility_breakout'):L=c[i]>hi and ef[i]>es[i];S=c[i]<lo and ef[i]<es[i]
  elif fam in ('pullback','trend_continuation'):L=ef[i]>es[i] and rows[i][3]<=ef[i] and c[i]>ef[i];S=ef[i]<es[i] and rows[i][2]>=ef[i] and c[i]<ef[i]
  elif fam in ('mean_reclaim','regime_hybrid'):L=c[i]>ef[i] and c[i-1]<=ef[i-1] and ef[i]>es[i];S=c[i]<ef[i] and c[i-1]>=ef[i-1] and ef[i]<es[i]
  elif fam=='liquidity_sweep':L=rows[i][3]<lo and c[i]>lo and ef[i]>=es[i];S=rows[i][2]>hi and c[i]<hi and ef[i]<=es[i]
  L=L and rs[i]>=p['rsi_long'];S=S and rs[i]<=p['rsi_short']
  if v[i]<av*p['vol_mult'] or bodyatr<p['body_min']:L=S=False
  if p['side']=='long':S=False
  if p['side']=='short':L=False
  side=1 if L else -1 if S else 0
  if not side:i+=1;continue
  ei=i+1+delay
  if ei>=len(rows) or rows[ei][0]>=end:break
  entry=rows[ei][1];risk=max(at[i]*p['atr_mult'],entry*.0015);sl=entry-side*risk;tp=entry+side*risk*rr;gross=None;xi=None;exitpx=None;hold=max(8,min(192,int(p['max_hold'])))
  for j in range(ei,min(len(rows),ei+hold)):
   h,l=rows[j][2],rows[j][3];hs=l<=sl if side==1 else h>=sl;ht=h>=tp if side==1 else l<=tp
   if hs:gross=-1;xi=j;exitpx=sl;break
   if ht:gross=rr;xi=j;exitpx=tp;break
  if gross is None:xi=min(len(rows)-1,ei+hold-1);exitpx=rows[xi][4];gross=side*(exitpx-entry)/risk
  costs=entry*(FEE+SLIP)*cost_mult/risk;net=gross-costs;tr.append({'t':rows[ei][0],'side':'LONG' if side==1 else 'SHORT','entry':entry,'exit':exitpx,'sl':sl,'tp':tp,'grossR':gross,'costR':costs,'netR':net,'holdBars':xi-ei+1});last_exit=xi;i=xi+1
 wins=sum(x['netR']>0 for x in tr);n=len(tr);eq=peak=mxdd=streak=mxstreak=0
 for x in tr:eq+=x['netR'];peak=max(peak,eq);mxdd=max(mxdd,peak-eq);streak=streak+1 if x['netR']<=0 else 0;mxstreak=max(mxstreak,streak)
 pos=sum(x['netR'] for x in tr if x['netR']>0);neg=-sum(x['netR'] for x in tr if x['netR']<0);return {'trades':tr,'n':n,'wins':wins,'losses':n-wins,'wr':100*wins/n if n else 0,'netR':sum(x['netR'] for x in tr),'expectancy':sum(x['netR'] for x in tr)/n if n else 0,'profitFactor':pos/neg if neg else (999 if pos else 0),'maxDrawdownR':mxdd,'maxConsecutiveLosses':mxstreak,'entriesPerDay':n/max(days,1),'longN':sum(x['side']=='LONG' for x in tr),'shortN':sum(x['side']=='SHORT' for x in tr)}
def gate(z,days):return z['n']>=max(10,math.ceil(days*MIN_PER_DAY)) and z['wr']>=TARGET and z['expectancy']>0 and z['netR']>0
def perturb(p):
 p=defaults(p);out=[]
 for k,m in [('fast',1),('slow',2),('lookback',1),('cooldown',1),('max_hold',8)]:
  for d in (-m,m):q=dict(p);q[k]=max(0,int(q[k])+d);q['fast']=max(5,q['fast']);q['slow']=max(q['fast']+5,q['slow']);q['lookback']=max(5,q['lookback']);q['max_hold']=max(8,q['max_hold']);out.append(q)
 for k,m in [('atr_mult',.1),('vol_mult',.1),('rsi_long',2),('rsi_short',2),('body_min',.1)]:
  for d in (-m,m):q=dict(p);q[k]=float(q[k])+d;out.append(q)
 return out
def loadlin(s):
 p=ROOT/'profiles'/f'{s}-lineage.json';return json.loads(p.read_text()) if p.exists() else {'symbol':s,'version':0,'current':None,'rejected':[]}
def stamp(state,sp,s=None,status='RESEARCH_RUNNING_V3'):
 state.update(status=status,currentSymbol=s,updatedAt=now(),targetWR=TARGET,windowPolicy={'mode':'ADAPTIVE','minDays':MIN_DAYS,'maxDays':MAX_DAYS,'minTradesPerDay':MIN_PER_DAY},validationWindows=VAL_WINDOWS,worstWindowWR=WORST,rrAllowed=[1,2],aiLearning=AI_META);atomic(sp,state);atomic(ROOT/'reports'/'current.json',state)
def main():
 valid=b.exchange_symbols();configured=b.SYMBOLS;active=[s for s in configured if s in valid];excluded=[{'symbol':s,'reason':'NO_BINANCE_USDT_PERPETUAL'} for s in configured if s not in valid];atomic(ROOT/'universe.json',{'configured':configured,'active':active,'excluded':excluded,'at':now()})
 sp=ROOT/'state.json';state=json.loads(sp.read_text()) if sp.exists() else {'version':'CRYPTO-50D-V3','epochStartedAt':now(),'round':0,'qualified':{},'history':[]};state.setdefault('qualified',{});state.setdefault('history',[]);stamp(state,sp,None,'INITIALIZING_V3')
 while True:
  unresolved=[s for s in active if s not in state['qualified']]
  if not unresolved:stamp(state,sp,None,'TARGET_ACHIEVED_ALL_USABLE_SYMBOLS');atomic(ROOT/'reports'/'final.json',state);time.sleep(3600);continue
  s=unresolved[state['round']%len(unresolved)];state['round']+=1;stamp(state,sp,s);seed=random.SystemRandom().randrange(1,2**31);lin=loadlin(s);p=defaults((lin.get('current') or {}).get('profile') or b.profile(seed));rr0=(lin.get('current') or {}).get('rr')
  try:
   rows=b.klines(s);q=quality(rows);days=choose_days(rows)
   if q['materialGap']:raise RuntimeError('DATA_QUALITY_FAIL '+json.dumps(q))
   if days<MIN_DAYS:raise RuntimeError('INSUFFICIENT_HISTORY_FOR_MIN_WINDOW days='+str(days))
   span=days*86400000;first,last=rows[0][0],rows[-1][0];reserve=span*VAL_WINDOWS;dev_max=last-reserve-span
   if dev_max<=first:raise RuntimeError('INSUFFICIENT_ADAPTIVE_HISTORY')
   ds=random.Random(seed).randrange(first,dev_max,900000);rrs=(rr0,) if rr0 in (1,2) else (1,2);devs=[]
   for rr in rrs:z=run(rows,ds,ds+span,p,rr,days);devs.append((gate(z,days),z['expectancy'],z['wr'],rr,z))
   _,_,_,rr,dev=max(devs,key=lambda x:(x[0],x[1],x[2]));passed=False;vals=[];stress={}
   if gate(dev,days):
    starts=[last-span*(VAL_WINDOWS-i) for i in range(VAL_WINDOWS)];vals=[run(rows,x,x+span,p,rr,days) for x in starts];aggN=sum(x['n'] for x in vals);aggW=sum(x['wins'] for x in vals);aggR=sum(x['netR'] for x in vals);aggWR=100*aggW/aggN if aggN else 0;need=max(10,math.ceil(days*MIN_PER_DAY));baseok=len(vals)==VAL_WINDOWS and all(x['n']>=need and x['netR']>0 for x in vals) and aggWR>=TARGET and min(x['wr'] for x in vals)>=WORST and aggR>0
    if baseok:
     stress['cost1_5x']=[run(rows,x,x+span,p,rr,days,1.5) for x in starts];stress['cost2x']=[run(rows,x,x+span,p,rr,days,2) for x in starts];stress['delay1']=[run(rows,x,x+span,p,rr,days,1,1) for x in starts];stressok=all(sum(z['netR'] for z in a)>0 for a in stress.values());neigh=[sum(run(rows,x,x+span,pp,rr,days)['netR'] for x in starts) for pp in perturb(p)];stress['neighborNetR']=neigh;passed=stressok and sum(x>0 for x in neigh)>=max(1,int(len(neigh)*.6))
   rec={'round':state['round'],'at':now(),'symbol':s,'seed':seed,'windowDays':days,'profileVersion':lin['version'],'profileHash':phash(p),'profile':p,'rr':rr,'dataQuality':q,'dev':{k:v for k,v in dev.items() if k!='trades'},'validation':[{k:v for k,v in x.items() if k!='trades'} for x in vals],'stress':{k:([{kk:vv for kk,vv in z.items() if kk!='trades'} for z in v] if isinstance(v,list) and v and isinstance(v[0],dict) else v) for k,v in stress.items()},'pass':passed};append(ROOT/'trials.jsonl',rec);atomic(ROOT/'trades'/f'{s}-{state["round"]}-dev.json',dev['trades'])
   if passed:lock={'symbol':s,'version':lin['version'],'profile':p,'profileHash':phash(p),'rr':rr,'windowDays':days,'lockedAt':now(),'validation':rec['validation'],'stress':rec['stress']};state['qualified'][s]=lock;atomic(ROOT/'profiles'/f'{s}.json',lock);lin['status']='LOCKED'
   else:
    package={'symbol':s,'round':state['round'],'profile':p,'rr':rr,'targetWR':TARGET,'minTrades':max(10,math.ceil(days*MIN_PER_DAY)),'windowDays':days,'metrics':rec['dev'],'long':{'n':dev['longN']},'short':{'n':dev['shortN']},'recentTrades':dev['trades'][-30:]}
    try:council=learn(package);lin['version']+=1;lin['current']={'version':lin['version'],'profile':council['consensus']['profile'],'rr':council['consensus']['rr'],'parentRound':state['round']};lin['lastCouncil']=council['consensus'];lin.pop('lastAIError',None)
    except Exception as e:lin['lastAIError']={'at':now(),'error':repr(e)}
   atomic(ROOT/'profiles'/f'{s}-lineage.json',lin);state['history']=(state['history']+[rec])[-500:];stamp(state,sp,s)
  except Exception as e:
   er={'round':state['round'],'at':now(),'symbol':s,'error':repr(e),'pass':False};append(ROOT/'trials.jsonl',er);state['lastError']=er;stamp(state,sp,s,'RESEARCH_RUNNING_V3_WITH_LAST_ERROR');time.sleep(2)
  time.sleep(float(os.getenv('CRYPTO_ROUND_PAUSE_SECONDS','2')))
if __name__=='__main__':main()
