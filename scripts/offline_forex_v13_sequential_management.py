#!/usr/bin/env python3
import json, os, itertools, statistics
from scripts.offline_crossmarket_rolling_blind_v4 import walk, dateof, num, result_of, rr_of, classify_r, PAIR_SET

FILES=['data/blind_backtest_forex_f8.json','data/blind_backtest_forex_f8_holdout2.json']
CHECKS=(('3h',12),('6h',24),('12h',48),('24h',96))

def extract():
    rows=[];seen=set()
    for fn in FILES:
        if not os.path.exists(fn):continue
        data=json.load(open(fn,encoding='utf-8'))
        for path,d,ctx in walk(data):
            if not isinstance(d,dict):continue
            t=d.get('trade') if isinstance(d.get('trade'),dict) else None;m=d.get('market') if isinstance(d.get('market'),dict) else None
            if not t or not m:continue
            sym=str(t.get('symbol','')).replace('/','').upper();dt=dateof(d.get('cutoff')) or ctx.get('date');side=str(t.get('side','')).upper()
            if sym not in PAIR_SET or not dt or side not in ('BUY','SELL'):continue
            res=result_of(m);rr=rr_of(t,m);rv=classify_r(res,rr)
            if rv is None or rr is None or rr<1:continue
            entry=num(t,'entry');risk=num(t,'risk');
            if entry is None or not risk:continue
            key=(fn,dt,sym,entry,res)
            if key in seen:continue
            seen.add(key);sg=1 if side=='BUY' else -1;direc=d.get('direction') if isinstance(d.get('direction'),dict) else {}
            cps={}
            for name,bars in CHECKS:
                q=direc.get(name) if isinstance(direc.get(name),dict) else {};close=num(q,'close')
                cps[name]=None if close is None else sg*(close-entry)/risk
            h1=num(t,'h1',0) or 0
            rows.append({'file':fn,'date':dt,'symbol':sym,'side':side,'y':1 if rv>0 else 0,'targetRR':min(rr,1.5),'targetR':min(rr,1.5) if rv>0 else -1,
              'entry':entry,'risk':risk,'bars':int(num(m,'bars',0) or 0),'score':abs(num(t,'score',0) or 0),'adx':num(t,'adx',0) or 0,
              'impulse':num(t,'impulseEvidence',0) or 0,'h1Align':1 if h1==sg else 0,'cps':cps})
    return rows

def v7(r):return r['side']=='BUY' and r['score']>=.5 and r['adx']>=20 and r['impulse']>=3 and r['h1Align']==1

def sm(rows):
    if not rows:return {'n':0}
    n=len(rows);w=sum(r['y'] for r in rows)
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':n-w,'wr':round(100*w/n,2),'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def manage(rows,rule):
    # rule = th3,th6,th12; None means disabled. Only act if final TP/SL has not occurred before checkpoint.
    out=[]
    for r in rows:
        z=dict(r);z['managed']='TP' if r['y'] else 'SL';z['managedR']=r['targetR'];z['cutAt']=None
        for (name,bars),th in zip(CHECKS[:3],rule):
            if th is None:continue
            p=r['cps'].get(name)
            if r['bars']>bars and p is not None and p<=th:
                z['managed']='CUT';z['managedR']=p;z['cutAt']=name;break
        out.append(z)
    return out

def msm(rows):
    if not rows:return {'n':0}
    tp=sum(r['managed']=='TP' for r in rows);sl=sum(r['managed']=='SL' for r in rows);cut=sum(r['managed']=='CUT' for r in rows);den=tp+sl
    cuts=[r['managedR'] for r in rows if r['managed']=='CUT']
    return {'n':len(rows),'dates':len(set(r['date'] for r in rows)),'TP':tp,'SL':sl,'CUT':cut,'terminal':den,
      'wrExcludingCut':round(100*tp/den,2) if den else None,'cutRate':round(100*cut/len(rows),2),'avgCutR':round(statistics.mean(cuts),3) if cuts else None,
      'meanManagedRIncludingCut':round(statistics.mean(r['managedR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def choose(dev):
    vals=(None,-.6,-.45,-.3,-.2,-.1,0,.1,.2,.35)
    best=None
    for rule in itertools.product(vals,repeat=3):
        if rule==(None,None,None):continue
        s=msm(manage(dev,rule))
        if s['terminal']<15 or s['cutRate']>55:continue
        score=(1 if s['wrExcludingCut']>=80 else 0,s['wrExcludingCut'],s['meanManagedRIncludingCut'],-s['cutRate'],s['terminal'])
        if best is None or score>best[0]:best=(score,rule,s)
    return best

def main():
    rows=extract();dates=sorted(set(r['date'] for r in rows));devdates=dates[:len(dates)//2];valdates=dates[len(dates)//2:]
    dev=[r for r in rows if r['date'] in devdates and v7(r)];val=[r for r in rows if r['date'] in valdates and v7(r)]
    best=choose(dev);rule=best[1] if best else (None,None,None);mv=manage(val,rule);v=msm(mv)
    out={'version':'FOREX V13 SEQUENTIAL CHECKPOINT MANAGEMENT','providerCreditsUsed':0,
      'method':'Forex-only V7 entries. Sequential post-fill management at genuine stored H+3/H+6/H+12 closes; a checkpoint is evaluated only if the trade is still alive based on final bar count. Thresholds frozen on first 5 dates, applied unchanged to later 5. No MFE/MAE or future outcome used in a CUT decision.',
      'devDates':devdates,'validationDates':valdates,'entryDevelopment':sm(dev),'entryValidation':sm(val),'managementRule':rule,
      'managedDevelopment':best[2] if best else None,'managedValidation':v,
      'validationCutsByCheckpoint':{k:sum(r.get('cutAt')==k for r in mv) for k,_ in CHECKS[:3]},'targetMet':False}
    out['targetMet']=bool(v.get('n',0)>=20 and v.get('terminal',0)>=20 and (v.get('wrExcludingCut') or 0)>=80 and 1<=v.get('avgRR',0)<=1.5 and v.get('meanManagedRIncludingCut',-9)>0)
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_forex_v13_sequential_management.json','w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
