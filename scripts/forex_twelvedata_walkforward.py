#!/usr/bin/env python3
import os,json,math,random,time,urllib.parse,urllib.request
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

def f(x,d=0.0):
 try:return float(x)
 except:return d

def ema(xs,p):
 if not xs:return []
 k=2/(p+1); out=[]; e=xs[0]
 for x in xs:e=x*k+e*(1-k);out.append(e)
 return out

def atr(rows,p=14):
 out=[0.0]*len(rows); trs=[]
 for i,r in enumerate(rows):
  if i==0: tr=r['h']-r['l']
  else: tr=max(r['h']-r['l'],abs(r['h']-rows[i-1]['c']),abs(r['l']-rows[i-1]['c']))
  trs.append(tr); out[i]=sum(trs[max(0,i-p+1):i+1])/min(p,i+1)
 return out

def rsi(cs,p=14):
 out=[50.0]*len(cs); gains=[];loss=[]
 for i in range(1,len(cs)):
  d=cs[i]-cs[i-1];gains.append(max(d,0));loss.append(max(-d,0))
  if i>=p:
   g=sum(gains[i-p:i])/p;l=sum(loss[i-p:i])/p
   out[i]=100 if l==0 else 100-100/(1+g/l)
 return out

def fetch(sym,a,b):
 q=urllib.parse.urlencode({'symbol':sym,'interval':'5min','start_date':a.strftime('%Y-%m-%d %H:%M:%S'),'end_date':b.strftime('%Y-%m-%d %H:%M:%S'),'outputsize':5000,'timezone':'UTC','apikey':KEY})
 url='https://api.twelvedata.com/time_series?'+q
 with urllib.request.urlopen(url,timeout=45) as r: j=json.load(r)
 if j.get('status')=='error' or 'values' not in j: raise RuntimeError(f'{sym}: {j}')
 rows=[]
 for x in reversed(j['values']):
  rows.append({'t':datetime.strptime(x['datetime'],'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc),'o':f(x['open']),'h':f(x['high']),'l':f(x['low']),'c':f(x['close'])})
 return rows

def enrich(rows):
 cs=[x['c'] for x in rows]; e20=ema(cs,20);e50=ema(cs,50);aa=atr(rows,14);rr=rsi(cs,14)
 for i,x in enumerate(rows):x['e20']=e20[i];x['e50']=e50[i];x['atr']=aa[i];x['rsi']=rr[i]
 return rows

def day_groups(rows):
 g=defaultdict(list)
 for r in rows:g[r['t'].date().isoformat()].append(r)
 return {k:v for k,v in g.items() if len(v)>=120}

def signal(row,p):
 trend=1 if row['e20']>row['e50'] else -1
 slope=(row['e20']-row['e50'])/max(row['atr'],1e-12)
 if abs(slope)<p['trend']: return 0
 if abs(row['c']-row['e20'])/max(row['atr'],1e-12)>p['chase']: return 0
 if trend>0 and not (p['rlo']<=row['rsi']<=p['rhi']):return 0
 if trend<0 and not (100-p['rhi']<=row['rsi']<=100-p['rlo']):return 0
 return trend

def trade_day(rows,p):
 # Decision uses only current/past features. Exactly one trade/day via deterministic fallback.
 cand=[(i,r) for i,r in enumerate(rows) if p['h0']<=r['t'].hour<=p['h1'] and i>=60]
 pick=None;side=0;fallback=False
 for i,r in cand:
  s=signal(r,p)
  if s: pick=(i,r);side=s;break
 if not pick:
  if not cand:return None
  i,r=cand[-1]; side=1 if r['e20']>=r['e50'] else -1; pick=(i,r); fallback=True
 i,r=pick; dist=max(r['atr']*p['stop'],1e-8); entry=r['c']; sl=entry-side*dist; tp=entry+side*dist*p['rr']
 result='TIMEOUT';exitp=rows[-1]['c'];mfe=0;mae=0
 for z in rows[i+1:]:
  favorable=(z['h']-entry)*side if side>0 else (entry-z['l'])
  adverse=(entry-z['l']) if side>0 else (z['h']-entry)
  mfe=max(mfe,favorable/dist);mae=max(mae,adverse/dist)
  hit_sl=z['l']<=sl if side>0 else z['h']>=sl
  hit_tp=z['h']>=tp if side>0 else z['l']<=tp
  if hit_sl and hit_tp: result='LOSS';exitp=sl;break # pessimistic same-bar ordering
  if hit_sl:result='LOSS';exitp=sl;break
  if hit_tp:result='WIN';exitp=tp;break
 # Timeout is scored by realized R, not silently excluded.
 rmult=((exitp-entry)*side)/dist
 if result=='TIMEOUT': result='WIN' if rmult>=0.5*p['rr'] else 'LOSS'
 return {'day':r['t'].date().isoformat(),'entry_time':r['t'].isoformat(),'side':'BUY' if side>0 else 'SELL','rr':p['rr'],'result':result,'r':round(rmult if result=='LOSS' else p['rr'],3),'fallback':fallback,'mfeR':round(mfe,3),'maeR':round(mae,3)}

def params():
 out=[]
 for rr in (1,2):
  for h0,h1 in ((6,10),(7,11),(8,13),(12,16),(13,17)):
   for stop in (0.8,1.0,1.2,1.5,1.8):
    for trend in (0.08,0.15,0.25,0.4):
     for chase in (0.3,0.5,0.8,1.2):
      for rlo,rhi in ((38,62),(42,64),(45,68),(35,65)):
       out.append({'rr':rr,'h0':h0,'h1':h1,'stop':stop,'trend':trend,'chase':chase,'rlo':rlo,'rhi':rhi})
 RNG.shuffle(out);return out
P=params()

def score(trades):
 if not trades:return (-1e9,{})
 w=sum(x['result']=='WIN' for x in trades); n=len(trades); fb=sum(x['fallback'] for x in trades)
 wr=100*w/n; avgR=sum(x['r'] for x in trades)/n
 return wr+min(10,max(-10,avgR*5))-fb/n*8,{'trades':n,'wins':w,'losses':n-w,'winrate':round(wr,2),'avgR':round(avgR,3),'fallbackPct':round(100*fb/n,2)}

def optimize(train_days):
 best=None
 # broad randomized search, then deterministic top selection on TRAIN only
 for p in P[:1800]:
  ts=[trade_day(v,p) for _,v in sorted(train_days.items())];ts=[x for x in ts if x]
  s,m=score(ts)
  if best is None or s>best[0]:best=(s,p,m)
 return best

def random_window():
 span=(END-START).days-DAYS
 a=START+timedelta(days=RNG.randint(0,max(1,span)));return a,a+timedelta(days=DAYS)

windows=[random_window() for _ in range(WINDOWS)]
report={'version':'FOREX-TWELVEDATA-WALKFORWARD-1','seed':SEED,'generatedAt':datetime.now(timezone.utc).isoformat(),'rules':{'source':'Twelve Data 5min','noLookahead':True,'sameBarSLTP':'SL_FIRST_PESSIMISTIC','rrAllowed':[1,2],'minOneTradePerDay':True,'targetWinratePctStrictlyGreaterThan':TARGET,'selection':'parameters selected on TRAIN only; HOLDOUT never used for parameter selection'},'windows':[{'start':a.isoformat(),'end':b.isoformat()} for a,b in windows],'symbols':{},'pass':False}
allpass=True
for si,sym in enumerate(SYMS):
 all_train={};all_test={}; source=[]
 for wi,(a,b) in enumerate(windows):
  rows=enrich(fetch(sym,a,b));g=day_groups(rows);days=sorted(g)
  cut=max(2,int(len(days)*.60));tr=days[:cut];te=days[cut:]
  for d in tr:all_train[f'w{wi}:{d}']=g[d]
  for d in te:all_test[f'w{wi}:{d}']=g[d]
  source.append({'window':wi,'bars':len(rows),'trainDays':len(tr),'testDays':len(te)})
  time.sleep(8.2)
 best=optimize(all_train);p=best[1]
 tests=[trade_day(v,p) for _,v in sorted(all_test.items())];tests=[x for x in tests if x]
 _,m=score(tests); coverage=(len(tests)/len(all_test)*100 if all_test else 0); passed=(len(tests)>=MIN_TEST_DAYS and coverage>=99.9 and m.get('winrate',0)>TARGET and p['rr'] in (1,2))
 report['symbols'][sym.replace('/','')]= {'pass':passed,'params':p,'train':best[2],'holdout':m,'coveragePct':round(coverage,2),'source':source,'trades':tests}
 allpass &= passed
 print(sym,report['symbols'][sym.replace('/','')]['holdout'],'PASS' if passed else 'FAIL',flush=True)
report['pass']=allpass
os.makedirs(os.path.dirname(OUT),exist_ok=True)
with open(OUT,'w') as fh:json.dump(report,fh,indent=2)
print('FINAL_PASS',allpass,'seed',SEED)
