#!/usr/bin/env python3
import json, math, random, statistics
from collections import defaultdict
import scripts.free_data_precision_evolver_v1 as m

VERSION='FREE_DATA_CACHED_PRECISION_V3'

# Hidden final holdout is present in fetched raw history but is NEVER transformed into events here.
HIDDEN=m.HIDDEN_START

def build_base(data,market):
    base=[]
    for s,rows in data.items():
        for i,r in enumerate(rows):
            d=m.day(r['ts'])
            if i<100 or d>=HIDDEN:continue
            if r.get('adx') is None or r.get('ema100') is None or r.get('r18') is None:continue
            if market=='FX' and r.get('factorNorm') is None:continue
            if market=='CRYPTO' and r.get('breadth') is None:continue
            side=1 if r['ema20']>r['ema50'] and r['r6']>0 else (-1 if r['ema20']<r['ema50'] and r['r6']<0 else 0)
            if not side:continue
            ar=r['rsi'] if side==1 else 100-r['rsi']
            z={'symbol':s,'rows':rows,'i':i,'ts':r['ts'],'day':d,'hour':m.hour(r['ts']),'side':side,
               'adx':r['adx'],'mom':abs(r['mom6atr']),'dist':r['emaDistAtr'],'long':1 if m.sign(r['r18'])==side else 0,'ar':ar,
               'break6':1 if ((side==1 and r['close']>r['prevHigh6']) or (side==-1 and r['close']<r['prevLow6'])) else 0,
               'break18':1 if ((side==1 and r['close']>r['prevHigh18']) or (side==-1 and r['close']<r['prevLow18'])) else 0}
            if market=='FX':
                z['factor']=side*r['factorNorm']
                z['raw']=r['adx']/30+z['mom']+.7*z['factor']+.25*z['long']-.15*z['dist']
            else:
                ba=r['breadth'] if side==1 else 1-r['breadth'];bt=side*r['btcR6'];rel=side*r['rel6']
                z.update({'breadthA':ba,'btcA':bt,'relA':rel})
                z['raw']=r['adx']/30+z['mom']+1.5*(ba-.5)+40*rel+.25*(bt>0)+.25*z['long']-.15*z['dist']
            base.append(z)
    return base

def make_outcome_cache(base, combos):
    cache={}
    for rr,risk,hold in combos:
        arr=[]
        for z in base:
            o=m.trade_outcome(z['rows'],z['i'],z['side'],rr,risk,hold)
            if not o:continue
            q={k:v for k,v in z.items() if k not in ('rows','i')};q.update(o);q['rr']=rr
            arr.append(q)
        cache[(rr,risk,hold)]=arr
    return cache

def day_top_prefilter(events,n=16):
    by=defaultdict(list)
    for e in events:by[e['day']].append(e)
    out=[]
    for d,z in by.items():out.extend(sorted(z,key=lambda x:x['raw'],reverse=True)[:n])
    return out

def select(events,p,market):
    out=[]
    for e in events:
        if p['session']>=0 and market=='FX' and e['hour']!=p['session']:continue
        if e['adx']<p['adx'] or e['mom']<p['mom'] or e['dist']>p['dist']:continue
        if p['long'] and not e['long']:continue
        if e['ar']<p['rsi_lo'] or e['ar']>p['rsi_hi']:continue
        if p['break']==1 and not e['break6']:continue
        if p['break']==2 and not e['break18']:continue
        if market=='FX':
            if e['factor']<p['factor']:continue
        else:
            if e['breadthA']<p['breadth']:continue
            if e['btcA']<p['btc']:continue
            if e['relA']<p['rel']:continue
        score=e['raw']
        out.append((score,e))
    by=defaultdict(list)
    for score,e in out:by[e['day']].append((score,e))
    sel=[]
    for d,z in by.items():sel.extend([e for _,e in sorted(z,key=lambda x:x[0],reverse=True)[:p['topk']]])
    return sel

def st(rows,a,b):return m.stats(rows,a,b)
def eval3(rows):return {name:st(rows,a,b) for name,a,b in m.FOLDS}

def quality(ev,market):
    mins={'DEV':24 if market=='FX' else 28,'JUNE':6,'JULY':6}
    valid=all(ev[k]['n']>=mins[k] for k in mins)
    hit=valid and all(ev[k]['wr']>=80 and ev[k]['meanR']>0 and ev[k]['resolvedRate']>=70 for k in mins)
    pen=sum(max(0,mins[k]-ev[k]['n'])*4 for k in mins)
    wr=[ev[k]['wr'] for k in mins]
    # prioritize true worst-fold precision before average, then sample and expectancy
    return (1 if hit else 0,min(wr)-pen,statistics.mean(wr),statistics.mean(ev[k]['meanR'] for k in mins),sum(ev[k]['n'] for k in mins))

