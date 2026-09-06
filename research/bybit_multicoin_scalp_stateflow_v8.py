#!/usr/bin/env python3
"""Event-based StateFlow Scalp V8 — fixed initial RR 1:1 / 1:2.

V8 drops probability fitting after V7 showed regime instability. It searches
interpretable structure + executed-flow setups per symbol/direction. Stops are
anchored to the actual sweep/retest/swing structure (with an ATR floor), then
TP is exactly 1R or 2R from that frozen initial risk.

Profile selection must be jointly strong on DEV and SHADOW. FINAL is consulted
once only after the profile is frozen. This remains historical research; Bybit
microstructure replay/forward-paper is required before production promotion.
"""
from __future__ import annotations
import argparse,dataclasses,json,math
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
import bybit_multicoin_scalp_flow_ml_v7 as d
import bybit_multicoin_scalp_rr_v4 as b4

TARGET=.80;WORST=.70;MIN_DEV=300;MIN_SHADOW=150;MIN_FINAL=220;MIN_WINDOW=45;COST=13.

@dataclass(frozen=True)
class P:
    family:str;side:int;rr:int;look:int;flow:float;vol:float;trend:float;trigger:float;buffer:float;min_atr:float;hold:int
@dataclass
class S:
    trades:int=0;wins:int=0;losses:int=0;timeouts:int=0;net:float=0.;gross:float=0.;cost:float=0.;dd:float=0.
    @property
    def wr(self):return self.wins/self.trades if self.trades else 0.
    @property
    def exp(self):return self.net/self.trades if self.trades else 0.
def sd(s):return {'trades':s.trades,'wins':s.wins,'losses':s.losses,'timeouts':s.timeouts,'win_rate':round(s.wr,6),'net_r':round(s.net,6),'gross_r':round(s.gross,6),'costs_r':round(s.cost,6),'expectancy_r':round(s.exp,6),'max_dd_r':round(s.dd,6)}

def signal(i,B,I,flow,vr,p):
    if i<60:return None
    x=B[i];prev=B[i-1];a=max(I['atr'][i],1e-12);side=p.side
    f3=sum(flow[i-2:i+1])/3*side
    if f3<p.flow or vr[i]<p.vol:return None
    sep=(I['e21'][i]-I['e50'][i])*side/a;eff=I['eff'][i]
    prior=B[max(1,i-p.look):i];hi=max(z.h for z in prior);lo=min(z.l for z in prior)
    bull=x.c>x.o;dirbar=bull if side>0 else not bull
    loc=(x.c-x.l)/max(x.h-x.l,1e-12) if side>0 else (x.h-x.c)/max(x.h-x.l,1e-12)
    anchor=None
    if p.family=='SWEEP_RECLAIM':
        if side>0 and x.l<lo-p.trigger*a and x.c>lo and dirbar and loc>.55:anchor=x.l-p.buffer*a
        elif side<0 and x.h>hi+p.trigger*a and x.c<hi and dirbar and loc>.55:anchor=x.h+p.buffer*a
    elif p.family=='BREAK_RETEST':
        if sep<p.trend or eff<.16:return None
        broke=False
        for j in range(max(60,i-3),i):
            q=B[max(1,j-p.look):j]
            if not q:continue
            hh=max(z.h for z in q);ll=min(z.l for z in q)
            if side>0 and B[j].c>hh+p.trigger*I['atr'][j]:broke=True
            if side<0 and B[j].c<ll-p.trigger*I['atr'][j]:broke=True
        if not broke:return None
        if side>0 and x.l<=hi+.18*a and x.c>hi and dirbar:anchor=min(z.l for z in B[i-3:i+1])-p.buffer*a
        elif side<0 and x.h>=lo-.18*a and x.c<lo and dirbar:anchor=max(z.h for z in B[i-3:i+1])+p.buffer*a
    elif p.family=='TREND_PULLBACK':
        if sep<p.trend or eff<p.trigger:return None
        aligned=I['e9'][i]>I['e21'][i]>I['e50'][i] if side>0 else I['e9'][i]<I['e21'][i]<I['e50'][i]
        if not aligned or not dirbar:return None
        if side>0 and min(z.l for z in B[i-3:i+1])<=I['e21'][i]+.12*a and x.c>I['e9'][i]:anchor=min(z.l for z in B[i-p.look:i+1])-p.buffer*a
        elif side<0 and max(z.h for z in B[i-3:i+1])>=I['e21'][i]-.12*a and x.c<I['e9'][i]:anchor=max(z.h for z in B[i-p.look:i+1])+p.buffer*a
    elif p.family=='RANGE_FADE':
        m=I['mean20'][i];ss=I['sd20'][i]
        if not math.isfinite(m) or not math.isfinite(ss) or ss<=0 or eff>p.trend:return None
        z=(x.c-m)/ss
        if side>0 and z<=-p.trigger and x.l<=lo and dirbar:anchor=min(z0.l for z0 in B[i-p.look:i+1])-p.buffer*a
        elif side<0 and z>=p.trigger and x.h>=hi and dirbar:anchor=max(z0.h for z0 in B[i-p.look:i+1])+p.buffer*a
    if anchor is None:return None
    # Return structure anchor; execution determines final ATR floor and RR.
    return anchor

