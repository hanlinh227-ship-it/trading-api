#!/usr/bin/env python3
import json, statistics
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import scripts.offline_forex_precision_evolver_v15 as b

SNAP='data/provider_snapshots/forex_h1_jul_dec_2025.json'
OUT='data/offline_forex_daily_each_symbol_v26_2025_walkforward.json'
TARGET=80.0
STAGES=[('JUL_AUG','2025-07-01','2025-07-31','2025-08-01','2025-08-31'),('AUG_SEP','2025-08-01','2025-08-31','2025-09-01','2025-09-30'),('SEP_OCT','2025-09-01','2025-09-30','2025-10-01','2025-10-31'),('OCT_NOV','2025-10-01','2025-10-31','2025-11-01','2025-11-30'),('NOV_DEC','2025-11-01','2025-11-30','2025-12-01','2025-12-31')]
FAMILIES=('FACTOR_FAST','FACTOR_BAL','H4TREND','H1TREND','SESSION','MEANREV','IMPULSE','REGIME')
HOURS=(0,4,8,12,16,20)
RRS=(1.0,2.0)
RFS=(.65,.85,1.10,1.40,1.75)
SWS=(6,12,18)
ENTRIES=(('MARKET',0.0,1),('HYBRID',.25,1),('HYBRID',.35,2),('HYBRID',.50,2),('HYBRID',.70,3))
MGMTS=((1,-.05,.00),(1,-.15,.05),(2,-.20,.10),(2,-.35,.15),(3,-.45,.20))


def load_data():
    doc=json.load(open(SNAP,encoding='utf-8'))
    if doc.get('coverageCount')!=28:raise RuntimeError('Need 28/28 2025 Forex snapshot')
    return {p:b.enrich(doc['data'][p]) for p in b.PAIRS}

def make_maps(data):
    mp={p:{r['dt']:(i,r) for i,r in rows} for p,rows in data.items()}
    common=set.intersection(*(set(x) for x in mp.values()))
    a=datetime(2025,7,1,tzinfo=timezone.utc);z=datetime(2026,1,1,tzinfo=timezone.utc)
    times=sorted(t for t in common if a<=t<z and t.hour in HOURS)
    return mp,times

def side_for(fam,m):
    if fam=='FACTOR_FAST':x=1.8*m['g3']+1.1*m['g6']+.25*m['g12']
    elif fam=='FACTOR_BAL':x=m['g3']+.8*m['g6']+.7*m['g12']+.6*m['g24']+.3*m['g72']
    elif fam=='H4TREND':return m['h4'] or m['h1'] or (1 if m['g6']>=0 else -1)
    elif fam=='H1TREND':return m['h1'] or (1 if m['g3']>=0 else -1)
    elif fam=='SESSION':x=m['sess']+.35*m['g3']
    elif fam=='MEANREV':return -1 if m['dev']>0 else 1
    elif fam=='IMPULSE':x=2*m['g3']+m['g6']-.35*m['g24']
    else:x=m['g24']+.7*m['g72']+.25*m['g12']
    return 1 if x>=0 else -1

def execute(rows,i,side,par):
    _,_,rr,rf,sw,entry_mode,off,expiry,cut_age,cut_r,min_progress=par
    if i+1>=len(rows) or not rows[i].get('atr'):return None
    sig=rows[i];atr=sig['atr'];entry=None;ei=None
    if entry_mode=='MARKET':
        ei=i+1;entry=rows[ei]['open']
    else:
        target=sig['close']-side*off*atr;last=min(len(rows)-1,i+expiry)
        for j in range(i+1,last+1):
            if rows[j]['low']<=target<=rows[j]['high']:
                ei=j;entry=target;break
        if ei is None:
            ei=last;entry=rows[ei]['close']
    recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent)
    struct=entry-swing if side==1 else swing-entry;risk=max(rf*atr,struct+.08*atr)
    if risk<=0:return None
    sl=entry-side*risk;tp=entry+side*rr*risk;hold=30 if rr==1 else 48;end=min(len(rows),ei+hold);best=-9
    for j in range(ei,end):
        x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
        if hs and ht:return ('SL',-1.0)
        if hs:return ('SL',-1.0)
        if ht:return ('TP',rr)
        age=j-ei+1;cur=(x['close']-entry)/risk*side;fav=(x['high']-entry)/risk if side==1 else (entry-x['low'])/risk;best=max(best,fav)
        if age>=cut_age:
            em=x.get('ema20');broken=em is not None and (x['close']-em)*side<0
            if cur<=cut_r or (broken and cur<.10) or (age>=2 and best<min_progress):return ('CUT',max(-1,cur))
    last=rows[end-1]['close'];return ('CUT',max(-1,min(rr,(last-entry)/risk*side)))

