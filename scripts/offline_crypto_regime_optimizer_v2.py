#!/usr/bin/env python3
import json, os, re, statistics, itertools
from collections import defaultdict
FILES=['data/blind_backtest_v24_validation.json','data/blind_backtest_v26.json','data/blind_backtest_v27_final.json','data/final_market_vs_limit_blind.json']
DR=re.compile(r'20\d\d-\d\d-\d\d')
def num(d,k,default=None):
    v=d.get(k,default) if isinstance(d,dict) else default
    return v if isinstance(v,(int,float)) and not isinstance(v,bool) else default
def dateof(x):
    if not isinstance(x,str):return None
    m=DR.search(x);return m.group(0) if m else None
def walk(x,ctx=None):
    ctx=dict(ctx or {})
    if isinstance(x,dict):
        for k in ('cutoff','signalTime','entryTime','date'):
            d=dateof(x.get(k))
            if d:ctx['date']=d;break
        for k in ('priceBreadth','flowBreadth','flowCoverage','flowMedian'):
            v=num(x,k)
            if v is not None:ctx[k]=v
        for k in ('marketRegime','modelRegime'):
            if isinstance(x.get(k),str):ctx[k]=x[k].lower()
        sym=x.get('symbol') or x.get('pair')
        if isinstance(sym,str):ctx['symbol']=sym.replace('/','').upper()
        side=x.get('side') or x.get('decision')
        if isinstance(side,str):ctx['side']=side.upper()
        yield x,ctx
        for k,v in x.items():
            c=dict(ctx);kd=dateof(str(k))
            if kd:c['date']=kd
            yield from walk(v,c)
    elif isinstance(x,list):
        for v in x:yield from walk(v,ctx)
def res(m):
    if not isinstance(m,dict):return None
    o=m.get('outcome')
    if isinstance(o,dict):return (o.get('result') or o.get('status') or '').upper()
    if isinstance(o,str):return o.upper()
    r=m.get('result');return r.upper() if isinstance(r,str) else None
def rr(m):
    if not isinstance(m,dict):return None
    for k in ('rr','plannedRR','effectiveRR','avgPlannedRR','avgRR'):
        v=num(m,k)
        if v is not None:return float(v)
def rval(m):
    r=res(m)
    if r in ('TP','WIN','TARGET'):return rr(m) or 1.0
    if r in ('SL','LOSS','STOP'):return -1.0
    return None
def rows():
    out=[];seen=set()
    for fn in FILES:
        if not os.path.exists(fn):continue
        data=json.load(open(fn,encoding='utf-8'))
        for d,c in walk(data):
            sym=c.get('symbol');dt=c.get('date')
            if not sym or not sym.endswith('USDT') or not dt:continue
            m=d.get('market') if isinstance(d.get('market'),dict) else None
            if m is None and res(d) and any(k in d for k in ('entry','sl','tp','plannedRR','rr')):m=d
            rv=rval(m)
            if rv is None:continue
            model=d.get('model') if isinstance(d.get('model'),dict) else {}
            side=c.get('side') or d.get('side') or d.get('decision') or ''
            rec={'file':fn,'date':dt,'symbol':sym,'side':str(side).upper(),'r':rv,'rr':rr(m) or num(d,'plannedRR',1.0) or 1.0,
                 'breadth':c.get('priceBreadth'),'flowBreadth':c.get('flowBreadth'),'flowCoverage':c.get('flowCoverage'),
                 'score':num(d,'score',num(d,'macroScore',0.0)) or 0.0,'macro':num(d,'macroScore',0.0) or 0.0,
                 'micro':num(d,'microScore',0.0) or 0.0,'htf':num(model,'htfScore',0.0) or 0.0,
                 'ltf':num(model,'ltfScore',0.0) or 0.0,'rangePos':num(model,'rangePositionH1'),
                 'regime':str(model.get('regime') or c.get('marketRegime') or 'unknown').lower()}
            key=(fn,dt,sym,rec['side'],num(m,'entry',num(d,'entry')),rv)
            if key in seen:continue
            seen.add(key);out.append(rec)
    return out
def summary(rs):
    if not rs:return {'n':0}
    w=sum(r['r']>0 for r in rs);l=sum(r['r']<0 for r in rs);n=w+l
    return {'n':len(rs),'dates':len(set(r['date'] for r in rs)),'resolved':n,'wins':w,'losses':l,
            'wr':round(100*w/n,2) if n else None,'meanR':round(statistics.mean(r['r'] for r in rs),3),
            'avgRR':round(statistics.mean(r['rr'] for r in rs),3)}