def randp(rng,market):
    p={'session':rng.choice([-1,-1,0,4,8,12,16,20]),'adx':rng.choice([14,17,20,23,26,29,32,36,40]),
       'mom':rng.choice([.15,.3,.45,.6,.8,1.0,1.25,1.5,1.8,2.2]),'dist':rng.choice([.2,.3,.45,.6,.8,1.0,1.25,1.5]),
       'long':rng.choice([False,True,True]),'rsi_lo':rng.choice([44,47,50,52,54]),'rsi_hi':rng.choice([60,64,68,72,76,80]),
       'break':rng.choice([0,0,0,1,1,2]),'topk':rng.choice([1,1,1,1,2])}
    if market=='FX':p['factor']=rng.choice([-.25,0,.2,.4,.6,.8,1.0,1.25,1.5,2.0])
    else:
        p['breadth']=rng.choice([.50,.54,.58,.62,.66,.70,.74,.78,.82,.86,.90])
        p['btc']=rng.choice([-.01,0,0,.001,.003,.006,.01])
        p['rel']=rng.choice([-.02,-.01,-.005,0,.003,.006,.01,.015,.02,.03])
    return p

def mutate(rng,p,market):
    q=dict(p); fresh=randp(rng,market)
    keys=list(fresh);n=rng.choice([1,1,1,2,2,3])
    for k in rng.sample(keys,n):q[k]=fresh[k]
    return q

def evolve(cache,market,iters=35000):
    rng=random.Random(7531 if market=='FX' else 97531)
    combos=list(cache); population=[];seen=set();best=None
    for t in range(iters):
        combo=rng.choice(combos)
        if population and rng.random()<.72:
            seed=rng.choice(population[:min(12,len(population))]);combo=seed[1];p=mutate(rng,seed[2],market)
        else:p=randp(rng,market)
        key=(combo,json.dumps(p,sort_keys=True))
        if key in seen:continue
        seen.add(key)
        rows=select(cache[combo],p,market);ev=eval3(rows);o=quality(ev,market)
        item=(o,combo,p,ev)
        population.append(item);population.sort(key=lambda x:x[0],reverse=True);population=population[:30]
        if best is None or o>best[0]:
            best=item
            print('BEST',market,t,combo,json.dumps(p,sort_keys=True),json.dumps({k:m.compact(v) for k,v in ev.items()}),flush=True)
        if o[0]:return best,t+1
    return best,iters

def pack(x):
    if not x:return None
    o,combo,p,ev=x
    return {'qualified':bool(o[0]),'objective':o,'combo':{'rr':combo[0],'risk':combo[1],'hold':combo[2]},'params':p,'folds':{k:m.compact(v) for k,v in ev.items()}}

def load_all():
    fx={};cr={};fe={};ce={};src={}
    for s in m.FX:
        try:fx[s]=m.indicators(m.fetch_fx(s));print('FX_FETCH',s,len(fx[s]),flush=True)
        except Exception as e:fe[s]=str(e);print('FX_FAIL',s,str(e)[:90],flush=True)
    m.add_context(fx,'FX')
    for s in m.CRYPTO:
        try:
            r,q=m.fetch_crypto(s);cr[s]=m.indicators(r);src[s]=q;print('CR_FETCH',s,q,len(r),flush=True)
        except Exception as e:ce[s]=str(e);print('CR_FAIL',s,str(e)[:90],flush=True)
    m.add_context(cr,'CRYPTO')
    return fx,cr,fe,ce,src

def main():
    print(json.dumps({'version':VERSION,'providerCreditsUsed':0,'hiddenHoldoutEvaluated':False}),flush=True)
    fx,cr,fe,ce,src=load_all()
    print('COVERAGE',json.dumps({'fxLoaded':len(fx),'fxRequested':len(m.FX),'fxFailed':fe,'cryptoLoaded':len(cr),'cryptoRequested':len(m.CRYPTO),'cryptoFailed':ce,'cryptoSources':src}),flush=True)
    combos=[(rr,risk,hold) for rr in (1.0,1.5) for risk in (.65,.8,1.0,1.2,1.4) for hold in (6,9,12,18)]
    fxb=build_base(fx,'FX');crb=build_base(cr,'CRYPTO')
    fxc={k:day_top_prefilter(v,20) for k,v in make_outcome_cache(fxb,combos).items()}
    crc={k:day_top_prefilter(v,24) for k,v in make_outcome_cache(crb,combos).items()}
    print('BASE_COUNTS',len(fxb),len(crb),flush=True)
    f,nf=evolve(fxc,'FX',35000);c,nc=evolve(crc,'CRYPTO',35000)
    out={'version':VERSION,'providerCreditsUsed':0,'hiddenHoldoutEvaluated':False,'coverage':{'fxLoaded':len(fx),'fxRequested':len(m.FX),'cryptoLoaded':len(cr),'cryptoRequested':len(m.CRYPTO)},'forex':pack(f),'crypto':pack(c),'bothQualifiedForLock':bool(f and c and f[0][0] and c[0][0]),'iterations':{'fx':nf,'crypto':nc},'integrity':'All requested symbols fetched/scanned where public history exists; NO_TRADE permitted; Aug1-14 excluded before outcomes are constructed.'}
    print('FINAL_CACHED',json.dumps(out,indent=2),flush=True)
if __name__=='__main__':main()
