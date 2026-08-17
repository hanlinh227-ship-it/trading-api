#!/usr/bin/env python3
import json, statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
import scripts.offline_forex_precision_evolver_v15 as b
import scripts.offline_forex_daily_per_symbol_v18 as old

OUT='data/offline_forex_intraday_nocut_v62.json'
TARGET=80.0
WINDOWS=old.WINDOWS
DIRS=('BOTH','BUY','SELL')
MONTHS=[('MAY','2026-05-01','2026-05-31'),('JUNE','2026-06-01','2026-06-30'),('JULY','2026-07-01','2026-07-31')]
CFGS=[(rr,rf,sw) for rr in (1.0,2.0) for rf in (.60,.75,1.0,1.25,1.5,2.0) for sw in (4,8,12)]
MODEL_SPECS=[('HGB',4,12),('HGB',5,20),('ET',10,8),('ET',14,5)]
THRESH=(.55,.62,.70,.78)
MARGINS=(0.0,.06)
MAXTRADES=(1,2,3)
CCY_DRIVERS={
 'USD':['Fed/FOMC','US CPI/PCE/NFP','US10Y and DXY','Treasury/liquidity conditions'],
 'EUR':['ECB','Eurozone CPI/PMI','Germany growth/industrial data','EU political/fiscal risk'],
 'GBP':['BoE','UK CPI/wages/jobs','UK GDP/retail sales','UK fiscal/political risk'],
 'JPY':['BoJ','MoF intervention risk','Tokyo/Japan CPI','JGB yields and global risk sentiment'],
 'CHF':['SNB','Swiss CPI','safe-haven flows','European risk sentiment'],
 'CAD':['BoC','Canada CPI/jobs/GDP','WTI crude oil','US-Canada growth differential'],
 'AUD':['RBA','Australia CPI/jobs','China PMIs/growth','iron ore and risk sentiment'],
 'NZD':['RBNZ','New Zealand CPI/jobs','China growth','dairy/commodity risk sentiment'],
}

def exec_intraday(rows,i,side,cfg):
    rr,rf,sw=cfg
    if i+1>=len(rows) or rows[i].get('atr') is None:return None
    sig=rows[i];atr=sig['atr'];ei=i+1;entry=rows[ei]['open'];eday=rows[ei]['dt'].date()
    recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent)
    struct=entry-swing if side==1 else swing-entry;risk=max(rf*atr,struct+.05*atr,.20*atr)
    if risk<=0 or risk>4*atr:return None
    sl=entry-side*risk;tp=entry+side*rr*risk
    lastj=ei
    for j in range(ei,len(rows)):
        if rows[j]['dt'].date()!=eday:break
        lastj=j;x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
        if hs and ht:return ('SL',-1.0,j-ei+1)
        if hs:return ('SL',-1.0,j-ei+1)
        if ht:return ('TP',rr,j-ei+1)
    return ('TIMEOUT',0.0,lastj-ei+1)

def build_base(raw,rows):
    cfg=(1.0,1.0,8);out=[]
    for e in raw:
        o=exec_intraday(rows,e['i'],e['side'],cfg)
        if o:
            q=dict(e);q['label']=1 if o[0]=='TP' else 0;out.append(q)
    return out

def fit(train,spec,seed):
    if len(train)<160:return None
    X=np.asarray([x['x'] for x in train],float);y=np.asarray([x['label'] for x in train],int)
    if len(set(y))<2:return None
    kind,d,l=spec
    if kind=='ET':m=ExtraTreesClassifier(n_estimators=220,max_depth=d,min_samples_leaf=l,max_features=.75,class_weight='balanced_subsample',n_jobs=-1,random_state=seed)
    else:m=HistGradientBoostingClassifier(max_iter=150,max_leaf_nodes=2**d-1,min_samples_leaf=l,learning_rate=.05,l2_regularization=4.0,random_state=seed)
    m.fit(X,y);return m

def score_period(base,train_end,a,z,spec,seed):
    tr=[x for x in base if x['day']<=train_end];te=[x for x in base if a<=x['day']<=z];m=fit(tr,spec,seed)
    if m is None or not te:return []
    p=m.predict_proba(np.asarray([x['x'] for x in te],float))[:,1]
    return [dict(x,prob=float(v)) for x,v in zip(te,p)]

def choose_day(scored,window,direction,thr,margin,maxtrades):
    hours=set(WINDOWS[window]);g=defaultdict(lambda:defaultdict(list))
    for x in scored:
        if x['time'].hour not in hours:continue
        if direction=='BUY' and x['side']!=1:continue
        if direction=='SELL' and x['side']!=-1:continue
        g[x['day']][x['time']].append(x)
    out=[]
    for day,times in sorted(g.items()):
        chosen=[];ordered=sorted(times)
        for ti,t in enumerate(ordered):
            z=sorted(times[t],key=lambda q:q['prob'],reverse=True);best=z[0];other=z[1]['prob'] if len(z)>1 else 0.0;edge=best['prob']-other
            is_last=ti==len(ordered)-1
            if best['prob']>=thr and edge>=margin:
                chosen.append(best)
                if len(chosen)>=maxtrades:break
            elif is_last and not chosen:
                chosen.append(best)
        if not chosen and ordered:
            z=sorted(times[ordered[-1]],key=lambda q:q['prob'],reverse=True);chosen=[z[0]]
        out.extend(chosen)
    return out