def outcome(i,B,I,p,anchor,cost_mult=1.,delay=0):
    ei=i+1+delay
    if ei>=len(B)-2:return None
    entry=B[ei].o;a=max(I['atr'][i],1e-12);side=p.side
    struct=(entry-anchor)*side
    risk=max(struct,p.min_atr*a)
    if risk<=0:return None
    # Avoid microscopic cost-dominated stops and non-scalp giant stops.
    pct=risk/max(entry,1e-12)
    if pct<.0020 or pct>.015:return None
    sl=entry-side*risk;tp=entry+side*p.rr*risk;last=ei
    for j in range(ei,min(len(B),ei+p.hold+1)):
        q=B[j];last=j
        if (q.l<=sl if side>0 else q.h>=sl):g=-1.;kind='SL';break
        if (q.h>=tp if side>0 else q.l<=tp):g=float(p.rr);kind='TP';break
    else:g=side*(B[last].c-entry)/risk;kind='TIMEOUT'
    c=COST*cost_mult/10000*entry/risk
    return last,kind,g,g-c,c

def run(B,I,flow,vr,p,lo,hi,cost_mult=1.,delay=0):
    s=S();eq=peak=0.;i=max(60,lo)
    while i<min(hi,len(B)-50):
        a=signal(i,B,I,flow,vr,p)
        if a is None:i+=1;continue
        z=outcome(i,B,I,p,a,cost_mult,delay)
        if not z:i+=1;continue
        last,k,g,n,c=z
        if last>hi:break
        s.trades+=1;s.gross+=g;s.net+=n;s.cost+=c
        if k=='TP':s.wins+=1
        else:s.losses+=1;s.timeouts+=1 if k=='TIMEOUT' else 0
        eq+=n;peak=max(peak,eq);s.dd=max(s.dd,peak-eq);i=last+1
    return s

def profiles(side):
    out=[]
    for rr in (1,2):
      for fam in ('SWEEP_RECLAIM','BREAK_RETEST','TREND_PULLBACK','RANGE_FADE'):
       looks=(6,12,24) if fam!='TREND_PULLBACK' else (4,8,12)
       for look in looks:
        for flow in (.02,.08,.16,.24):
         for vol in (.75,1.,1.25):
          for buf in (.05,.12):
           for floor in (1.2,1.8,2.4):
            if fam=='SWEEP_RECLAIM': pars=((0.,0.02),(0.,0.08))
            elif fam=='BREAK_RETEST':pars=((.12,.02),(.28,.06))
            elif fam=='TREND_PULLBACK':pars=((.12,.16),(.28,.28))
            else:pars=((.34,1.35),(.26,1.75))
            for trend,trig in pars:out.append(P(fam,side,rr,look,flow,vol,trend,trig,buf,floor,24 if rr==1 else 36))
    return out

def score(dev,sh):
    enough=dev.trades>=MIN_DEV and sh.trades>=MIN_SHADOW
    econ=dev.exp>0 and sh.exp>0
    return (1 if enough and econ else 0,min(dev.wr,sh.wr),(dev.wr+sh.wr)/2,(dev.exp+sh.exp)/2,-max(dev.dd,sh.dd),sh.trades)

