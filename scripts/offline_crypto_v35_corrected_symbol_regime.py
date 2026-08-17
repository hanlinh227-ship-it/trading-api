#!/usr/bin/env python3
import json, os, re, statistics, math
from collections import defaultdict
from scripts.offline_crypto_v28_separate import PROFILE, FAMILY_WEIGHTS, base_symbol

FILES=['data/blind_backtest_v24_validation.json','data/blind_backtest_v26.json','data/blind_backtest_v27_final.json','data/final_market_vs_limit_blind.json']
DR=re.compile(r'20\d\d-\d\d-\d\d')

def num(d,k,z=None):
    v=d.get(k,z) if isinstance(d,dict) else z
    return float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) else z

def dt(x):
    m=DR.search(x) if isinstance(x,str) else None;return m.group(0) if m else None

def walk(x,c=None):
    c=dict(c or {})
    if isinstance(x,dict):
        for k in ('cutoff','signalTime','entryTime','date'):
            q=dt(x.get(k))
            if q:c['date']=q;break
        for k in ('priceBreadth','flowBreadth','flowCoverage'):
            q=num(x,k)
            if q is not None:c[k]=q
        if isinstance(x.get('marketRegime'),str):c['marketRegime']=x['marketRegime'].lower()
        s=x.get('symbol') or x.get('pair');side=x.get('side') or x.get('decision')
        if isinstance(s,str):c['symbol']=s.replace('/','').upper()
        if isinstance(side,str):c['side']=side.upper()
        yield x,c
        for k,v in x.items():
            cc=dict(c);q=dt(str(k))
            if q:cc['date']=q
            yield from walk(v,cc)
    elif isinstance(x,list):
        for v in x:yield from walk(v,c)

def ores(m):
    if not isinstance(m,dict):return ''
    o=m.get('outcome')
    if isinstance(o,dict):return str(o.get('result') or '').upper()
    if isinstance(o,str):return o.upper()
    return str(m.get('result') or '').upper()

def rrv(m,d):
    for src in (m,d):
        if not isinstance(src,dict):continue
        for k in ('rr','plannedRR','effectiveRR','avgPlannedRR'):
            q=num(src,k)
            if q is not None:return q

def load():
    rows=[];seen=set()
    for fn in FILES:
        if not os.path.exists(fn):continue
        data=json.load(open(fn,encoding='utf-8'))
        for d,c in walk(data):
            s=c.get('symbol');day=c.get('date')
            if not s or not s.endswith('USDT') or not day:continue
            m=d.get('market') if isinstance(d.get('market'),dict) else None
            if m is None and ores(d) and any(k in d for k in ('entry','sl','tp')):m=d
            if not isinstance(m,dict):continue
            res=ores(m);rr=rrv(m,d)
            if res not in ('TP','SL') or rr is None or rr<1:continue
            side=str(c.get('side') or d.get('side') or d.get('decision') or '').upper()
            if side not in ('BUY','SELL'):continue
            mod=d.get('model') if isinstance(d.get('model'),dict) else {};coin=base_symbol(s);fam=PROFILE.get(coin,'L1')
            entry=num(m,'entry',num(d,'entry'));key=(fn,day,s,side,entry,res)
            if key in seen:continue
            seen.add(key);b=c.get('priceBreadth');sg=1 if side=='BUY' else -1
            micro=num(d,'microScore',0) or 0;macro=num(d,'macroScore',0) or 0;htf=num(mod,'htfScore',0) or 0;chase=abs(num(mod,'chaseAdjustment',0) or 0)
            rows.append({'file':fn,'date':day,'symbol':s,'coin':coin,'family':fam,'side':side,'b':b,'reg':str(mod.get('regime') or c.get('marketRegime') or 'unknown').lower(),
              'score':abs(num(d,'score',macro) or 0),'macro':abs(macro),'htf':abs(htf),'micro':micro,'chase':chase,
              'breadthAlign':0 if b is None else sg*(b-.5)*2,'microAlign':0 if micro==0 else (1 if sg*micro>0 else -1),
              'targetRR':min(rr,1.5),'y':1 if res=='TP' else 0,'targetR':min(rr,1.5) if res=='TP' else -1})
    return rows

def sm(a):
    if not a:return {'n':0}
    n=len(a);w=sum(x['y'] for x in a)
    return {'n':n,'dates':len(set(x['date'] for x in a)),'wins':w,'losses':n-w,'wr':round(100*w/n,2),'meanR':round(statistics.mean(x['targetR'] for x in a),3),'avgRR':round(statistics.mean(x['targetRR'] for x in a),3)}

def priors(train):
    gp=(sum(x['y'] for x in train)+6)/(len(train)+12)
    def mk(key,a):
        by=defaultdict(list)
        for x in train:by[key(x)].append(x['y'])
        return {k:(sum(v)+a*gp)/(len(v)+a) for k,v in by.items()}
    return gp,mk(lambda x:x['coin'],8),mk(lambda x:x['family'],12),mk(lambda x:(x['family'],x['side']),12)

