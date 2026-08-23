#!/usr/bin/env python3
"""V11 report-only four-month per-symbol backtest using public feeds.

Purpose: reproduce the earlier V62/V63/V73-style research loop without
requiring a GitHub Twelve Data secret. This runner NEVER deploys, trades, or
unlocks Telegram.

Data:
- Forex/Metal/Index: Yahoo Finance exact public symbols, H1 bars.
- Crypto: Binance Spot H1, fallback Bybit Spot H1.

Protocol:
- every current V11 catalog symbol is tested independently;
- latest 122 days, H1, max 3 executed entries per eligible UTC day;
- Crypto 7/7; Forex/Metal/Index exclude Saturday/Sunday;
- next-bar entry with adverse execution padding;
- same-bar TP+SL => LOSS; timeout => non-win;
- RR exactly 1:1 or 1:2;
- chronological 60% DEV / 20% VALIDATION / 20% untouched OOS;
- OOS never ranks/tunes candidates;
- PASS requires >=80.00% on full, validation and OOS plus sample gates.
"""
from __future__ import annotations

import bisect
import concurrent.futures as cf
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CATALOG=ROOT/'cloudflare-worker/v11/symbol-catalog.js'
OUT=ROOT/'data/v11_public_backtest_4m.json'
GATE=ROOT/'data/v11_public_backtest_gate.json'
VERSION='V11-PUBLIC-H1-4M-R1'
DAYS=int(os.environ.get('V11_BT_DAYS','122'))
MIN_TOTAL=int(os.environ.get('V11_MIN_TOTAL_TRADES','40'))
MIN_DEV=int(os.environ.get('V11_MIN_DEV_TRADES','20'))
MIN_VAL=int(os.environ.get('V11_MIN_VAL_TRADES','8'))
MIN_OOS=int(os.environ.get('V11_MIN_OOS_TRADES','8'))
REQUIRED=float(os.environ.get('V11_REQUIRED_WR','80'))
ALLOWED_RR=(1.0,2.0)
STOP_ATR=(0.65,0.8,1.0,1.25,1.5,1.8)
HORIZON=(3,6,12)
STRENGTH=(0.0,0.35,0.6,0.9)
COST_ATR={'forex':0.015,'crypto':0.02,'metal':0.02,'index':0.015}
INDEX_Y={'NAS100':'^NDX','US30':'^DJI','US500':'^GSPC','DEX':'^GDAXI','JP225':'^N225'}
USD_BASE={'USDJPY':'JPY=X','USDCHF':'CHF=X','USDCAD':'CAD=X'}


