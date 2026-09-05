#!/usr/bin/env python3
"""Scalp Flow-ML V7 — fixed RR 1:1/1:2, per symbol.

Adds information absent from V6 while staying causal and available in USD-M
5m futures kline archives: taker-buy volume ratio, trade count intensity,
quote-volume intensity, flow persistence/divergence, multi-horizon trend and
volatility state. Searches stop distance 1.5..3 ATR so round-trip costs do not
consume most of 1R. TP remains exactly 1R or 2R from the initial SL.

DEV trains models. SHADOW selects direction/RR/stop/filter/threshold. FINAL is
read only after freeze. A failure is RESEARCH, never silently promoted.
"""
from __future__ import annotations
import argparse,csv,io,json,math,time,urllib.request,urllib.error,zipfile
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
import bybit_multicoin_scalp_rr_v4 as b4

ARCH='https://data.binance.vision/data/futures/um/monthly/klines'
MONTHS=23; RR_SET=(1,2); STOP_SET=(1.5,2.0,2.5,3.0)
TARGET=.80; WORST=.70; MIN_SHADOW=150; MIN_FINAL=220; MIN_WINDOW=45; COST_BPS=13.
DEV_DAYS=240;SHADOW_DAYS=120;FINAL_DAYS=45;FINAL_WINDOWS=4;GAP_DAYS=10

@dataclass(frozen=True)
class Bar:
    ts:int;o:float;h:float;l:float;c:float;v:float;qv:float;trades:float;taker:float
@dataclass
class S:
    trades:int=0;wins:int=0;losses:int=0;timeouts:int=0;net:float=0.;gross:float=0.;cost:float=0.;dd:float=0.
    @property
    def wr(self):return self.wins/self.trades if self.trades else 0.
    @property
    def exp(self):return self.net/self.trades if self.trades else 0.
def sd(s):return {'trades':s.trades,'wins':s.wins,'losses':s.losses,'timeouts':s.timeouts,'win_rate':round(s.wr,6),'net_r':round(s.net,6),'gross_r':round(s.gross,6),'costs_r':round(s.cost,6),'expectancy_r':round(s.exp,6),'max_dd_r':round(s.dd,6)}

def months(y,m,n):
    a=[]
    for _ in range(n):
        a.append((y,m));m-=1
        if m==0:y-=1;m=12
    return list(reversed(a))
def get(url):
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'flow-v7'}),timeout=45) as r:return r.read()
        except urllib.error.HTTPError as e:
            if e.code==404:return None
            last=e
        except Exception as e:last=e
        time.sleep(.3*2**k)
    raise RuntimeError(last)
def load(sym):
    now=datetime.now(timezone.utc);y,m=now.year,now.month-1
    if m==0:y-=1;m=12
    rows={};miss=[]
    for yy,mm in months(y,m,MONTHS):
        ym=f'{yy:04d}-{mm:02d}';url=f'{ARCH}/{sym}/5m/{sym}-5m-{ym}.zip';raw=get(url)
        if raw is None:miss.append(ym);continue
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            name=[x for x in z.namelist() if x.endswith('.csv')][0];text=z.read(name).decode('utf-8-sig')
        for r in csv.reader(io.StringIO(text)):
            if not r or not r[0].isdigit():continue
            try:
                ts=int(r[0]);ts=ts//1000 if ts>10**15 else ts
                rows[ts]=Bar(ts,float(r[1]),float(r[2]),float(r[3]),float(r[4]),float(r[5]),float(r[7]),float(r[8]),float(r[9]))
            except Exception:pass
    B=[rows[k] for k in sorted(rows)]
    if len(B)<100000:raise RuntimeError(f'insufficient bars {len(B)} missing={miss}')
    gaps=[(x.ts,y.ts) for x,y in zip(B,B[1:]) if y.ts-x.ts!=300000];exp=(B[-1].ts-B[0].ts)//300000+1
    return B,{'source':'Binance USD-M futures kline proxy','target':'Bybit Linear','symbol':sym,'interval':'5m','bars':len(B),'coverage':len(B)/exp,'gaps':len(gaps),'missing_months':miss,'first':b4.iso(B[0].ts),'last':b4.iso(B[-1].ts)}