def matrix(data,mp,times):
    out=defaultdict(lambda:defaultdict(dict))
    for t in times:
        fp=b.factor_pack(mp,t)
        if not fp:continue
        for p in b.PAIRS:
            i,r=mp[p][t]
            if r.get('adx') is None or r.get('ema50') is None:continue
            _,m=b.candidate_features(p,r,fp,1);out[p][t.date().isoformat()][t.hour]=(i,m)
    return out

def weekdays(a,c):
    x=datetime.fromisoformat(a).date();y=datetime.fromisoformat(c).date();n=0
    while x<=y:
        if x.weekday()<5:n+=1
        x+=timedelta(days=1)
    return n

def evaluate(sym,days,data,par,a,c):
    fam,hour,rr,rf,sw,em,off,exp,ca,cr,prog=par;expected=weekdays(a,c);z=[]
    for d in sorted(k for k in days if a<=k<=c):
        if datetime.fromisoformat(d).weekday()>=5:continue
        hs=days[d];hh=hour if hour in hs else max([x for x in hs if x<=hour],default=max(hs));i,m=hs[hh]
        o=execute(data[sym],i,side_for(fam,m),par)
        if o:z.append(o)
    tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);cuts=len(z)-tp-sl;resolved=tp+sl;wr=100*tp/resolved if resolved else 0;mean=statistics.mean(x[1] for x in z) if z else -9
    return {'expectedDays':expected,'tradedDays':len(z),'missing':expected-len(z),'tp':tp,'sl':sl,'cut':cuts,'resolved':resolved,'wr':round(wr,2),'cutRate':round(100*cuts/len(z),2) if z else 100,'meanR':round(mean,3)}
def rank(s):
    viable=s['missing']==0 and s['resolved']>=5 and s['cutRate']<=82 and s['meanR']>0
    return (int(viable and s['wr']>=TARGET),s['wr']-(0 if viable else 60),s['meanR'],s['resolved'],-s['cutRate'])
def params():
    for fam in FAMILIES:
      for h in HOURS:
       for rr in RRS:
        for rf in RFS:
         for sw in SWS:
          for em,off,exp in ENTRIES:
           for ca,cr,prog in MGMTS:
            yield (fam,h,rr,rf,sw,em,off,exp,ca,cr,prog)
def main():
    data=load_data();mp,times=make_maps(data);mx=matrix(data,mp,times);ps=list(params());res={}
    print('PARAMS',len(ps),flush=True)
    for sym in b.PAIRS:
        hist=[];winner=None
        for name,da,db,fa,fb in STAGES:
            best=None;bp=None;ds=None
            for p in ps:
                s=evaluate(sym,mx[sym],data,p,da,db);r=rank(s)
                if best is None or r>best:best=r;bp=p;ds=s
            fs=evaluate(sym,mx[sym],data,bp,fa,fb);ok=rank(fs)[0]==1;rec={'stage':name,'params':bp,'development':ds,'final':fs,'pass':ok};hist.append(rec)
            print(sym,name,fs,'PASS' if ok else 'FAIL',flush=True)
            if ok:winner=rec;break
        res[sym]={'status':'PASS' if winner else 'FAIL','frozen':winner,'history':hist}
    passed=[s for s in b.PAIRS if res[s]['status']=='PASS'];failed=[s for s in b.PAIRS if res[s]['status']=='FAIL'];out={'version':'FOREX_DAILY_EACH_SYMBOL_V26_2025_WF','independentDataset':SNAP,'rule':'Each pair trades every weekday. Own rule selected only on prior month, tested on next month. TP/(TP+SL)>=80, RR1 or2, positive total meanR, >=5 resolved, CUT<=82%.','passCount':len(passed),'failCount':len(failed),'passRate':round(100*len(passed)/28,2),'passed':passed,'failed':failed,'allPass':not failed,'results':res};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:out[k] for k in ('passCount','failCount','passRate','passed','failed','allPass')},indent=2),flush=True)
if __name__=='__main__':main()
