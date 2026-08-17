#!/usr/bin/env python3
import json, math, statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
import scripts.offline_crypto_precision_evolver_v36 as v
from scripts.offline_crypto_v28_separate import PROFILE

OUT='data/offline_crypto_daily_per_symbol_v37.json';TARGET=80.0
WINDOWS={'ALL':(0,4,8,12,16,20),'EARLY':(0,4,8),'MID':(8,12,16),'LATE':(12,16,20)};DIRS=('BOTH','BUY','SELL')
CFGS=[]
for rr in (1.0,2.0):
  for rf in (.55,.75,.95):
    for sw in (3,5):
      hold=6 if rr==1.0 else 9
      for ca,cr,cm in ((0,0,'NONE'),(1,.25,'R'),(1,0.0,'R'),(1,-.20,'EMA'),(2,.10,'R'),(2,-.35,'EMA')):
        CFGS.append((rr,rf,sw,hold,ca,cr,cm))

def regime(mp,t):
    eligible={}
    for s in v.SYMBOLS:
        q=mp[s].get(t)
        if not q:continue
        r=q[1];req=(r.get('ret24'),r.get('ret72'),r.get('adx'),r.get('rsi'),r.get('ema20'),r.get('ema50'),r.get('atr'),r.get('mom24atr'),r.get('dev'))
        if all(x is not None for x in req):eligible[s]=q
    if len(eligible)<20:return None
    rets=[q[1]['ret24'] for q in eligible.values()];breadth=sum(x>0 for x in rets)/len(rets);med=statistics.median(rets);disp=statistics.pstdev(rets) or 1e-9
    btc=eligible.get('BTC');return eligible,{'breadth':breadth,'median24':med,'dispersion24':disp,'btc24':btc[1]['ret24'] if btc else med,'btc72':btc[1]['ret72'] if btc else 0,'eligible':len(eligible)}

def exec_mkt(rows,i,side,cfg):
    rr,rf,sw,hold,ca,cr,cm=cfg
    if i+1>=len(rows) or not rows[i].get('atr'):return None
    sig=rows[i];atr=sig['atr'];ei=i+1;entry=rows[ei]['open'];recent=rows[max(0,i-sw+1):i+1]
    swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);struct=entry-swing if side==1 else swing-entry;risk=max(rf*atr,struct+.05*atr,.25*atr)
    sl=entry-side*risk;tp=entry+side*rr*risk;end=min(len(rows),ei+hold)
    for j in range(ei,end):
        x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
        if hs and ht:return ('SL',-1.0,j-ei+1)
        if hs:return ('SL',-1.0,j-ei+1)
        if ht:return ('TP',rr,j-ei+1)
        age=j-ei+1
        if ca and age>=ca:
            cur=(x['close']-entry)/risk*side
            if cm=='R' and cur<=cr:return ('CUT',max(-1,cur),age)
            if cm=='EMA' and x.get('ema20') is not None and (x['close']-x['ema20'])*side<0 and cur<=cr:return ('CUT',max(-1,cur),age)
    last=rows[max(ei,end-1)]['close'];cur=(last-entry)/risk*side;return ('CUT',max(-1,min(rr,cur)),end-ei)

def build_raw(data,mp):
    out=defaultdict(list);times=sorted(set().union(*(set(x) for x in mp.values())))
    for t in times:
        d=t.date().isoformat()
        if d<'2026-02-10' or d>'2026-07-31':continue
        rp=regime(mp,t)
        if not rp:continue
        eligible,r=rp
        for sym,q in eligible.items():
            i,row=q
            for side in (1,-1):
                x,meta=v.features(sym,row,r,side);out[sym].append({'time':t,'day':d,'i':i,'side':side,'x':x,'meta':meta})
    return out

def baseline(rows,raw):
    cfg=(1.0,.75,5,6,0,0,'NONE');z=[]
    for e in raw:
        o=exec_mkt(rows,e['i'],e['side'],cfg)
        if o:q=dict(e);q['result'],q['r'],q['bars']=o;z.append(q)
    return z

def fit_score(base,train_end,a,b,seed):
    tr=[x for x in base if x['day']<=train_end];te=[x for x in base if a<=x['day']<=b]
    if len(tr)<80 or not te:return []
    X=np.asarray([x['x'] for x in tr],float);y=np.asarray([1 if x['result']=='TP' else 0 for x in tr],int)
    if len(set(y))<2:return []
    m=HistGradientBoostingClassifier(max_iter=120,max_leaf_nodes=15,min_samples_leaf=12,learning_rate=.055,l2_regularization=4.0,random_state=seed);m.fit(X,y)
    p=m.predict_proba(np.asarray([x['x'] for x in te],float))[:,1];return [dict(x,prob=float(q)) for x,q in zip(te,p)]