def split(B):
    for sh in range(0,61,5):
        fe=B[-1].ts-sh*b4.DAY_MS;fs=fe-FINAL_WINDOWS*FINAL_DAYS*b4.DAY_MS+b4.INTERVAL_MS
        se=fs-GAP_DAYS*b4.DAY_MS-b4.INTERVAL_MS;ss=se-SHADOW_DAYS*b4.DAY_MS+b4.INTERVAL_MS
        de=ss-GAP_DAYS*b4.DAY_MS-b4.INTERVAL_MS;ds=de-DEV_DAYS*b4.DAY_MS+b4.INTERVAL_MS
        di=b4.idx(B,ds,de);si=b4.idx(B,ss,se)
        if not di or not si or not b4.clean(B,*di) or not b4.clean(B,*si):continue
        fw=[];ok=True
        for k in range(FINAL_WINDOWS):
            st=fs+k*FINAL_DAYS*b4.DAY_MS;en=st+FINAL_DAYS*b4.DAY_MS-b4.INTERVAL_MS;z=b4.idx(B,st,en)
            if not z or not b4.clean(B,*z):ok=False;break
            fw.append(z)
        if ok:return di,si,fw,sh
    return None

def prep(B):
    base=[b4.Bar(x.ts,x.o,x.h,x.l,x.c,x.v) for x in B];I=b4.prep(base);n=len(B)
    flow=np.zeros(n);vr=np.ones(n);qr=np.ones(n);tr=np.ones(n);rv12=np.zeros(n);rv48=np.zeros(n)
    vols=np.asarray([x.v for x in B]);qvs=np.asarray([x.qv for x in B]);nts=np.asarray([x.trades for x in B]);cs=np.asarray([x.c for x in B])
    for i in range(60,n):
        flow[i]=2*B[i].taker/max(B[i].v,1e-12)-1
        vr[i]=B[i].v/max(float(np.mean(vols[i-20:i])),1e-12)
        qr[i]=B[i].qv/max(float(np.mean(qvs[i-20:i])),1e-12)
        tr[i]=B[i].trades/max(float(np.mean(nts[i-20:i])),1e-12)
        rr=np.diff(np.log(cs[i-12:i+1]));rv12[i]=float(np.std(rr))
        rr=np.diff(np.log(cs[i-48:i+1]));rv48[i]=float(np.std(rr))
    return base,I,flow,vr,qr,tr,rv12,rv48