def expected_days(scored,window,direction):
    hours=set(WINDOWS[window]);return len(set(x['day'] for x in scored if x['time'].hour in hours and (direction=='BOTH' or (direction=='BUY' and x['side']==1) or (direction=='SELL' and x['side']==-1))))

def eval_sel(sel,rows,cfg,expected):
    z=[]
    for e in sel:
        o=exec_intraday(rows,e['i'],e['side'],cfg)
        if o:z.append(o)
    tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);to=sum(x[0]=='TIMEOUT' for x in z);n=len(z);days=len(set(e['day'] for e in sel));wr=100*tp/n if n else 0
    return {'trades':n,'daysTraded':days,'expectedDays':expected,'coveragePct':round(100*days/expected,2) if expected else 0,'tp':tp,'sl':sl,'timeout':to,'wrAllTrades':round(wr,2),'meanRAllTrades':round((tp*cfg[0]-sl)/n,3) if n else -9,'avgBars':round(statistics.mean(x[2] for x in z),2) if z else 0}

def rank(s):
    hit=s['coveragePct']>=99.9 and s['trades']>=s['expectedDays'] and s['trades']<=3*s['expectedDays'] and s['wrAllTrades']>=TARGET and s['meanRAllTrades']>0
    return (int(hit),s['wrAllTrades'],s['meanRAllTrades'],-s['timeout'],-s['trades'])

def tune_april(sym,base,rows,seed):
    scored_by_spec={}
    for mi,spec in enumerate(MODEL_SPECS):scored_by_spec[spec]=score_period(base,'2026-03-31','2026-04-01','2026-04-30',spec,seed+mi)
    best=None;bp=None
    for spec,scored in scored_by_spec.items():
      if not scored:continue
      for w in WINDOWS:
       for d in DIRS:
        exp=expected_days(scored,w,d)
        if exp<18:continue
        for th in THRESH:
         for ma in MARGINS:
          for mt in MAXTRADES:
            sel=choose_day(scored,w,d,th,ma,mt)
            for cfg in CFGS:
                s=eval_sel(sel,rows,cfg,exp);q=rank(s)
                if best is None or q>best:best=q;bp=(spec,w,d,th,ma,mt,cfg,s)
    return bp

def style(sym,bp):
    spec,w,d,th,ma,mt,cfg,dev=bp;a=sym[:3];q=sym[3:]
    return {'styleId':f'{sym}_V62_{spec[0]}_{w}_{d}_RR{int(cfg[0])}_RF{cfg[1]}_SW{cfg[2]}','model':{'kind':spec[0],'depth':spec[1],'leaf':spec[2]},'window':w,'direction':d,'triggerProbability':th,'sideEdge':ma,'maxTradesPerDay':mt,'execution':{'rr':cfg[0],'riskFloorATR':cfg[1],'swingHours':cfg[2],'sameBarTPandSL':'SL'},'currencies':[a,q],'macroNewsDrivers':{a:CCY_DRIVERS[a],q:CCY_DRIVERS[q]},'liveNewsRule':'Refresh point-in-time news/calendar for both currencies before each session. High-impact surprise is a symbol-specific input/veto; V62 historical score does not fabricate missing historical news.' ,'aprilStyleSelection':dev}

def main():
    doc=json.load(open(b.SNAP,encoding='utf-8'));data={s:b.enrich(doc['data'][s]) for s in b.PAIRS};maps,times=b.make_maps(data);raw=old.raw_candidates(data,maps,times);results={}
    for si,sym in enumerate(b.PAIRS):
        base=build_base(raw[sym],data[sym]);bp=tune_april(sym,base,data[sym],620000+si*100)
        if bp is None:results[sym]={'status':'FAIL','reason':'no style'};print('FAIL',sym,'NO_STYLE',flush=True);continue
        sty=style(sym,bp);monthly=[];allsel=[]
        for mi,(name,a,z) in enumerate(MONTHS):
            train_end={'MAY':'2026-04-30','JUNE':'2026-05-31','JULY':'2026-06-30'}[name];spec=bp[0]
            scored=score_period(base,train_end,a,z,spec,720000+si*100+mi);exp=expected_days(scored,sty['window'],sty['direction']);sel=choose_day(scored,sty['window'],sty['direction'],sty['triggerProbability'],sty['sideEdge'],sty['maxTradesPerDay']);s=eval_sel(sel,data[sym],bp[6],exp);monthly.append({'month':name,**s});allsel.extend(sel)
        expected=sum(x['expectedDays'] for x in monthly);final=eval_sel(allsel,data[sym],bp[6],expected);ok=bool(rank(final)[0]);results[sym]={'status':'PASS' if ok else 'FAIL','style':sty,'walkForwardMayJuly':final,'monthly':monthly};print('PASS' if ok else 'FAIL',sym,final,flush=True)
    passed=[s for s in b.PAIRS if results[s]['status']=='PASS'];failed=[s for s in b.PAIRS if results[s]['status']!='PASS'];ans={'version':'FOREX_INTRADAY_NOCUT_V62','definition':{'cutUsed':False,'noTradeAllowed':False,'minTradesPerEligibleWeekday':1,'maxTradesPerDay':3,'rrAllowed':[1.0,2.0],'timeout':'non-win; fixed intraday session end, never counted as TP','wr':'TP/all trades','styleSelection':'April using model trained through March; style frozen May-Jul; model refit monthly only on past data'},'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'allPassed':not failed,'results':results};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(ans,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:ans[k] for k in ('passCount','failCount','failed','allPassed')},indent=2),flush=True)
if __name__=='__main__':main()
