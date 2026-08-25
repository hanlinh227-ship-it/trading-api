#!/usr/bin/env python3
import os,json,math,random,time,urllib.parse,urllib.request,http.client
from datetime import datetime,timedelta,timezone
from collections import defaultdict

KEY=os.environ.get('TWELVEDATA_API_KEY','').strip()
if not KEY: raise SystemExit('TWELVEDATA_API_KEY missing')
OUT='data/forex-twelvedata-walkforward-latest.json'
SYMS=['EUR/USD','GBP/USD','USD/JPY','USD/CHF','AUD/USD','NZD/USD','USD/CAD','EUR/JPY','GBP/JPY','EUR/GBP','XAU/USD']
SEED=int(os.environ.get('BACKTEST_SEED') or random.SystemRandom().randrange(1,2**31-1)); RNG=random.Random(SEED)
WINDOWS=int(os.environ.get('BACKTEST_WINDOWS','2')); DAYS=int(os.environ.get('BACKTEST_WINDOW_DAYS','16'))
MIN_TEST_DAYS=int(os.environ.get('BACKTEST_MIN_TEST_DAYS','8')); TARGET=float(os.environ.get('BACKTEST_TARGET_WR','80'))
START=datetime(2025,1,6,tzinfo=timezone.utc); END=datetime(2026,7,31,tzinfo=timezone.utc)
HOURS=(6,7,8,9,10,12,13,14,15,16); STOPS=(0.8,1.0,1.2,1.5,1.8,2.2); RRS=(1,2)

def f(x,d=0.0):
 try:return float(x)
 except:return d

def ema(xs,p):
 if not xs:return []
 k=2/(p+1);out=[];e=xs[0]
 for x in xs:e=x*k+e*(1-k);out.append(e)
 return out

def atr(rows,p=14):
 out=[0.0]*len(rows);trs=[]
 for i,r in enumerate(rows):
  tr=r['h']-r['l'] if i==0 else max(r['h']-r['l'],abs(r['h']-rows[i-1]['c']),abs(r['l']-rows[i-1]['c']))
  trs.append(tr);out[i]=sum(trs[max(0,i-p+1):i+1])/min(p,i+1)
 return out

def rsi(cs,p=14):
 out=[50.0]*len(cs);g=[];l=[]
 for i in range(1,len(cs)):
  d=cs[i]-cs[i-1];g.append(max(d,0));l.append(max(-d,0))
  if i>=p:
   ga=sum(g[i-p:i])/p;lo=sum(l[i-p:i])/p;out[i]=100 if lo==0 else 100-100/(1+ga/lo)
 return out