def feats(B,I,flow,vr,qr,tr,rv12,rv48):
    n=len(B);X=np.zeros((n,36),np.float32);c=np.asarray([x.c for x in B])
    for i in range(60,n):
        a=max(I['atr'][i],1e-12);x=B[i];rng=max(x.h-x.l,1e-12);m=I['mean20'][i];ss=I['sd20'][i]
        z=(x.c-m)/ss if math.isfinite(m) and math.isfinite(ss) and ss>0 else 0.;hi=I['hi20'][i];lo=I['lo20'][i]
        f3=float(np.mean(flow[i-2:i+1]));f6=float(np.mean(flow[i-5:i+1]));f12=float(np.mean(flow[i-11:i+1]));fa=float(np.mean(np.abs(flow[i-5:i+1])))
        hour=(x.ts//3600000)%24;dow=(x.ts//86400000+4)%7
        X[i]=[(c[i]-c[i-k])/a for k in (1,2,3,6,12,24,48)]+[
            (I['e9'][i]-I['e21'][i])/a,(I['e21'][i]-I['e50'][i])/a,(I['e9'][i]-I['e9'][i-6])/a,
            I['rsi'][i]/100.,I['eff'][i],I['mom3'][i]/4.,(x.c-x.o)/a,(x.h-x.l)/a,(x.c-x.l)/rng,z/4.,
            ((hi-x.c)/a if math.isfinite(hi) else 0.)/5.,((x.c-lo)/a if math.isfinite(lo) else 0.)/5.,a/max(x.c,1e-12)*100.,
            flow[i],f3,f6,f12,fa,min(vr[i],5.)/5.,min(qr[i],5.)/5.,min(tr[i],5.)/5.,
            flow[i]*min(vr[i],3.),f3*((c[i]-c[i-3])/a),rv12[i]*1000.,rv48[i]*1000.,rv12[i]/max(rv48[i],1e-9),
            math.sin(2*math.pi*hour/24.),math.cos(2*math.pi*hour/24.),math.sin(2*math.pi*dow/7.)]
    return X

def out(i,B,I,side,rr,stop_atr,cost_mult=1.,delay=0):
    ei=i+1+delay
    if ei>=len(B)-1:return None
    entry=B[ei].o;d=stop_atr*max(I['atr'][i],1e-12)
    if d/entry<.0008:return None
    sl=entry-side*d;tp=entry+side*rr*d;hold=24 if rr==1 else 36;last=ei
    for j in range(ei,min(len(B),ei+hold+1)):
        q=B[j];last=j
        if (q.l<=sl if side>0 else q.h>=sl):g=-1.;kind='SL';break
        if (q.h>=tp if side>0 else q.l<=tp):g=float(rr);kind='TP';break
    else:g=side*(B[last].c-entry)/d;kind='TIMEOUT'
    cost=COST_BPS*cost_mult/10000*entry/d;return last,kind,g,g-cost,cost

def labels(B,I,lo,hi,side,rr,stop):
    inds=[];ys=[]
    for i in range(max(60,lo),min(hi,len(B)-40)):
        z=out(i,B,I,side,rr,stop)
        if z:inds.append(i);ys.append(1 if z[1]=='TP' else 0)
    return np.asarray(inds,np.int32),np.asarray(ys,np.int8)
def fit(X,B,I,di,side,rr,stop):
    ix,y=labels(B,I,*di,side,rr,stop)
    if len(ix)<5000 or y.sum()<200:return None
    mdl=HistGradientBoostingClassifier(learning_rate=.055,max_iter=160,max_leaf_nodes=31,min_samples_leaf=80,l2_regularization=2.,random_state=260905,early_stopping=True,validation_fraction=.15,n_iter_no_change=16)
    mdl.fit(X[ix],y);return mdl

def evalp(mdl,X,B,I,flow,vr,lo,hi,side,rr,stop,th,fmin,vmin,mode,cost_mult=1.,delay=0,probs=None):
    e=S();eq=peak=0.;base=max(60,lo)
    if probs is None:probs=mdl.predict_proba(X[base:hi+1])[:,1]
    i=base
    while i<min(hi,len(B)-40):
        if probs[i-base]<th:i+=1;continue
        f3=float(np.mean(flow[i-2:i+1]))*side
        if f3<fmin or vr[i]<vmin:i+=1;continue
        trend=(I['e21'][i]-I['e50'][i])*side/max(I['atr'][i],1e-12)
        eff=I['eff'][i]
        if mode==1 and not (trend>.12 and eff>.18):i+=1;continue
        if mode==2 and not (trend>.28 and eff>.28):i+=1;continue
        if mode==3 and not (eff<.32):i+=1;continue
        z=out(i,B,I,side,rr,stop,cost_mult,delay)
        if not z:i+=1;continue
        last,k,g,n,c=z
        if last>hi:break
        e.trades+=1;e.gross+=g;e.net+=n;e.cost+=c
        if k=='TP':e.wins+=1
        else:e.losses+=1;e.timeouts+=1 if k=='TIMEOUT' else 0
        eq+=n;peak=max(peak,eq);e.dd=max(e.dd,peak-eq);i=last+1
    return e

def select(mdl,X,B,I,flow,vr,si,side,rr,stop):
    lo,hi=si;base=max(60,lo);pr=mdl.predict_proba(X[base:hi+1])[:,1];best=None
    for th in np.arange(.50,.951,.025):
      for fm in (0.,.08,.16,.24):
       for vm in (.75,1.,1.25):
        for mode in (0,1,2,3):
            e=evalp(mdl,X,B,I,flow,vr,lo,hi,side,rr,stop,float(th),fm,vm,mode,probs=pr)
            enough=e.trades>=MIN_SHADOW;score=(1 if enough else 0,1 if enough and e.exp>0 else 0,e.wr,e.exp,-e.dd,e.trades)
            if best is None or score>best[0]:best=(score,float(th),fm,vm,mode,e)
    return best

def cal(sym,B,man):
    sp=split(B)
    if not sp:return {'symbol':sym,'status':'DATA_GAP','reason':'no clean block','manifest':man}
    di,si,fw,shift=sp;base,I,flow,vr,qr,tr,rv12,rv48=prep(B);X=feats(B,I,flow,vr,qr,tr,rv12,rv48);cand=[]
    for side in (1,-1):
     for rr in RR_SET:
      for stop in STOP_SET:
        mdl=fit(X,B,I,di,side,rr,stop)
        if mdl is None:continue
        z=select(mdl,X,B,I,flow,vr,si,side,rr,stop);cand.append((z[0],side,rr,stop,*z[1:],mdl))
    if not cand:return {'symbol':sym,'status':'NO_MODEL','reason':'none','manifest':man}
    cand.sort(key=lambda x:x[0],reverse=True);_,side,rr,stop,th,fm,vm,mode,shadow,mdl=cand[0]
    fs=[evalp(mdl,X,B,I,flow,vr,*w,side,rr,stop,th,fm,vm,mode) for w in fw]
    agg=S()
    for e in fs:
        agg.trades+=e.trades;agg.wins+=e.wins;agg.losses+=e.losses;agg.timeouts+=e.timeouts;agg.net+=e.net;agg.gross+=e.gross;agg.cost+=e.cost;agg.dd=max(agg.dd,e.dd)
    worst=min((e.wr for e in fs),default=0.)
    def stres(mult=1.,delay=0):
        xs=[evalp(mdl,X,B,I,flow,vr,*w,side,rr,stop,th,fm,vm,mode,mult,delay) for w in fw];t=sum(e.trades for e in xs);return sum(e.net for e in xs)/t if t else -999.
    s15=stres(1.5);s20=stres(2.);sdel=stres(1.,1);rob=s15>0 and s20>0 and sdel>0
    baseok=agg.wr>=TARGET and worst>=WORST and agg.trades>=MIN_FINAL and all(e.trades>=MIN_WINDOW for e in fs) and agg.exp>0 and all(e.net>0 for e in fs);locked=baseok and rob
    rs=[]
    if agg.wr<TARGET:rs.append('FINAL_WR_LT_80')
    if worst<WORST:rs.append('WORST_LT_70')
    if agg.trades<MIN_FINAL:rs.append('FINAL_TRADES_LT_220')
    if any(e.trades<MIN_WINDOW for e in fs):rs.append('WINDOW_TRADES_LT_45')
    if agg.exp<=0:rs.append('NONPOSITIVE_EXPECTANCY')
    if any(e.net<=0 for e in fs):rs.append('NEGATIVE_WINDOW_R')
    if not rob:rs.append('STRESS_FAIL')
    return {'symbol':sym,'status':'LOCKED' if locked else 'RESEARCH','reason':'PASS' if locked else rs,'profile_version':'flow_ml_v7','manifest':man,'data_gap_shift_days':shift,
      'profile':{'direction':'LONG' if side>0 else 'SHORT','side':side,'rr':rr,'stop_atr':stop,'probability_threshold':round(th,4),'flow3_min':fm,'volume_ratio_min':vm,'regime_mode':mode,'hold_bars':24 if rr==1 else 36},
      'shadow':sd(shadow),'final_windows':[{'range':[b4.iso(B[w[0]].ts),b4.iso(B[w[1]].ts)],**sd(e)} for w,e in zip(fw,fs)],'final_aggregate':sd(agg),'worst_final_window_wr':round(worst,6),
      'stress':{'cost_1_5x_expectancy':round(s15,6),'cost_2x_expectancy':round(s20,6),'delay_1bar_expectancy':round(sdel,6),'pass':rob},
      'limitations':['Binance USD-M futures proxy for historical research','Bybit microstructure replay/forward test still required']}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--symbols',default=','.join(b4.UNIVERSE));ap.add_argument('--out',default='research/results/flow_ml_v7.json');a=ap.parse_args();syms=[x.strip().upper() for x in a.symbols.split(',') if x.strip()];res=[]
    print('=== MULTICOIN SCALP FLOW-ML V7 ===',flush=True)
    for n,sym in enumerate(syms,1):
        print(f'[{n}/{len(syms)}] {sym}',flush=True)
        try:B,m=load(sym);print(f"DATA {sym} bars={m['bars']} gaps={m['gaps']}",flush=True);r=cal(sym,B,m)
        except Exception as e:r={'symbol':sym,'status':'ERROR','reason':repr(e)}
        res.append(r)
        if r.get('final_aggregate'):
            x=r['final_aggregate'];p=r['profile'];print(f"RESULT {sym} {r['status']} WR={100*x['win_rate']:.2f}% N={x['trades']} ExpR={x['expectancy_r']:+.4f} worst={100*r['worst_final_window_wr']:.2f}% {p['direction']} RR{p['rr']} stop={p['stop_atr']} flow={p['flow3_min']} vol={p['volume_ratio_min']} mode={p['regime_mode']} SHADOW={100*r['shadow']['win_rate']:.2f}% reason={r['reason']}",flush=True)
        else:print('RESULT',sym,r['status'],r.get('reason'),flush=True)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);summary={'generated_at':datetime.now(timezone.utc).isoformat(),'engine':'MULTICOIN_SCALP_FLOW_ML_V7','research_only':True,'locked':[r['symbol'] for r in res if r.get('status')=='LOCKED'],'unresolved':[r['symbol'] for r in res if r.get('status')!='LOCKED'],'results':res};out.write_text(json.dumps(summary,ensure_ascii=False,indent=2));print('LOCKED',summary['locked'],flush=True);print('REPORT',out,flush=True)
if __name__=='__main__':main()
