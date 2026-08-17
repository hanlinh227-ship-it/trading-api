#!/usr/bin/env python3
import csv, io, json, math, random, statistics, time, urllib.parse, urllib.request
from collections import defaultdict
from datetime import datetime, timezone

VERSION='FREE_FX_DAILY_PRECISION_V6'
FX=['EURUSD','GBPUSD','USDJPY','USDCHF','USDCAD','AUDUSD','NZDUSD','EURJPY','EURGBP','EURCHF','EURAUD','EURNZD','EURCAD','GBPJPY','GBPCHF','GBPAUD','GBPNZD','GBPCAD','AUDJPY','AUDNZD','AUDCAD','AUDCHF','NZDJPY','NZDCAD','NZDCHF','CADJPY','CADCHF','CHFJPY']
HIDDEN='2026-08-01'
UA='trading-api-daily-precision/1.0'

def get_text(url,timeout=12):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/csv,*/*'})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read().decode('utf-8',errors='replace')

def stooq(pair):
    url='https://stooq.com/q/d/l/?'+urllib.parse.urlencode({'s':pair.lower(),'d1':'20240101','d2':'20260815','i':'d'})
    txt=get_text(url);rows=[]
    for x in csv.DictReader(io.StringIO(txt)):
        try:
            dt=datetime.strptime(x['Date'],'%Y-%m-%d').replace(tzinfo=timezone.utc);rows.append({'ts':int(dt.timestamp()),'open':float(x['Open']),'high':float(x['High']),'low':float(x['Low']),'close':float(x['Close'])})
        except Exception:pass
    if len(rows)<250:raise RuntimeError('STOOQ_SHORT_'+str(len(rows)))
    return sorted(rows,key=lambda x:x['ts']),'STOOQ'

def yahoo(pair):
    p1=int(datetime(2024,1,1,tzinfo=timezone.utc).timestamp());p2=int(datetime(2026,8,15,tzinfo=timezone.utc).timestamp())
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+pair+'=X?'+urllib.parse.urlencode({'period1':p1,'period2':p2,'interval':'1d','events':'div,splits'})
    d=json.loads(get_text(url));r=(d.get('chart',{}).get('result') or [None])[0]
    if not r:raise RuntimeError('YAHOO_NO_RESULT')
    q=(r.get('indicators',{}).get('quote') or [{}])[0];rows=[]
    for i,t in enumerate(r.get('timestamp') or []):
        try:
            o,h,l,c=q['open'][i],q['high'][i],q['low'][i],q['close'][i]
            if None in (o,h,l,c):continue
            rows.append({'ts':int(t),'open':float(o),'high':float(h),'low':float(l),'close':float(c)})
        except Exception:pass
    if len(rows)<250:raise RuntimeError('YAHOO_SHORT_'+str(len(rows)))
    return rows,'YAHOO'

def fetch(pair):
    try:return stooq(pair)
    except Exception as e1:
        try:return yahoo(pair)
        except Exception as e2:raise RuntimeError(str(e1)+'|'+str(e2))

def ema(v,p):
    out=[None]*len(v)
    if len(v)<p:return out
    e=sum(v[:p])/p;out[p-1]=e;k=2/(p+1)
    for i in range(p,len(v)):e=v[i]*k+e*(1-k);out[i]=e
    return out

def enrich(rows):
    c=[x['close'] for x in rows];e20=ema(c,20);e50=ema(c,50);e100=ema(c,100);tr=[0]*len(rows);atr=[None]*len(rows);rsi=[None]*len(rows)
    for i in range(1,len(rows)):tr[i]=max(rows[i]['high']-rows[i]['low'],abs(rows[i]['high']-c[i-1]),abs(rows[i]['low']-c[i-1]))
    if len(rows)>14:
        a=sum(tr[1:15])/14;ag=sum(max(c[i]-c[i-1],0) for i in range(1,15))/14;al=sum(max(c[i-1]-c[i],0) for i in range(1,15))/14
        for i in range(14,len(rows)):
            if i>14:
                a=(a*13+tr[i])/14;d=c[i]-c[i-1];ag=(ag*13+max(d,0))/14;al=(al*13+max(-d,0))/14
            atr[i]=a;rsi[i]=100 if al==0 else 100-100/(1+ag/al)
    out=[]
    for i,x in enumerate(rows):
        z=dict(x);z.update({'e20':e20[i],'e50':e50[i],'e100':e100[i],'atr':atr[i],'rsi':rsi[i]})
        if i>=20 and atr[i]:
            z['r1']=c[i]/c[i-1]-1;z['r3']=c[i]/c[i-3]-1;z['r5']=c[i]/c[i-5]-1;z['r10']=c[i]/c[i-10]-1;z['r20']=c[i]/c[i-20]-1
            z['mom5']=(c[i]-c[i-5])/atr[i];z['dist']=abs(c[i]-e20[i])/atr[i] if e20[i] else 9;z['h5']=max(a['high'] for a in rows[i-5:i]);z['l5']=min(a['low'] for a in rows[i-5:i]);z['h20']=max(a['high'] for a in rows[i-20:i]);z['l20']=min(a['low'] for a in rows[i-20:i])
        out.append(z)
    return out

def d(ts):return datetime.fromtimestamp(ts,timezone.utc).date().isoformat()
def sg(x):return 1 if x>0 else -1 if x<0 else 0

def context(data):
    by=defaultdict(dict)
    for s,rows in data.items():
        for i,r in enumerate(rows):
            if r.get('r5') is not None:by[r['ts']][s]=(i,r)
    for ts,z in by.items():
        st=defaultdict(list)
        for s,(i,r) in z.items():st[s[:3]].append(r['r5']);st[s[3:]].append(-r['r5'])
        av={k:sum(v)/len(v) for k,v in st.items() if v};gaps=[]
        for s,(i,r) in z.items():r['factor']=av.get(s[:3],0)-av.get(s[3:],0);gaps.append(abs(r['factor']))
        sc=statistics.median(gaps) if gaps else 1
        for s,(i,r) in z.items():r['fn']=r['factor']/(sc if sc>1e-9 else 1)

def market_out(rows,i,side,rr,risk,hold):
    if i+1>=len(rows):return None
    r=rows[i];entry=rows[i+1]['open'];a=r['atr'];sw=min(x['low'] for x in rows[max(0,i-3):i+1]) if side==1 else max(x['high'] for x in rows[max(0,i-3):i+1]);struct=(entry-sw) if side==1 else (sw-entry);R=max(risk*a,struct)
    if R<=0 or R>3*a:return None
    sl=entry-side*R;tp=entry+side*rr*R
    for j in range(i+1,min(len(rows),i+1+hold)):
        b=rows[j]
        if (side==1 and b['low']<=sl) or (side==-1 and b['high']>=sl):return {'res':'SL','R':-1}
        if (side==1 and b['high']>=tp) or (side==-1 and b['low']<=tp):return {'res':'TP','R':rr}
    last=rows[min(len(rows)-1,i+hold)]['close'];return {'res':'CUT','R':max(-1,min(rr,(last-entry)/R*side))}

def limit_out(rows,i,side,rr,risk,hold,off,expiry):
    r=rows[i];a=r['atr'];price=r['close']-side*off*a;fill=None
    for j in range(i+1,min(len(rows),i+1+expiry)):
        if rows[j]['low']<=price<=rows[j]['high']:fill=j;break
    if fill is None:return None
    sw=min(x['low'] for x in rows[max(0,i-4):i+1]) if side==1 else max(x['high'] for x in rows[max(0,i-4):i+1]);struct=(price-sw) if side==1 else (sw-price);R=max(risk*a,struct)
    if R<=0 or R>3*a:return None
    sl=price-side*R;tp=price+side*rr*R
    for j in range(fill,min(len(rows),fill+hold)):
        b=rows[j]
        if (side==1 and b['low']<=sl) or (side==-1 and b['high']>=sl):return {'res':'SL','R':-1}
        if (side==1 and b['high']>=tp) or (side==-1 and b['low']<=tp):return {'res':'TP','R':rr}
    last=rows[min(len(rows)-1,fill+hold-1)]['close'];return {'res':'CUT','R':max(-1,min(rr,(last-price)/R*side))}

def events(data,cfg):
    mode,rr,risk,hold,off,exp=cfg;out=[]
    for s,rows in data.items():
        for i,r in enumerate(rows):
            if i<110 or d(r['ts'])>=HIDDEN or r.get('fn') is None:continue
            side=1 if r['e20']>r['e50'] and r['r5']>0 else -1 if r['e20']<r['e50'] and r['r5']<0 else 0
            if not side:continue
            o=market_out(rows,i,side,rr,risk,hold) if mode=='M' else limit_out(rows,i,side,rr,risk,hold,off,exp)
            if not o:continue
            ar=r['rsi'] if side==1 else 100-r['rsi'];f=side*r['fn']
            raw=abs(r['mom5'])+.8*f+.3*(sg(r['r20'])==side)-.2*r['dist']+.2*((side==1 and r['close']>r['h5']) or (side==-1 and r['close']<r['l5']))
            out.append({'symbol':s,'day':d(r['ts']),'side':side,'mom':abs(r['mom5']),'factor':f,'long':int(sg(r['r20'])==side),'dist':r['dist'],'ar':ar,'break5':int((side==1 and r['close']>r['h5']) or (side==-1 and r['close']<r['l5'])),'break20':int((side==1 and r['close']>r['h20']) or (side==-1 and r['close']<r['l20'])),'raw':raw,'result':o['res'],'r':o['R'],'rr':rr})
    return out

def sel(ev,p):
    q=[]
    for x in ev:
        if x['mom']<p['mom'] or x['factor']<p['factor'] or x['dist']>p['dist'] or x['ar']<p['lo'] or x['ar']>p['hi']:continue
        if p['long'] and not x['long']:continue
        if p['br']==1 and not x['break5']:continue
        if p['br']==2 and not x['break20']:continue
        q.append(x)
    by=defaultdict(list)
    for x in q:by[x['day']].append(x)
    out=[]
    for day,z in by.items():out.extend(sorted(z,key=lambda x:x['raw'],reverse=True)[:p['top']])
    return out

def stat(z,a,b):
    q=[x for x in z if a<=x['day']<=b];tp=sum(x['result']=='TP' for x in q);sl=sum(x['result']=='SL' for x in q);cut=sum(x['result']=='CUT' for x in q);den=tp+sl
    return {'n':len(q),'tp':tp,'sl':sl,'cut':cut,'wr':100*tp/den if den else 0,'meanR':statistics.mean([x['r'] for x in q]) if q else -9,'resolved':100*den/len(q) if q else 0,'symbols':len(set(x['symbol'] for x in q))}

def folds(z):
    return {'DEV':stat(z,'2025-01-01','2026-04-30'),'MAY':stat(z,'2026-05-01','2026-05-31'),'JUNE':stat(z,'2026-06-01','2026-06-30'),'JULY':stat(z,'2026-07-01','2026-07-31')}
def obj(e):
    mins={'DEV':50,'MAY':6,'JUNE':6,'JULY':6};hit=all(e[k]['n']>=mins[k] and e[k]['wr']>=80 and e[k]['meanR']>0 and e[k]['resolved']>=70 for k in mins);pen=sum(max(0,mins[k]-e[k]['n'])*3 for k in mins);w=[e[k]['wr'] for k in mins];return (int(hit),min(w)-pen,statistics.mean(w),statistics.mean(e[k]['meanR'] for k in mins),sum(e[k]['n'] for k in mins))
def rp(r):return {'mom':r.choice([.1,.25,.4,.6,.8,1,1.3,1.6,2]),'factor':r.choice([-.2,0,.2,.4,.6,.8,1,1.25,1.5,2]),'dist':r.choice([.2,.35,.5,.7,.9,1.1,1.4]),'lo':r.choice([43,46,49,52,55]),'hi':r.choice([60,64,68,72,76,80]),'long':r.choice([False,True,True]),'br':r.choice([0,0,0,1,1,2]),'top':r.choice([1,1,1,2])}
def mutate(r,p):
    q=dict(p);x=rp(r);ks=list(x)
    for k in r.sample(ks,r.choice([1,1,2,2,3])):q[k]=x[k]
    return q

def evolve(cache,iters=50000):
    r=random.Random(606);cfgs=list(cache);pop=[];seen=set();best=None
    for t in range(iters):
        if pop and r.random()<.8:
            seed=r.choice(pop[:min(15,len(pop))]);cfg=seed[1];p=mutate(r,seed[2]);
            if r.random()<.12:cfg=r.choice(cfgs)
        else:cfg=r.choice(cfgs);p=rp(r)
        key=(cfg,json.dumps(p,sort_keys=True))
        if key in seen:continue
        seen.add(key);e=folds(sel(cache[cfg],p));o=obj(e);it=(o,cfg,p,e);pop.append(it);pop.sort(key=lambda x:x[0],reverse=True);pop=pop[:35]
        if best is None or o>best[0]:best=it;print('BEST',t,cfg,json.dumps(p),json.dumps(e),flush=True)
        if o[0]:return best,t+1
    return best,iters

def main():
    data={};errs={};src={}
    for s in FX:
        try:r,q=fetch(s);data[s]=enrich(r);src[s]=q;print('FETCH',s,q,len(r),flush=True)
        except Exception as e:errs[s]=str(e);print('FAIL',s,str(e)[:100],flush=True)
    context(data);print('COVERAGE',json.dumps({'loaded':len(data),'requested':len(FX),'failed':errs,'sources':src}),flush=True)
    cfgs=[]
    for mode in ('M','L'):
      for rr in (1.0,1.5):
       for risk in (.65,.8,1,1.2,1.4):
        for hold in (3,5,7,10):
         if mode=='M':cfgs.append((mode,rr,risk,hold,0,1))
         else:
          for off in (.2,.35,.5,.7,.9):
           for exp in (1,2,3):cfgs.append((mode,rr,risk,hold,off,exp))
    cache={c:events(data,c) for c in cfgs};best,n=evolve(cache,50000)
    o,c,p,e=best if best else (None,None,None,None)
    out={'version':VERSION,'providerCreditsUsed':0,'hiddenHoldoutEvaluated':False,'coverage':{'loaded':len(data),'requested':len(FX)},'qualified':bool(o and o[0]),'objective':o,'execution':c,'params':p,'folds':e,'iterations':n,'integrity':'28 FX requested; daily cross-currency factor; LIMIT unfilled = NO_TRADE; Aug excluded.'}
    print('FINAL_DAILY_FX',json.dumps(out,indent=2),flush=True)
if __name__=='__main__':main()