def cal(sym,B,man):
    sp=d.split(B)
    if not sp:return {'symbol':sym,'status':'DATA_GAP','reason':'no clean block','manifest':man}
    di,si,fw,shift=sp;base,I,flow,vr,qr,tr,rv12,rv48=d.prep(B)
    ranked=[]
    for side in (1,-1):
      for p in profiles(side):
        dev=run(B,I,flow,vr,p,*di)
        # Reject obviously sparse/poor DEV before spending SHADOW compute.
        if dev.trades<MIN_DEV//2:continue
        sh=run(B,I,flow,vr,p,*si);ranked.append((score(dev,sh),p,dev,sh))
    if not ranked:return {'symbol':sym,'status':'NO_PROFILE','reason':'no sufficiently active setup','manifest':man}
    ranked.sort(key=lambda x:x[0],reverse=True);_,p,dev,sh=ranked[0]
    fs=[run(B,I,flow,vr,p,*w) for w in fw];agg=S()
    for e in fs:
        agg.trades+=e.trades;agg.wins+=e.wins;agg.losses+=e.losses;agg.timeouts+=e.timeouts;agg.net+=e.net;agg.gross+=e.gross;agg.cost+=e.cost;agg.dd=max(agg.dd,e.dd)
    worst=min((e.wr for e in fs),default=0.)
    def st(mult=1.,delay=0):
        xs=[run(B,I,flow,vr,p,*w,mult,delay) for w in fw];t=sum(x.trades for x in xs);return sum(x.net for x in xs)/t if t else -999.
    a,b,c=st(1.5),st(2),st(1,1);rob=a>0 and b>0 and c>0;baseok=agg.wr>=TARGET and worst>=WORST and agg.trades>=MIN_FINAL and all(x.trades>=MIN_WINDOW for x in fs) and agg.exp>0 and all(x.net>0 for x in fs);locked=baseok and rob
    rs=[]
    if agg.wr<TARGET:rs.append('FINAL_WR_LT_80')
    if worst<WORST:rs.append('WORST_LT_70')
    if agg.trades<MIN_FINAL:rs.append('FINAL_TRADES_LT_220')
    if any(x.trades<MIN_WINDOW for x in fs):rs.append('WINDOW_TRADES_LT_45')
    if agg.exp<=0:rs.append('NONPOSITIVE_EXPECTANCY')
    if any(x.net<=0 for x in fs):rs.append('NEGATIVE_WINDOW_R')
    if not rob:rs.append('STRESS_FAIL')
    return {'symbol':sym,'status':'LOCKED' if locked else 'RESEARCH','reason':'PASS' if locked else rs,'profile_version':'stateflow_event_v8','manifest':man,'data_gap_shift_days':shift,'profile':dataclasses.asdict(p),'dev':sd(dev),'shadow':sd(sh),'final_windows':[{'range':[b4.iso(B[w[0]].ts),b4.iso(B[w[1]].ts)],**sd(e)} for w,e in zip(fw,fs)],'final_aggregate':sd(agg),'worst_final_window_wr':round(worst,6),'stress':{'cost_1_5x_expectancy':round(a,6),'cost_2x_expectancy':round(b,6),'delay_1bar_expectancy':round(c,6),'pass':rob},'limitations':['USD-M futures historical proxy','Bybit full microstructure replay/forward test required']}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--symbols',default=','.join(b4.UNIVERSE));ap.add_argument('--out',default='research/results/stateflow_v8.json');a=ap.parse_args();res=[];syms=[x.strip().upper() for x in a.symbols.split(',') if x.strip()];print('=== STATEFLOW EVENT SCALP V8 ===',flush=True)
    for n,sym in enumerate(syms,1):
        print(f'[{n}/{len(syms)}] {sym}',flush=True)
        try:B,m=d.load(sym);r=cal(sym,B,m)
        except Exception as e:r={'symbol':sym,'status':'ERROR','reason':repr(e)}
        res.append(r)
        if r.get('final_aggregate'):
            x=r['final_aggregate'];p=r['profile'];print(f"RESULT {sym} {r['status']} WR={100*x['win_rate']:.2f}% N={x['trades']} ExpR={x['expectancy_r']:+.4f} worst={100*r['worst_final_window_wr']:.2f}% {p['family']} {'LONG' if p['side']>0 else 'SHORT'} RR{p['rr']} DEV={100*r['dev']['win_rate']:.2f}% SHADOW={100*r['shadow']['win_rate']:.2f}% reason={r['reason']}",flush=True)
        else:print('RESULT',sym,r['status'],r.get('reason'),flush=True)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True);s={'generated_at':datetime.now(timezone.utc).isoformat(),'engine':'STATEFLOW_EVENT_SCALP_V8','research_only':True,'locked':[r['symbol'] for r in res if r.get('status')=='LOCKED'],'unresolved':[r['symbol'] for r in res if r.get('status')!='LOCKED'],'results':res};out.write_text(json.dumps(s,ensure_ascii=False,indent=2));print('LOCKED',s['locked'],flush=True);print('REPORT',out,flush=True)
if __name__=='__main__':main()