def score(x,pr,variant):
    gp,sp,fp,fsp=pr;wb,wm,wh,wc=FAMILY_WEIGHTS.get(x['family'],(1,1,1,.8))
    prior=.55*sp.get(x['coin'],gp)+.45*fsp.get((x['family'],x['side']),fp.get(x['family'],gp))
    if variant in ('DRIVER','DRIVER_MICRO'):
        return 1.3*prior + .9*wb*x['breadthAlign'] + .55*wm*(x['macro']/6) + .75*wh*(x['htf']/10) + (.45 if variant=='DRIVER_MICRO' else .2)*x['microAlign'] - .8*wc*x['chase']
    if variant=='HTF':return 1.1*prior+.7*x['breadthAlign']+.9*(x['htf']/10)+.35*(x['macro']/6)-.6*x['chase']
    return prior+.8*x['breadthAlign']+.5*(x['score']/6)-.7*x['chase']

def daystats(rows):
    by=defaultdict(list)
    for x in rows:by[x['date']].append(x)
    out={}
    for d,a in by.items():
        bs=[x['b'] for x in a if x['b'] is not None];b=statistics.median(bs) if bs else .5
        out[d]={'b':b,'alignShare':sum(x['breadthAlign']>0 for x in a)/len(a),'medHTF':statistics.median(x['htf'] for x in a),'medMacro':statistics.median(x['macro'] for x in a),'medChase':statistics.median(x['chase'] for x in a)}
    return out

def day_ok(st,mode,minAlign,minHTF,maxChase):
    b=st['b']
    if mode=='BULL' and b<.6:return False
    if mode=='BULL_STRONG' and b<.8:return False
    if mode=='BEAR' and b>.4:return False
    if mode=='ALIGN_EXTREME' and not (b>=.8 or b<=.2):return False
    if mode=='NO_BEAR_CAP' and b<.15:return False
    return st['alignShare']>=minAlign and st['medHTF']>=minHTF and st['medChase']<=maxChase

def select(dayrows,train,states,param):
    mode,minAlign,minHTF,maxDayChase,sideMode,variant,floor,topk,requireMicro=param;d=dayrows[0]['date'] if dayrows else None
    if not d or not day_ok(states[d],mode,minAlign,minHTF,maxDayChase):return []
    pr=priors(train);z=[]
    for x in dayrows:
        if sideMode=='ALIGN' and x['breadthAlign']<=0:continue
        if sideMode=='BUY' and x['side']!='BUY':continue
        if sideMode=='SELL' and x['side']!='SELL':continue
        if requireMicro and x['micro']!=0 and x['microAlign']<=0:continue
        sc=score(x,pr,variant)
        if sc>=floor:z.append((sc,x))
    return [x for _,x in sorted(z,key=lambda q:q[0],reverse=True)[:topk]]

PARAMS=[]
for mode in ('ANY','NO_BEAR_CAP','BULL','BULL_STRONG','BEAR','ALIGN_EXTREME'):
 for al in (0,.5,.65):
  for ht in (0,5,8):
   for dc in (.75,1.5,99):
    for side in ('ANY','ALIGN','BUY','SELL'):
     for var in ('DRIVER','DRIVER_MICRO','HTF','SCORE'):
      for fl in (.4,.7,1.0):
       for k in (3,5):
        for mic in (False,True):PARAMS.append((mode,al,ht,dc,side,var,fl,k,mic))

def choose(train,states):
    dates=sorted(set(x['date'] for x in train));best=None
    for p in PARAMS:
        z=[]
        for d in dates:
            past=[x for x in train if x['date']<d]
            if len(set(x['date'] for x in past))<2:continue
            day=[x for x in train if x['date']==d];z+=select(day,past,states,p)
        s=sm(z)
        if s['n']<15 or s['dates']<3:continue
        sc=(1 if s['wr']>=80 else 0,s['wr'],s['meanR'],min(s['n'],30))
        if best is None or sc>best[0]:best=(sc,p,s)
    return best

def main():
    rows=load();states=daystats(rows);dates=sorted(set(x['date'] for x in rows));wf=[];by={}
    for i,d in enumerate(dates):
        if i<5:by[d]={'warmup':True,'all':sm([x for x in rows if x['date']==d]),'state':states[d]};continue
        train=[x for x in rows if x['date']<d];best=choose(train,states);day=[x for x in rows if x['date']==d];sel=select(day,train,states,best[1]) if best else [];wf+=sel
        by[d]={'warmup':False,'rule':best[1] if best else None,'inner':best[2] if best else None,'all':sm(day),'state':states[d],'selected':sm(sel),'symbols':[x['coin'] for x in sel]}
    res=sm(wf);out={'version':'CRYPTO V35 CORRECTED SYMBOL REGIME','providerCreditsUsed':0,'method':'Crypto-only corrected context inheritance. Expanding walk-forward chooses among a small family of regime/side/profile-driver rules using earlier dates only; current day then ranks symbol/family-specific drivers. No Forex features.',
      'all':sm(rows),'walkForward':res,'byDate':by,'targetMet':bool(res.get('n',0)>=20 and res.get('wr',0)>=80 and 1<=res.get('avgRR',0)<=1.5 and res.get('meanR',-9)>0),'hourlyManagement':'NOT_REPLAYABLE_FROM_OLD_CRYPTO_ROWS'}
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crypto_v35_corrected_symbol_regime.json','w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
