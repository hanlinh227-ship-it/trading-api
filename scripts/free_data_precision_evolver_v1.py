#!/usr/bin/env python3
import json, math, random, statistics, time, urllib.request, urllib.parse, urllib.error
from collections import defaultdict
from datetime import datetime, timezone

VERSION = 'FREE_DATA_PRECISION_EVOLVER_V1'
UA = 'trading-api-research/1.0'

FX = [
'EURUSD','GBPUSD','USDJPY','USDCHF','USDCAD','AUDUSD','NZDUSD',
'EURJPY','EURGBP','EURCHF','EURAUD','EURNZD','EURCAD',
'GBPJPY','GBPCHF','GBPAUD','GBPNZD','GBPCAD',
'AUDJPY','AUDNZD','AUDCAD','AUDCHF','NZDJPY','NZDCAD','NZDCHF','CADJPY','CADCHF','CHFJPY']

CRYPTO = ['BTC','ETH','SOL','HYPE','SHIB','TRX','XRP','AAVE','ADA','ALGO','APT','ARB','ATOM','AVAX','BCH','BONK','CRV','DOGE','DOT','ETC','FIL','FLOKI','HBAR','INJ','JTO','JUP','KAITO','LDO','LINK','LTC','MOODENG','NEAR','ONDO','OP','ORDI','PENGU','PEPE','PNUT','POL','POPCAT','RENDER','S','STX','SUI','TAO','TIA','TON','TRUMP','UNI','WIF','WLD','AIXBT','ASTER','FARTCOIN','GRASS','IP','LIT','PUMP','VIRTUAL','XPL','ZEC']

START_TS = int(datetime(2026,2,1,tzinfo=timezone.utc).timestamp())
END_TS = int(datetime(2026,8,15,tzinfo=timezone.utc).timestamp())
HIDDEN_START = datetime(2026,8,1,tzinfo=timezone.utc).date().isoformat()

FOLDS = [
    ('DEV','2026-02-01','2026-05-31'),
    ('JUNE','2026-06-01','2026-06-30'),
    ('JULY','2026-07-01','2026-07-31'),
]


def http_json(url, timeout=25, retries=3):
    last = None
    for n in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':UA,'Accept':'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last = str(e)
            time.sleep(0.7*(n+1))
    raise RuntimeError(last or 'HTTP_FAIL')


def floor4(ts):
    return ts - (ts % (4*3600))


def resample4(rows):
    g = defaultdict(list)
    for r in rows:
        g[floor4(r['ts'])].append(r)
    out=[]
    for ts in sorted(g):
        a=sorted(g[ts], key=lambda x:x['ts'])
        if not a: continue
        out.append({'ts':ts,'open':a[0]['open'],'high':max(x['high'] for x in a),'low':min(x['low'] for x in a),'close':a[-1]['close']})
    return out


def fetch_fx(pair):
    ticker = pair + '=X'
    q = urllib.parse.urlencode({'period1':START_TS,'period2':END_TS,'interval':'1h','includePrePost':'false','events':'div,splits'})
    bases=['https://query1.finance.yahoo.com/v8/finance/chart/','https://query2.finance.yahoo.com/v8/finance/chart/']
    err=None
    for base in bases:
        try:
            d=http_json(base+urllib.parse.quote(ticker,safe='=')+'?'+q)
            result=d.get('chart',{}).get('result') or []
            if not result: raise RuntimeError(str(d.get('chart',{}).get('error')))
            x=result[0]; ts=x.get('timestamp') or []; q0=(x.get('indicators',{}).get('quote') or [{}])[0]
            rows=[]
            for i,t in enumerate(ts):
                try:
                    o,h,l,c=q0['open'][i],q0['high'][i],q0['low'][i],q0['close'][i]
                    if None in (o,h,l,c): continue
                    rows.append({'ts':int(t),'open':float(o),'high':float(h),'low':float(l),'close':float(c)})
                except Exception: pass
            if len(rows)>300: return resample4(rows)
        except Exception as e: err=str(e)
    raise RuntimeError(err or 'FX_NO_DATA')