def choose(rows,window,direction):
    g=defaultdict(list)
    for x in rows:
        if x['time'].hour not in WINDOWS[window]:continue
        if direction=='BUY' and x['side']!=1:continue
        if direction=='SELL' and x['side']!=-1:continue
        g[x['day']].append(x)
    return [max(z,key=lambda q:q['prob']) for d,z in sorted(g.items())]

def apply_cfg(selected,rows,cfg):
    out=[]
    for e in selected:
        o=exec_mkt(rows,e['i'],e['side'],cfg)
        if o:q=dict(e);q['result'],q['r'],q['bars']=o;out.append(q)
    return out

def expected_days(scored):return len(set(x['day'] for x in scored))
def sm(z,expected):
    tp=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);cut=sum(x['result']=='CUT' for x in z);den=tp+sl
    return {'days':len(z),'eligibleDays':expected,'coveragePct':round(100*len(z)/expected,2) if expected else 0,'tp':tp,'sl':sl,'cut':cut,'resolved':den,'wr':round(100*tp/den,2) if den else 0,'meanR':round(statistics.mean(x['r'] for x in z),3) if z else -9,'cutRatePct':round(100*cut/len(z),2) if z else 0}

def rank(s):
    minres=max(5,math.ceil(s['eligibleDays']*.25));hit=s['eligibleDays']>=10 and s['coveragePct']>=99.9 and s['resolved']>=minres and s['wr']>=TARGET and s['meanR']>0
    return (int(hit),s['wr']-max(0,minres-s['resolved'])*8,s['meanR'],-s['cutRatePct'],s['resolved'])

def tune(scored,rows):
    exp=expected_days(scored);best=None;bp=None
    for w in WINDOWS:
      for d in DIRS:
        sel=choose(scored,w,d)
        for cfg in CFGS:
            s=sm(apply_cfg(sel,rows,cfg),exp);r=rank(s)
            if best is None or r>best:best=r;bp={'window':w,'direction':d,'cfg':cfg,'stats':s}
    return bp

def stage(sym,base,rows,devtrain,devrange,finaltrain,finalrange,seed):
    dev=fit_score(base,devtrain,*devrange,seed);p=tune(dev,rows) if dev else None
    final=fit_score(base,finaltrain,*finalrange,seed+9999)
    if not p:return None,sm([],expected_days(final))
    fs=sm(apply_cfg(choose(final,p['window'],p['direction']),rows,p['cfg']),expected_days(final));cfg=p['cfg']
    return {'execution':{'rr':cfg[0],'riskFloorATR':cfg[1],'swingBars4H':cfg[2],'maxHoldBars4H':cfg[3],'cutAfterBars4H':cfg[4],'cutR':cfg[5],'cutMode':cfg[6]},'selector':{'window':p['window'],'direction':p['direction']},'development':p['stats'],'profile':PROFILE.get(sym,'OTHER')},fs

def main():
    doc=json.load(open(v.SNAP,encoding='utf-8'));data={s:v.enrich(doc['data'][s]) for s in v.SYMBOLS};mp=v.maps(data);raw=build_raw(data,mp);results={}
    for si,sym in enumerate(v.SYMBOLS):
        bs=baseline(data[sym],raw.get(sym,[]));p,fs=stage(sym,bs,data[sym],'2026-04-30',('2026-05-01','2026-05-31'),'2026-05-31',('2026-06-01','2026-06-30'),370000+si)
        if p and rank(fs)[0]:results[sym]={'status':'PASS','stage':'JUNE','method':p,'final':fs};print('PASS_JUNE',sym,fs,flush=True);continue
        p2,fs2=stage(sym,bs,data[sym],'2026-05-31',('2026-06-01','2026-06-30'),'2026-06-30',('2026-07-01','2026-07-31'),470000+si);ok=bool(p2 and rank(fs2)[0])
        results[sym]={'status':'PASS' if ok else 'FAIL','stage':'JULY','method':p2,'final':fs2,'previousJune':fs};print('PASS_JULY' if ok else 'FAIL',sym,fs2,flush=True)
    passed=[s for s in v.SYMBOLS if results[s]['status']=='PASS'];failed=[s for s in v.SYMBOLS if results[s]['status']!='PASS'];ans={'version':'CRYPTO_DAILY_PER_SYMBOL_V37','definition':{'oneMarketTradeEveryEligibleCalendarDayPerCoin':True,'crossSymbolRanking':False,'rrAllowed':[1.0,2.0],'wr':'TP/(TP+SL)','cutSeparate':True},'universeCount':61,'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'allPassed':not failed,'results':results};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(ans,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:ans[k] for k in ('passCount','failCount','passed','failed','allPassed')},indent=2),flush=True)
if __name__=='__main__':main()