def fetch(sym,a,b):
 q=urllib.parse.urlencode({'symbol':sym,'interval':'5min','start_date':a.strftime('%Y-%m-%d %H:%M:%S'),'end_date':b.strftime('%Y-%m-%d %H:%M:%S'),'outputsize':5000,'timezone':'UTC','apikey':KEY})
 url='https://api.twelvedata.com/time_series?'+q
 err=None
 for attempt in range(5):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'TradingProjectWalkForward/2.0','Accept':'application/json'})
   with urllib.request.urlopen(req,timeout=60) as r: raw=r.read()
   j=json.loads(raw.decode('utf-8'))
   if j.get('status')=='error' or 'values' not in j: raise RuntimeError(f'{sym}: {j}')
   rows=[]
   for x in reversed(j['values']):
    rows.append({'t':datetime.strptime(x['datetime'],'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc),'o':f(x['open']),'h':f(x['high']),'l':f(x['low']),'c':f(x['close'])})
   return rows
  except Exception as e:
   err=e;time.sleep(3*(attempt+1))
 raise RuntimeError(f'{sym} TwelveData failed after retries: {err}')

def enrich(rows):
 cs=[x['c'] for x in rows];e8=ema(cs,8);e20=ema(cs,20);e50=ema(cs,50);aa=atr(rows,14);rr=rsi(cs,14)
 for i,x in enumerate(rows):x.update(e8=e8[i],e20=e20[i],e50=e50[i],atr=aa[i],rsi=rr[i])
 return rows

def day_groups(rows):
 g=defaultdict(list)
 for r in rows:g[r['t'].date().isoformat()].append(r)
 return {k:v for k,v in g.items() if len(v)>=120}

def idx_for_hour(rows,h):
 for i,r in enumerate(rows):
  if r['t'].hour==h and r['t'].minute>=0 and i>=48:return i
 return None

def features(rows,i,side,stop,rr):
 r=rows[i];a=max(r['atr'],1e-12);c=r['c'];p12=rows[max(0,i-12)]['c'];p36=rows[max(0,i-36)]['c'];past=rows[:i+1]
 hi=max(x['h'] for x in past);lo=min(x['l'] for x in past);pos=(c-lo)/max(hi-lo,1e-12)
 return [
  side*(r['e8']-r['e20'])/a,
  side*(r['e20']-r['e50'])/a,
  side*(c-p12)/a,
  side*(c-p36)/a,
  side*(r['rsi']-50)/25,
  side*(c-r['e20'])/a,
  (pos-.5)*side*2,
  min(3.0,a/max(abs(c),1e-12)*10000)/3,
  math.sin(2*math.pi*r['t'].hour/24),math.cos(2*math.pi*r['t'].hour/24),
  (stop-1.5)/0.8,(rr-1.5)/.5
 ]

def outcome(rows,i,side,stop,rr):
 r=rows[i];dist=max(r['atr']*stop,1e-12);entry=r['c'];sl=entry-side*dist;tp=entry+side*dist*rr;mfe=mae=0
 for z in rows[i+1:]:
  fav=z['h']-entry if side>0 else entry-z['l'];adv=entry-z['l'] if side>0 else z['h']-entry
  mfe=max(mfe,fav/dist);mae=max(mae,adv/dist)
  hs=z['l']<=sl if side>0 else z['h']>=sl;ht=z['h']>=tp if side>0 else z['l']<=tp
  if hs and ht:return 0,-1.0,mfe,mae,'SL_SAME_BAR_PESSIMISTIC'
  if hs:return 0,-1.0,mfe,mae,'SL'
  if ht:return 1,float(rr),mfe,mae,'TP'
 return 0,-1.0,mfe,mae,'TIMEOUT_AS_LOSS'

def samples_for_day(rows):
 s=[]
 for h in HOURS:
  i=idx_for_hour(rows,h)
  if i is None:continue
  for side in (-1,1):
   for stop in STOPS:
    for rr in RRS:
     y,r,mfe,mae,why=outcome(rows,i,side,stop,rr)
     s.append({'x':features(rows,i,side,stop,rr),'y':y,'r':r,'h':h,'side':side,'stop':stop,'rr':rr,'mfe':mfe,'mae':mae,'why':why})
 return s

def dist(a,b):
 weights=(1.15,1.15,.9,.7,.65,.8,.55,.25,.2,.2,.6,.8)
 return sum(w*(x-y)*(x-y) for w,x,y in zip(weights,a,b))

def predict(x,train,k=21):
 ds=sorted(((dist(x,z['x']),z['y']) for z in train),key=lambda q:q[0])[:min(k,len(train))]
 if not ds:return .5
 num=1.5;den=3.0
 for d,y in ds:
  w=1/(0.08+d);num+=w*y;den+=w
 return num/den

def choose_trade(rows,train):
 candidates=[]
 for h in HOURS:
  i=idx_for_hour(rows,h)
  if i is None:continue
  for side in (-1,1):
   for stop in STOPS:
    for rr in RRS:
     x=features(rows,i,side,stop,rr);pr=predict(x,train)
     # Require positive model edge preference, but always choose one due quota.
     edge=pr*(rr+1)-1
     trend_align=x[1]
     quality=edge+.055*trend_align-.02*abs(x[5])+.012*(rr==2)
     candidates.append((quality,pr,i,side,stop,rr,x))
 if not candidates:return None
 quality,pr,i,side,stop,rr,x=max(candidates,key=lambda q:q[0]);y,r,mfe,mae,why=outcome(rows,i,side,stop,rr);e=rows[i]
 return {'day':e['t'].date().isoformat(),'entry_time':e['t'].isoformat(),'side':'BUY' if side>0 else 'SELL','rr':rr,'stopAtr':stop,'predictedWinProb':round(pr,4),'modelEdge':round(pr*(rr+1)-1,4),'result':'WIN' if y else 'LOSS','r':r,'mfeR':round(mfe,3),'maeR':round(mae,3),'exitReason':why}

def metrics(ts):
 n=len(ts);w=sum(x['result']=='WIN' for x in ts);return {'trades':n,'wins':w,'losses':n-w,'winrate':round(100*w/n,2) if n else 0,'avgR':round(sum(x['r'] for x in ts)/n,3) if n else 0,'rr1Trades':sum(x['rr']==1 for x in ts),'rr2Trades':sum(x['rr']==2 for x in ts)}

def random_window():
 span=(END-START).days-DAYS;a=START+timedelta(days=RNG.randint(0,max(1,span)));return a,a+timedelta(days=DAYS)

windows=sorted([random_window() for _ in range(WINDOWS)],key=lambda z:z[0])
report={'version':'FOREX-TWELVEDATA-WALKFORWARD-2','seed':SEED,'generatedAt':datetime.now(timezone.utc).isoformat(),'rules':{'source':'Twelve Data 5min','noLookahead':True,'learner':'per-symbol expanding KNN pattern learner','sameBarSLTP':'SL_FIRST_PESSIMISTIC','timeouts':'LOSS','rrAllowed':[1,2],'minOneTradePerTestDay':True,'targetWinratePctStrictlyGreaterThan':TARGET,'holdout':'each random window uses only its own 60% prefix for initial training; test days are sequential and become learnable only after that day closes'},'windows':[{'start':a.isoformat(),'end':b.isoformat()} for a,b in windows],'symbols':{},'pass':False}
allpass=True
for sym in SYMS:
 trades=[];source=[];data_error=None
 try:
  for wi,(a,b) in enumerate(windows):
   rows=enrich(fetch(sym,a,b));g=day_groups(rows);days=sorted(g);cut=max(3,int(len(days)*.60));tr=days[:cut];te=days[cut:];train=[]
   for d in tr:train.extend(samples_for_day(g[d]))
   wintr=[]
   for d in te:
    t=choose_trade(g[d],train)
    if t:trades.append(t);wintr.append(t)
    # Online learning becomes available only after the entire day has completed.
    train.extend(samples_for_day(g[d]))
   source.append({'window':wi,'bars':len(rows),'trainDays':len(tr),'testDays':len(te),'testMetrics':metrics(wintr)})
   time.sleep(8.2)
 except Exception as e:data_error=str(e)
 m=metrics(trades);test_days=sum(x['testDays'] for x in source);coverage=100*len(trades)/test_days if test_days else 0
 passed=(data_error is None and len(trades)>=MIN_TEST_DAYS and coverage>=99.9 and m['winrate']>TARGET and all(x['rr'] in (1,2) for x in trades))
 report['symbols'][sym.replace('/','')]={'pass':passed,'holdout':m,'coveragePct':round(coverage,2),'source':source,'dataError':data_error,'trades':trades}
 allpass &= passed;print(sym,m,'coverage',round(coverage,1),'PASS' if passed else 'FAIL',data_error or '',flush=True)
 # persist partial evidence so a later API fault cannot erase completed symbols
 report['pass']=False;os.makedirs(os.path.dirname(OUT),exist_ok=True)
 with open(OUT,'w') as fh:json.dump(report,fh,indent=2)
report['pass']=allpass
with open(OUT,'w') as fh:json.dump(report,fh,indent=2)
print('FINAL_PASS',allpass,'seed',SEED)