# Rule uses only state available before outcomes.
def candidates():
    bms=['ANY','BULL55','BULL65','BULL75','BULL85','BULL93','BEAR45','BEAR35','BEAR25','BEAR15','BEAR07','MID','EXTREME','SIDE_ALIGN']
    sms=['ANY','BUY','SELL','BREADTH_ALIGN']
    for x in itertools.product(bms,sms,(0,1,2,3,4,5),(0,2,4,6,8),(0,4,8,12),('ANY','trend','transition','range'),('ANY','AGREE'),('ANY','EDGE')):yield x
def passed(r,p):
    bm,sm,sc,ma,ht,rg,mi,loc=p;b=r['breadth'];s=r['side']
    if bm!='ANY':
        if b is None:return False
        if bm=='BULL55' and b<.55:return False
        if bm=='BULL65' and b<.65:return False
        if bm=='BULL75' and b<.75:return False
        if bm=='BULL85' and b<.85:return False
        if bm=='BULL93' and b<.93:return False
        if bm=='BEAR45' and b>.45:return False
        if bm=='BEAR35' and b>.35:return False
        if bm=='BEAR25' and b>.25:return False
        if bm=='BEAR15' and b>.15:return False
        if bm=='BEAR07' and b>.07:return False
        if bm=='MID' and not (.35<=b<=.65):return False
        if bm=='EXTREME' and not (b>=.8 or b<=.2):return False
        if bm=='SIDE_ALIGN' and ((b>=.5 and s!='BUY') or (b<.5 and s!='SELL')):return False
    if sm=='BUY' and s!='BUY':return False
    if sm=='SELL' and s!='SELL':return False
    if sm=='BREADTH_ALIGN':
        if b is None or ((b>=.5 and s!='BUY') or (b<.5 and s!='SELL')):return False
    if abs(r['score'])<sc or abs(r['macro'])<ma or abs(r['htf'])<ht:return False
    if rg!='ANY' and r['regime']!=rg:return False
    if mi=='AGREE' and r['micro']!=0:
        if (s=='BUY' and r['micro']<=0) or (s=='SELL' and r['micro']>=0):return False
    if loc=='EDGE':
        q=r['rangePos']
        if q is None:return False
        # continuation requires non-mid location; direction-specific anti-chase.
        if s=='BUY' and q>.85:return False
        if s=='SELL' and q<.15:return False
    return True
def choose(train,minn):
    best=None
    for p in candidates():
        ss=[r for r in train if passed(r,p)];sm=summary(ss)
        if sm.get('resolved',0)<minn or sm.get('dates',0)<3 or (sm.get('avgRR') or 0)<1.0:continue
        wr=sm['wr'];mr=sm['meanR'];cnt=sm['resolved']
        # high precision target, then economic value and breadth of evidence
        key=(1 if wr>=80 else 0,wr,mr,min(cnt,120))
        if best is None or key>best[0]:best=(key,p,sm)
    return best
def main():
    rs=rows();dates=sorted(set(r['date'] for r in rs));wf=[];by={}
    for i,dt in enumerate(dates):
        day=[r for r in rs if r['date']==dt]
        if i<4:
            by[dt]={'warmup':True,'all':summary(day),'selected':{'n':0}};continue
        train=[r for r in rs if r['date']<dt]
        best=choose(train,max(20,int(len(train)*.04)))
        ss=[r for r in day if best and passed(r,best[1])];wf+=ss
        by[dt]={'warmup':False,'all':summary(day),'rule':best[1] if best else None,'train':best[2] if best else None,'selected':summary(ss)}
    ins=choose(rs,max(40,int(len(rs)*.07)))
    out={'version':'CRYPTO REGIME OPTIMIZER V2','providerCreditsUsed':0,'rows':len(rs),'dates':dates,'all':summary(rs),
         'walkForward':summary(wf),'inSampleCeiling':{'rule':ins[1] if ins else None,'performance':ins[2] if ins else None,'promotable':False},
         'byDate':by,'targetMet':False}
    out['targetMet']=bool((out['walkForward'].get('wr') or 0)>=80 and (out['walkForward'].get('avgRR') or 0)>=1.0 and out['walkForward'].get('resolved',0)>=20)
    os.makedirs('data',exist_ok=True)
    json.dump(out,open('data/offline_crypto_regime_optimizer_v2.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps({'all':out['all'],'walkForward':out['walkForward'],'inSampleCeiling':out['inSampleCeiling'],'targetMet':out['targetMet'],'byDate':out['byDate']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
