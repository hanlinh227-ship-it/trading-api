#!/usr/bin/env python3
import json, os, math, statistics, itertools
from scripts.offline_crypto_v28_separate import PROFILE, base_symbol

FN='data/blind_backtest_v24.json'

def sm(rows):
    if not rows:return {'n':0}
    n=len(rows);w=sum(r['y'] for r in rows)
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':n-w,'wr':round(100*w/n,2),'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def wilson(w,n,z=1.2816):
    if not n:return 0
    p=w/n;den=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/den

def extract():
    data=json.load(open(FN,encoding='utf-8'));out=[]
    for label,s in data.get('samples',{}).items():
        date=str(s.get('cutoff',''))[:10];pb=float(s.get('priceBreadth',.5) or .5);fb=float(s.get('flowBreadth',.5) or .5)
        for t in s.get('tests',[]):
            o=t.get('outcome') or {};res=str(o.get('result','')).upper();rr=t.get('plannedRR')
            if res not in ('TP','SL') or not isinstance(rr,(int,float)) or rr<1:continue
            side=str(t.get('decision','')).upper();sg=1 if side=='BUY' else -1;flow=t.get('flow') or {};model=t.get('model') or {};ofi=float(flow.get('ofi',0) or 0)
            out.append({'date':date,'label':label,'coin':base_symbol(str(t.get('symbol',''))),'family':PROFILE.get(base_symbol(str(t.get('symbol',''))),'L1'),'side':side,
              'flowAvailable':bool(flow.get('available')),'ofiAlign':sg*ofi,'microAlign':sg*float(t.get('microScore',0) or 0),'scoreAlign':sg*float(t.get('score',0) or 0),
              'macroAlign':sg*float(t.get('macroScore',0) or 0),'htfAlign':sg*float(model.get('htfScore',0) or 0),'ltfAlign':sg*float(model.get('ltfScore',0) or 0),
              'rsAlign':sg*float(model.get('relativeStrengthScore',0) or 0),'btcAlign':sg*float(model.get('btcBias',0) or 0),'chase':abs(float(model.get('chaseAdjustment',0) or 0)),
              'regime':str(model.get('regime','unknown')).lower(),'breadthAlign':sg*(pb-.5)*2,'flowBreadthAlign':sg*(fb-.5)*2,'microMoveAlign':sg*float(t.get('microMoveATR',0) or 0),
              'targetRR':min(float(rr),1.5),'y':1 if res=='TP' else 0,'targetR':min(float(rr),1.5) if res=='TP' else -1})
    return out

def candidates():
    return itertools.product((False,True),(0,.05,.15,.3,.5),(0,1.5,3,5),( -99,0,2,4),( -99,-1,0,1),( -99,-.5,0,.5),(99,1,2.5,4),('ANY','trend','transition','range'),('ANY','ALIGN_BREADTH','ALIGN_FLOW_BREADTH'),(-99,-.25,0,.25))

def passed(r,p):
    reqflow,ofi,score,htf,ltf,rs,maxchase,reg,sideMode,micro=p
    if reqflow and not r['flowAvailable']:return False
    if r['ofiAlign']<ofi or r['scoreAlign']<score or r['htfAlign']<htf or r['ltfAlign']<ltf or r['rsAlign']<rs or r['chase']>maxchase or r['microAlign']<micro:return False
    if reg!='ANY' and r['regime']!=reg:return False
    if sideMode=='ALIGN_BREADTH' and r['breadthAlign']<=0:return False
    if sideMode=='ALIGN_FLOW_BREADTH' and r['flowBreadthAlign']<=0:return False
    return True

def choose(dev):
    best=None
    for p in candidates():
        z=[r for r in dev if passed(r,p)];s=sm(z)
        if s['n']<18:continue
        lb=100*wilson(s['wins'],s['n']);score=(1 if s['wr']>=80 else 0,lb,s['wr'],s['meanR'],min(s['n'],45))
        if best is None or score>best[0]:best=(score,p,s)
    return best

def main():
    rows=extract();dates=sorted(set(r['date'] for r in rows));devdate=dates[0];valdate=dates[-1];dev=[r for r in rows if r['date']==devdate];val=[r for r in rows if r['date']==valdate]
    best=choose(dev);sel=[r for r in val if best and passed(r,best[1])];v=sm(sel)
    out={'version':'CRYPTO V34 FRESH FLOW MODE','providerCreditsUsed':0,'method':'Crypto-only V24 fresh-flow branch. Rule selected on earlier Jul02 sample and frozen for later Jul04 sample using only pre-entry flow/HTF/LTF/RS/BTC/chase/breadth fields. This branch is only for FLOW_AVAILABLE conditions.',
      'developmentDate':devdate,'validationDate':valdate,'allDevelopment':sm(dev),'allValidation':sm(val),'rule':best[1] if best else None,'development':best[2] if best else None,'validation':v,
      'targetThresholdHitOnOneDay':bool(v.get('n',0)>=20 and v.get('wr',0)>=80 and 1<=v.get('avgRR',0)<=1.5 and v.get('meanR',-9)>0),'targetMet':False,
      'promotionNote':'Even if one validation day exceeds 80%, global promotion remains false because only one later independent date is available for this exact fresh-flow mode.'}
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crypto_v34_flow_mode.json','w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