def binance_klines(symbol):
    pair=symbol+'USDT'; step=4*3600*1000; start=START_TS*1000; end=END_TS*1000
    rows=[]
    hosts=['https://api.binance.com','https://api1.binance.com','https://api2.binance.com','https://api3.binance.com']
    host_i=0
    while start<end:
        url=hosts[host_i%len(hosts)]+'/api/v3/klines?'+urllib.parse.urlencode({'symbol':pair,'interval':'4h','startTime':start,'endTime':end,'limit':1000})
        try:
            d=http_json(url,retries=2)
            if not isinstance(d,list): raise RuntimeError(str(d)[:200])
            if not d: break
            for k in d:
                rows.append({'ts':int(k[0]//1000),'open':float(k[1]),'high':float(k[2]),'low':float(k[3]),'close':float(k[4])})
            nxt=int(d[-1][0])+step
            if nxt<=start: break
            start=nxt
            time.sleep(0.03)
        except Exception:
            host_i+=1
            if host_i>=len(hosts): raise
    return rows


def bybit_klines(symbol):
    pair=symbol+'USDT'; start=START_TS*1000; end=END_TS*1000; rows=[]; cursor=start
    # Bybit returns newest-first for range; paginate forward using explicit start/end chunks ~1000*4h.
    chunk=999*4*3600*1000
    while cursor<end:
        e=min(end,cursor+chunk)
        url='https://api.bybit.com/v5/market/kline?'+urllib.parse.urlencode({'category':'spot','symbol':pair,'interval':'240','start':cursor,'end':e,'limit':1000})
        d=http_json(url,retries=2)
        arr=((d.get('result') or {}).get('list') or []) if isinstance(d,dict) else []
        for k in arr:
            rows.append({'ts':int(int(k[0])//1000),'open':float(k[1]),'high':float(k[2]),'low':float(k[3]),'close':float(k[4])})
        cursor=e+1
        time.sleep(0.03)
    ded={r['ts']:r for r in rows}
    return [ded[k] for k in sorted(ded)]


def fetch_crypto(symbol):
    try:
        r=binance_klines(symbol)
        if len(r)>=120: return r,'BINANCE'
    except Exception: pass
    try:
        r=bybit_klines(symbol)
        if len(r)>=120: return r,'BYBIT'
    except Exception: pass
    raise RuntimeError('NO_PUBLIC_HISTORY')


def ema_series(v,p):
    out=[None]*len(v)
    if len(v)<p:return out
    e=sum(v[:p])/p; out[p-1]=e; k=2/(p+1)
    for i in range(p,len(v)):
        e=v[i]*k+e*(1-k);out[i]=e
    return out


def indicators(rows):
    n=len(rows); c=[x['close'] for x in rows]
    e20=ema_series(c,20);e50=ema_series(c,50);e100=ema_series(c,100)
    tr=[0.0]*n; plus=[0.0]*n;minus=[0.0]*n
    for i in range(1,n):
        tr[i]=max(rows[i]['high']-rows[i]['low'],abs(rows[i]['high']-c[i-1]),abs(rows[i]['low']-c[i-1]))
        up=rows[i]['high']-rows[i-1]['high'];dn=rows[i-1]['low']-rows[i]['low']
        plus[i]=up if up>dn and up>0 else 0.0;minus[i]=dn if dn>up and dn>0 else 0.0
    atr=[None]*n; rsi=[None]*n; adx=[None]*n
    if n>14:
        a=sum(tr[1:15])/14; pg=sum(plus[1:15])/14; mg=sum(minus[1:15])/14
        gains=[];losses=[]
        for i in range(1,15):
            d=c[i]-c[i-1];gains.append(max(d,0));losses.append(max(-d,0))
        ag=sum(gains)/14;al=sum(losses)/14
        dx=[]
        for i in range(14,n):
            if i>14:
                a=(a*13+tr[i])/14;pg=(pg*13+plus[i])/14;mg=(mg*13+minus[i])/14
                d=c[i]-c[i-1];ag=(ag*13+max(d,0))/14;al=(al*13+max(-d,0))/14
            atr[i]=a
            rsi[i]=100.0 if al==0 else 100-100/(1+ag/al)
            pdi=100*pg/a if a else 0;mdi=100*mg/a if a else 0;den=pdi+mdi
            dxv=100*abs(pdi-mdi)/den if den else 0;dx.append(dxv)
            if len(dx)>=14: adx[i]=sum(dx[-14:])/14
    out=[]
    for i,r in enumerate(rows):
        z=dict(r);z.update({'ema20':e20[i],'ema50':e50[i],'ema100':e100[i],'atr':atr[i],'rsi':rsi[i],'adx':adx[i]})
        if i>=18 and atr[i] and c[i]>0:
            z['r1']=c[i]/c[i-1]-1;z['r3']=c[i]/c[i-3]-1;z['r6']=c[i]/c[i-6]-1;z['r18']=c[i]/c[i-18]-1
            z['mom6atr']=(c[i]-c[i-6])/atr[i]
            z['emaDistAtr']=abs(c[i]-e20[i])/atr[i] if e20[i] else 99
            z['prevHigh6']=max(x['high'] for x in rows[i-6:i]);z['prevLow6']=min(x['low'] for x in rows[i-6:i])
            z['prevHigh18']=max(x['high'] for x in rows[i-18:i]);z['prevLow18']=min(x['low'] for x in rows[i-18:i])
        out.append(z)
    return out


def day(ts): return datetime.fromtimestamp(ts,timezone.utc).date().isoformat()
def hour(ts): return datetime.fromtimestamp(ts,timezone.utc).hour

def sign(x,eps=0): return 1 if x>eps else (-1 if x<-eps else 0)


def add_context(data, market):
    # data: symbol -> enriched rows
    byts=defaultdict(dict)
    for s,rows in data.items():
        for i,r in enumerate(rows):
            if r.get('r6') is not None: byts[r['ts']][s]=(i,r)
    if market=='FX':
        strengths={}
        for ts,m in byts.items():
            vals=defaultdict(list)
            for s,(i,r) in m.items():
                if len(s)!=6: continue
                b,q=s[:3],s[3:];ret=r['r6'];vals[b].append(ret);vals[q].append(-ret)
            strengths[ts]={k:(sum(v)/len(v) if v else 0) for k,v in vals.items()}
        for ts,m in byts.items():
            st=strengths.get(ts,{})
            gaps=[]
            for s,(i,r) in m.items():
                g=st.get(s[:3],0)-st.get(s[3:],0);r['factorGap']=g;gaps.append(abs(g))
            scale=statistics.median(gaps) if gaps else 0
            for s,(i,r) in m.items(): r['factorNorm']=r.get('factorGap',0)/(scale if scale>1e-9 else 1)
    else:
        btcmap={r['ts']:r for r in data.get('BTC',[]) if r.get('r6') is not None}
        for ts,m in byts.items():
            rr=[x[1]['r6'] for x in m.values() if x[1].get('r6') is not None]
            br=sum(x>0 for x in rr)/len(rr) if rr else .5
            b=btcmap.get(ts);bret=b.get('r6',0) if b else 0
            for s,(i,r) in m.items():
                r['breadth']=br;r['btcR6']=bret;r['rel6']=r['r6']-bret


def trade_outcome(rows,i,side,rr,risk_floor,maxhold):
    if i+1>=len(rows): return None
    sig=rows[i]; entry=rows[i+1]['open'];atr=sig.get('atr')
    if not atr or atr<=0:return None
    if side==1:
        swing=min(x['low'] for x in rows[max(0,i-4):i+1]);struct=max(entry-swing,0)
    else:
        swing=max(x['high'] for x in rows[max(0,i-4):i+1]);struct=max(swing-entry,0)
    risk=max(atr*risk_floor,struct)
    if risk<=0 or risk>atr*3.0:return None
    sl=entry-side*risk;tp=entry+side*rr*risk
    for j in range(i+1,min(len(rows),i+1+maxhold)):
        b=rows[j]
        if side==1:
            if b['low']<=sl:return {'result':'SL','r':-1.0,'bars':j-i,'entry':entry,'sl':sl,'tp':tp}
            if b['high']>=tp:return {'result':'TP','r':rr,'bars':j-i,'entry':entry,'sl':sl,'tp':tp}
        else:
            if b['high']>=sl:return {'result':'SL','r':-1.0,'bars':j-i,'entry':entry,'sl':sl,'tp':tp}
            if b['low']<=tp:return {'result':'TP','r':rr,'bars':j-i,'entry':entry,'sl':sl,'tp':tp}
    last=rows[min(len(rows)-1,i+maxhold)]['close'];r=(last-entry)/risk*side
    return {'result':'CUT','r':max(-1,min(rr,r)),'bars':maxhold,'entry':entry,'sl':sl,'tp':tp}


def fx_candidates(data,p):
    out=[]
    for s,rows in data.items():
        for i,r in enumerate(rows):
            if i<100 or day(r['ts'])>=HIDDEN_START: continue
            if r.get('adx') is None or r.get('ema100') is None or r.get('factorNorm') is None:continue
            if p['session']>=0 and hour(r['ts'])!=p['session']:continue
            side=1 if r['ema20']>r['ema50'] and r['r6']>0 else (-1 if r['ema20']<r['ema50'] and r['r6']<0 else 0)
            if not side:continue
            if r['adx']<p['adx'] or abs(r['mom6atr'])<p['mom']:continue
            if p['long'] and sign(r['r18'])!=side:continue
            if p['factor'] and sign(r['factorNorm'])!=side:continue
            if abs(r['factorNorm'])<p['fmin']:continue
            if r['emaDistAtr']>p['dist']:continue
            if side==1 and not (p['rsi_lo']<=r['rsi']<=p['rsi_hi']):continue
            if side==-1 and not (100-p['rsi_hi']<=r['rsi']<=100-p['rsi_lo']):continue
            if p['breakout']:
                if side==1 and r['close']<=r['prevHigh6']:continue
                if side==-1 and r['close']>=r['prevLow6']:continue
            o=trade_outcome(rows,i,side,p['rr'],p['risk'],p['hold'])
            if not o:continue
            score=(r['adx']/25)+abs(r['mom6atr'])+abs(r['factorNorm'])*.65+(1.5-r['emaDistAtr'])*.3+(0.3 if sign(r['r18'])==side else 0)
            out.append({'symbol':s,'ts':r['ts'],'day':day(r['ts']),'side':side,'score':score,**o})
    return select_daily(out,p['topk'])


def crypto_candidates(data,p):
    out=[]
    for s,rows in data.items():
        for i,r in enumerate(rows):
            if i<100 or day(r['ts'])>=HIDDEN_START:continue
            if r.get('adx') is None or r.get('breadth') is None or r.get('rel6') is None:continue
            side=1 if r['ema20']>r['ema50'] and r['r6']>0 else (-1 if r['ema20']<r['ema50'] and r['r6']<0 else 0)
            if not side:continue
            if r['adx']<p['adx'] or abs(r['mom6atr'])<p['mom']:continue
            if p['long'] and sign(r['r18'])!=side:continue
            if p['btc'] and sign(r['btcR6']) not in (0,side):continue
            if side==1 and r['breadth']<p['breadth']:continue
            if side==-1 and r['breadth']>1-p['breadth']:continue
            if side*r['rel6']<p['rel']:continue
            if r['emaDistAtr']>p['dist']:continue
            if side==1 and not (p['rsi_lo']<=r['rsi']<=p['rsi_hi']):continue
            if side==-1 and not (100-p['rsi_hi']<=r['rsi']<=100-p['rsi_lo']):continue
            if p['breakout']:
                if side==1 and r['close']<=r['prevHigh6']:continue
                if side==-1 and r['close']>=r['prevLow6']:continue
            o=trade_outcome(rows,i,side,p['rr'],p['risk'],p['hold'])
            if not o:continue
            regime=abs(r['breadth']-.5)*2
            score=(r['adx']/25)+abs(r['mom6atr'])+regime*1.2+side*r['rel6']*40+(0.35 if sign(r['btcR6'])==side else 0)+(1.5-r['emaDistAtr'])*.25
            out.append({'symbol':s,'ts':r['ts'],'day':day(r['ts']),'side':side,'score':score,**o})
    return select_daily(out,p['topk'])


def select_daily(a,topk):
    by=defaultdict(list)
    for x in a:by[x['day']].append(x)
    out=[]
    for d,z in by.items():out.extend(sorted(z,key=lambda x:x['score'],reverse=True)[:topk])
    return out


def stats(rows,start,end):
    z=[x for x in rows if start<=x['day']<=end]
    tp=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);cut=sum(x['result']=='CUT' for x in z);den=tp+sl
    return {'n':len(z),'tp':tp,'sl':sl,'cut':cut,'wr':100*tp/den if den else 0,'meanR':statistics.mean([x['r'] for x in z]) if z else -9,
            'resolvedRate':100*den/len(z) if z else 0,'symbols':len(set(x['symbol'] for x in z))}


def compact(s):return {k:(round(v,3) if isinstance(v,float) else v) for k,v in s.items()}


def evaluate(rows):return {name:stats(rows,a,b) for name,a,b in FOLDS}


def qualifies(ev,market):
    req={'DEV':30 if market=='FX' else 35,'JUNE':8,'JULY':8}
    return all(ev[k]['n']>=req[k] and ev[k]['wr']>=80 and ev[k]['meanR']>0 and ev[k]['resolvedRate']>=75 for k in req)


def objective(ev,market):
    req={'DEV':30 if market=='FX' else 35,'JUNE':8,'JULY':8}
    penalties=sum(max(0,req[k]-ev[k]['n'])*3 for k in req)
    wrs=[ev[k]['wr'] for k in ('DEV','JUNE','JULY') if ev[k]['n']>0]
    worst=min(wrs) if wrs else 0;avg=sum(wrs)/len(wrs) if wrs else 0
    mean=sum(ev[k]['meanR'] for k in ('DEV','JUNE','JULY'))/3
    return (1 if qualifies(ev,market) else 0,worst-penalties,avg,mean,sum(ev[k]['n'] for k in ev))


def rand_fx(rng):
    return {'rr':rng.choice([1.0,1.5]),'risk':rng.choice([.65,.8,1.0,1.2,1.4]),'hold':rng.choice([6,9,12,18]),'topk':rng.choice([1,1,1,2,2,3]),
      'session':rng.choice([-1,0,4,8,12,16,20]),'adx':rng.choice([15,18,20,23,25,28,30,35]),'mom':rng.choice([.2,.4,.6,.8,1.0,1.3,1.6]),
      'long':rng.choice([False,True]),'factor':rng.choice([False,True,True]),'fmin':rng.choice([0,.25,.5,.75,1.0,1.25]),'dist':rng.choice([.25,.4,.6,.8,1.0,1.3,1.6]),
      'rsi_lo':rng.choice([42,45,48,50]),'rsi_hi':rng.choice([62,65,68,72,75]),'breakout':rng.choice([False,False,True])}


def rand_cr(rng):
    return {'rr':rng.choice([1.0,1.5]),'risk':rng.choice([.65,.8,1.0,1.2,1.4]),'hold':rng.choice([6,9,12,18]),'topk':rng.choice([1,1,1,2,2,3]),
      'adx':rng.choice([15,18,20,23,25,28,30,35]),'mom':rng.choice([.2,.4,.6,.8,1.0,1.3,1.6]),'long':rng.choice([False,True]),'btc':rng.choice([False,True,True]),
      'breadth':rng.choice([.5,.55,.6,.65,.7,.75,.8,.85]),'rel':rng.choice([-.02,-.01,0,.005,.01,.02]),'dist':rng.choice([.25,.4,.6,.8,1.0,1.3,1.6]),
      'rsi_lo':rng.choice([42,45,48,50]),'rsi_hi':rng.choice([62,65,68,72,75]),'breakout':rng.choice([False,False,True])}


def evolve(data,market,iters=12000):
    rng=random.Random(20260817 + (1 if market=='FX' else 2));best=[];seen=set()
    gen=rand_fx if market=='FX' else rand_cr;fn=fx_candidates if market=='FX' else crypto_candidates
    for n in range(iters):
        p=gen(rng);key=json.dumps(p,sort_keys=True)
        if key in seen:continue
        seen.add(key)
        rows=fn(data,p);ev=evaluate(rows);obj=objective(ev,market)
        item=(obj,p,ev)
        if len(best)<20 or obj>best[-1][0]:
            best.append(item);best.sort(key=lambda x:x[0],reverse=True);best=best[:20]
        if obj[0]==1:
            return item,best,n+1
    return best[0] if best else None,best,iters


def main():
    print(json.dumps({'version':VERSION,'phase':'PUBLIC_FREE_DATA_DEVELOPMENT_ONLY','hiddenHoldout':'2026-08-01..2026-08-14 NOT EVALUATED','providerCreditsUsed':0}))
    fxdata={};fxerr={}
    for s in FX:
        try:
            fxdata[s]=indicators(fetch_fx(s));print('FX_FETCH',s,len(fxdata[s]))
        except Exception as e:fxerr[s]=str(e);print('FX_FAIL',s,str(e)[:120])
    add_context(fxdata,'FX')
    crdata={};crsrc={};crerr={}
    for s in CRYPTO:
        try:
            r,src=fetch_crypto(s);crdata[s]=indicators(r);crsrc[s]=src;print('CR_FETCH',s,src,len(r))
        except Exception as e:crerr[s]=str(e);print('CR_FAIL',s,str(e)[:120])
    add_context(crdata,'CRYPTO')
    print('COVERAGE',json.dumps({'fx':{'requested':len(FX),'loaded':len(fxdata),'failed':fxerr},'crypto':{'requested':len(CRYPTO),'loaded':len(crdata),'failed':crerr,'sources':crsrc}}))
    fxbest,fxtop,fxn=evolve(fxdata,'FX',12000)
    crbest,crtop,crn=evolve(crdata,'CRYPTO',12000)
    def pack(x):
        if not x:return None
        obj,p,ev=x;return {'objective':obj,'params':p,'folds':{k:compact(v) for k,v in ev.items()},'qualified':bool(obj[0])}
    out={'version':VERSION,'providerCreditsUsed':0,'hiddenHoldoutEvaluated':False,
      'coverage':{'fxLoaded':len(fxdata),'fxRequested':len(FX),'cryptoLoaded':len(crdata),'cryptoRequested':len(CRYPTO)},
      'forex':pack(fxbest),'crypto':pack(crbest),'bothQualifiedForLock':bool(fxbest and crbest and fxbest[0][0] and crbest[0][0]),
      'iterations':{'forex':fxn,'crypto':crn},
      'integrity':'All symbols are scanned at every eligible timestamp; NO_TRADE is allowed. August final holdout is not read by candidate generation or evaluation.'}
    print('FINAL_CANDIDATE',json.dumps(out,indent=2))

if __name__=='__main__':main()