def now(): return datetime.now(timezone.utc)
def iso(ts): return datetime.fromtimestamp(ts,timezone.utc).isoformat().replace('+00:00','Z')
def norm(s): return re.sub(r'[^A-Z0-9]','',str(s).upper())
def f(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except Exception:return None


def get_json(url,timeout=30,retries=3):
    last=None
    for n in range(retries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 TradingResearch/1.0','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last=e; time.sleep(.5*(n+1))
    raise RuntimeError(f'HTTP_FAIL {last}')


def load_catalog():
    text=CATALOG.read_text(encoding='utf-8'); out={}
    for m in ('forex','crypto','metal','index'):
        z=re.search(rf"{m}:Object\.freeze\(\[(.*?)\]\)",text,re.S)
        if not z: raise RuntimeError('catalog parse '+m)
        out[m]=re.findall(r"'([^']+)'",z.group(1))
    return out


def yahoo_ticker(symbol,market):
    s=norm(symbol)
    if market=='forex': return USD_BASE.get(s,s+'=X')
    if market=='metal': return s+'=X'
    if market=='index': return INDEX_Y[s]
    raise KeyError((s,market))


def yahoo_history(symbol,market,start_ts,end_ts):
    t=yahoo_ticker(symbol,market)
    q=urllib.parse.urlencode({'period1':start_ts-7*86400,'period2':end_ts+3600,'interval':'1h','includePrePost':'true','events':'div,splits'})
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(t,safe='^=')+'?'+q
    j=get_json(url,timeout=45,retries=4)
    res=((j.get('chart') or {}).get('result') or [])
    if not res: raise RuntimeError('YAHOO_EMPTY '+str((j.get('chart') or {}).get('error')))
    r=res[0]; ts=r.get('timestamp') or []; qd=((r.get('indicators') or {}).get('quote') or [{}])[0]
    O=qd.get('open') or []; H=qd.get('high') or []; L=qd.get('low') or []; C=qd.get('close') or []; V=qd.get('volume') or []
    rows=[]
    for i,t0 in enumerate(ts):
        if not(start_ts<=int(t0)<=end_ts): continue
        vals=[f(a[i]) if i<len(a) else None for a in (O,H,L,C)]
        if None in vals: continue
        vol=f(V[i]) if i<len(V) else 0.0
        rows.append([int(t0),*vals,vol or 0.0])
    if not rows: raise RuntimeError('YAHOO_NO_ROWS '+t)
    return rows,'Yahoo Finance H1 '+t


def binance_history(symbol,start_ts,end_ts):
    cur=start_ts*1000; end=end_ts*1000; out=[]
    while cur<=end:
        q=urllib.parse.urlencode({'symbol':symbol,'interval':'1h','startTime':cur,'endTime':end,'limit':1000})
        j=get_json('https://api.binance.com/api/v3/klines?'+q,30,2)
        if not isinstance(j,list) or not j: break
        for x in j:
            out.append([int(x[0])//1000,float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5])])
        nxt=int(j[-1][0])+3600000
        if nxt<=cur: break
        cur=nxt
        if len(j)<1000: break
        time.sleep(.03)
    d={r[0]:r for r in out if start_ts<=r[0]<=end_ts}
    if not d: raise RuntimeError('BINANCE_EMPTY')
    return [d[k] for k in sorted(d)],'Binance Spot H1'


def bybit_history(symbol,start_ts,end_ts):
    cursor=end_ts*1000; start=start_ts*1000; out=[]; guard=0
    while cursor>=start and guard<8:
        guard+=1
        q=urllib.parse.urlencode({'category':'spot','symbol':symbol,'interval':'60','start':start,'end':cursor,'limit':1000})
        j=get_json('https://api.bybit.com/v5/market/kline?'+q,30,2)
        arr=((j.get('result') or {}).get('list') or []) if isinstance(j,dict) else []
        if not arr: break
        batch=[]
        for x in arr:
            t=int(x[0])//1000; batch.append(t)
            out.append([t,float(x[1]),float(x[2]),float(x[3]),float(x[4]),float(x[5])])
        oldest=min(batch); nxt=oldest*1000-1
        if nxt>=cursor: break
        cursor=nxt; time.sleep(.03)
    d={r[0]:r for r in out if start_ts<=r[0]<=end_ts}
    if not d: raise RuntimeError('BYBIT_EMPTY')
    return [d[k] for k in sorted(d)],'Bybit Spot H1'


def fetch_one(symbol,market,start_ts,end_ts):
    try:
        if market=='crypto':
            try: rows,src=binance_history(symbol,start_ts,end_ts)
            except Exception: rows,src=bybit_history(symbol,start_ts,end_ts)
        else: rows,src=yahoo_history(symbol,market,start_ts,end_ts)
        return symbol,rows,src,None
    except Exception as e:return symbol,[],None,str(e)[:500]


def ema(vals,p):
    o=[None]*len(vals)
    if len(vals)<p:return o
    e=sum(vals[:p])/p;o[p-1]=e;k=2/(p+1)
    for i in range(p,len(vals)):e=vals[i]*k+e*(1-k);o[i]=e
    return o


def rsi(vals,p=14):
    o=[None]*len(vals)
    if len(vals)<=p:return o
    g=l=0.0
    for i in range(1,p+1):
        d=vals[i]-vals[i-1];g+=max(d,0);l+=max(-d,0)
    ag,al=g/p,l/p;o[p]=100 if al==0 else 100-100/(1+ag/al)
    for i in range(p+1,len(vals)):
        d=vals[i]-vals[i-1];ag=(ag*(p-1)+max(d,0))/p;al=(al*(p-1)+max(-d,0))/p
        o[i]=100 if al==0 else 100-100/(1+ag/al)
    return o


def atr(rows,p=14):
    o=[None]*len(rows)
    if len(rows)<=p:return o
    tr=[max(rows[i][2]-rows[i][3],abs(rows[i][2]-rows[i-1][4]),abs(rows[i][3]-rows[i-1][4])) for i in range(1,len(rows))]
    a=sum(tr[:p])/p;o[p]=a
    for i in range(p+1,len(rows)):a=(a*(p-1)+tr[i-1])/p;o[i]=a
    return o


def generate(rows,market):
    c=[r[4] for r in rows];e20=ema(c,20);e50=ema(c,50);rv=rsi(c);av=atr(rows);out=[];last=defaultdict(lambda:-99)
    def emit(i,fam,side,strength,aligned):
        if i+1>=len(rows):return
        if i-last[(fam,side)]<3:return
        a=av[i]
        if not a:return
        hist=rows[max(0,i-8):i+1]; st=min(x[3] for x in hist) if side=='LONG' else max(x[2] for x in hist)
        out.append({'id':len(out),'i':i,'entry':i+1,'ts':rows[i][0]+3600,'family':fam,'side':side,'strength':strength,'aligned':aligned,'atr':a,'structure':st,'hour':datetime.fromtimestamp(rows[i][0]+3600,timezone.utc).hour,'market':market})
        last[(fam,side)]=i
    for i in range(60,len(rows)-14):
        if None in (e20[i],e50[i],rv[i],av[i]):continue
        a=av[i];cur=rows[i];prev=rows[i-1];body=abs(cur[4]-cur[1])/a if a else 0
        up=cur[4]>e20[i]>e50[i];dn=cur[4]<e20[i]<e50[i]
        hist=rows[i-12:i];hi=max(x[2] for x in hist);lo=min(x[3] for x in hist)
        if up and cur[3]<=e20[i]<=cur[4] and cur[4]>cur[1]:emit(i,'TREND_PULLBACK','LONG',body,True)
        if dn and cur[2]>=e20[i]>=cur[4] and cur[4]<cur[1]:emit(i,'TREND_PULLBACK','SHORT',body,True)
        if cur[4]>hi+.05*a and cur[4]>cur[1]:emit(i,'BREAKOUT','LONG',body,up)
        if cur[4]<lo-.05*a and cur[4]<cur[1]:emit(i,'BREAKOUT','SHORT',body,dn)
        if cur[3]<lo-.04*a and cur[4]>lo and cur[4]>cur[1]:emit(i,'SWEEP','LONG',(lo-cur[3])/a+body,not dn)
        if cur[2]>hi+.04*a and cur[4]<hi and cur[4]<cur[1]:emit(i,'SWEEP','SHORT',(cur[2]-hi)/a+body,not up)
        pr=rv[i-1]
        if pr is not None and pr<32 and rv[i]>38 and cur[4]>cur[1]:emit(i,'RSI_RECLAIM','LONG',(38-pr)/20+body,not dn)
        if pr is not None and pr>68 and rv[i]<62 and cur[4]<cur[1]:emit(i,'RSI_RECLAIM','SHORT',(pr-62)/20+body,not up)
        if up and 52<=rv[i]<=75 and cur[4]>max(x[2] for x in rows[i-3:i]) and body>=.25:emit(i,'MOMENTUM','LONG',body,True)
        if dn and 25<=rv[i]<=48 and cur[4]<min(x[3] for x in rows[i-3:i]) and body>=.25:emit(i,'MOMENTUM','SHORT',body,True)
        if not up and not dn and cur[4]<e20[i]-.7*a and rv[i]<32 and cur[4]>cur[1]:emit(i,'MEANREV','LONG',(e20[i]-cur[4])/a,False)
        if not up and not dn and cur[4]>e20[i]+.7*a and rv[i]>68 and cur[4]<cur[1]:emit(i,'MEANREV','SHORT',(cur[4]-e20[i])/a,False)
    return out


def simulate(rows,sig,market,stop,rr,horizon):
    i=sig['entry'];sg=1 if sig['side']=='LONG' else -1;a=sig['atr'];raw=rows[i][1]
    entry=raw+sg*COST_ATR[market]*a; floor=entry-sg*stop*a; struct=sig['structure']-sg*.05*a
    sl=min(struct,floor) if sg>0 else max(struct,floor);risk=abs(entry-sl)
    if not risk or risk>3*a:return ('SKIP',i)
    tp=entry+sg*rr*risk;last=min(len(rows)-1,i+horizon)
    for k in range(i,last+1):
        h,l=rows[k][2],rows[k][3];hs=l<=sl if sg>0 else h>=sl;ht=h>=tp if sg>0 else l<=tp
        if hs:return ('LOSS',k)
        if ht:return ('WIN',k)
    return ('TIMEOUT',last)


def metric(sigs,outcomes,key,t0,t1,hour=None,aligned=False,strength=0):
    xs=[s for s in sigs if t0<=s['ts']<t1 and (hour is None or s['hour']==hour) and (not aligned or s['aligned']) and s['strength']>=strength]
    xs.sort(key=lambda s:s['entry']);wins=losses=timeouts=0;last=-1;per=defaultdict(int);days=set();eligible=set();rr=key[1]
    for s in xs:
        dt=datetime.fromtimestamp(s['ts'],timezone.utc);day=dt.date().isoformat()
        if s['market']!='crypto' and dt.weekday()>=5:continue
        eligible.add(day)
        if per[day]>=3 or s['entry']<=last:continue
        st,ex=outcomes[s['id']][key]
        if st=='SKIP':continue
        per[day]+=1;days.add(day);last=ex
        if st=='WIN':wins+=1
        elif st=='LOSS':losses+=1
        else:timeouts+=1
    n=wins+losses+timeouts;wr=100*wins/n if n else 0;mr=(wins*rr-losses-timeouts)/n if n else 0
    return {'trades':n,'wins':wins,'losses':losses,'timeouts':timeouts,'winRate':round(wr,2),'meanR':round(mr,4),'daysTraded':len(days),'eligibleSignalDays':len(eligible),'maxTradesInDay':max(per.values(),default=0)}


def optimize(symbol,market,rows,src,error,start,end):
    r={'symbol':symbol,'market':market,'source':src,'dataError':error,'rows':len(rows)}
    if len(rows)<1000:r.update(pass_=False,reasons=['DATA_COVERAGE_FAIL']);r['pass']=False;return r
    r['firstBar']=iso(rows[0][0]);r['lastBar']=iso(rows[-1][0]);sigs=generate(rows,market);r['rawSignals']=len(sigs)
    if len(sigs)<MIN_TOTAL:r.update({'pass':False,'reasons':['INSUFFICIENT_SIGNALS']});return r
    keys=[(s,rr,h) for s in STOP_ATR for rr in ALLOWED_RR for h in HORIZON]
    outcomes={s['id']:{} for s in sigs}
    for s in sigs:
        for k in keys:outcomes[s['id']][k]=simulate(rows,s,market,*k)
    span=end-start;d1=start+int(span*.6);d2=start+int(span*.8);families=sorted(set(s['family'] for s in sigs));hours=[None]+list(range(24));cand=[]
    for fam in families:
        ff=[s for s in sigs if s['family']==fam]
        for hr in hours:
            for al in (False,True):
                for st in STRENGTH:
                    for k in keys:
                        dev=metric(ff,outcomes,k,start,d1,hr,al,st)
                        if dev['trades']<MIN_DEV or dev['meanR']<=0:continue
                        val=metric(ff,outcomes,k,d1,d2,hr,al,st)
                        if val['trades']<MIN_VAL:continue
                        score=(min(dev['winRate'],val['winRate']),val['winRate'],val['meanR'],val['trades'],dev['winRate'])
                        cand.append((score,fam,hr,al,st,k,ff,dev,val))
    if not cand:r.update({'pass':False,'reasons':['NO_DEV_VALIDATION_CANDIDATE']});return r
    cand.sort(key=lambda x:x[0],reverse=True);_,fam,hr,al,st,k,ff,dev,val=cand[0]
    oos=metric(ff,outcomes,k,d2,end+1,hr,al,st);full=metric(ff,outcomes,k,start,end+1,hr,al,st);stop,rr,h=k
    reasons=[]
    if full['trades']<MIN_TOTAL:reasons.append('MIN_TOTAL')
    if val['trades']<MIN_VAL:reasons.append('MIN_VAL')
    if oos['trades']<MIN_OOS:reasons.append('MIN_OOS')
    if full['winRate']<REQUIRED:reasons.append('FULL_WR_BELOW_80')
    if val['winRate']<REQUIRED:reasons.append('VAL_WR_BELOW_80')
    if oos['winRate']<REQUIRED:reasons.append('OOS_WR_BELOW_80')
    r.update({'pass':not reasons,'reasons':reasons,'profile':{'family':fam,'hourUTC':'ANY' if hr is None else hr,'requireAlignment':al,'minStrength':st,'stopAtr':stop,'rr':rr,'horizonHours':h},'dev':dev,'validation':val,'oos':oos,'full4m':full,'split':{'devEnd':iso(d1),'validationEnd':iso(d2)}})
    return r


def main():
    end_dt=now().replace(minute=0,second=0,microsecond=0);start_dt=end_dt-timedelta(days=DAYS);start,end=int(start_dt.timestamp()),int(end_dt.timestamp());cat=load_catalog();items=[(s,m) for m in ('forex','crypto','metal','index') for s in cat[m]]
    fetched={}
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        futs={ex.submit(fetch_one,s,m,start,end):(s,m) for s,m in items}
        for fut in cf.as_completed(futs):
            s,m=futs[fut];ss,rows,src,err=fut.result();fetched[ss]=(m,rows,src,err);print('FETCH',m,ss,len(rows),src or err,flush=True)
    results={}
    for s,m in items:
        mm,rows,src,err=fetched[s];print('BACKTEST',m,s,flush=True);results[s]=optimize(s,m,rows,src,err,start,end)
    passed=[s for s,x in results.items() if x.get('pass')];failed=[s for s,x in results.items() if not x.get('pass')];total=len(items)
    meta={'version':VERSION,'generatedAt':now().isoformat(),'start':start_dt.isoformat(),'end':end_dt.isoformat(),'timeframe':'H1','requiredWinRateInclusive':REQUIRED,'allowedRR':[1,2],'maxEntriesPerEligibleDay':3,'minTrades':MIN_TOTAL,'totalSymbols':total,'passCount':len(passed),'allPassed':len(passed)==total,'selectionProtocol':'60% DEV / 20% VALIDATION / 20% untouched OOS; OOS never tunes','sameBarRule':'SL conservative','timeoutRule':'non-win','dataMode':'public/no-secret'}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps({'meta':meta,'markets':{k:len(v) for k,v in cat.items()},'symbols':results},ensure_ascii=False,indent=2),encoding='utf-8');GATE.write_text(json.dumps({**meta,'passingSymbols':passed,'failingSymbols':failed},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'allPassed':meta['allPassed'],'passCount':len(passed),'totalSymbols':total,'failedCount':len(failed)},ensure_ascii=False))
    return 0

if __name__=='__main__':raise SystemExit(main())
