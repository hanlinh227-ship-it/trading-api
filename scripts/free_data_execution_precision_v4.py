#!/usr/bin/env python3
import json, math, random, statistics
from collections import defaultdict
import scripts.free_data_precision_evolver_v1 as m

VERSION='FREE_DATA_EXECUTION_PRECISION_V4'
HIDDEN=m.HIDDEN_START

def limit_outcome(rows,i,side,rr,risk_floor,maxhold,offset,expiry):
    if i+1>=len(rows):return None
    sig=rows[i];atr=sig.get('atr')
    if not atr:return None
    limit=sig['close']-side*offset*atr
    fill_i=None
    for j in range(i+1,min(len(rows),i+1+expiry)):
        b=rows[j]
        if b['low']<=limit<=b['high']:
            fill_i=j;break
    if fill_i is None:return None
    if side==1:
        swing=min(x['low'] for x in rows[max(0,i-5):i+1]);struct=max(limit-swing,0)
    else:
        swing=max(x['high'] for x in rows[max(0,i-5):i+1]);struct=max(swing-limit,0)
    risk=max(atr*risk_floor,struct)
    if risk<=0 or risk>atr*3:return None
    sl=limit-side*risk;tp=limit+side*rr*risk
    end=min(len(rows),fill_i+maxhold)
    for j in range(fill_i,end):
        b=rows[j]
        # conservative: if both possible in same 4H candle, SL wins
        if side==1:
            if b['low']<=sl:return {'result':'SL','r':-1.0,'bars':j-fill_i+1,'entry':limit,'sl':sl,'tp':tp,'fillDelay':fill_i-i}
            if b['high']>=tp:return {'result':'TP','r':rr,'bars':j-fill_i+1,'entry':limit,'sl':sl,'tp':tp,'fillDelay':fill_i-i}
        else:
            if b['high']>=sl:return {'result':'SL','r':-1.0,'bars':j-fill_i+1,'entry':limit,'sl':sl,'tp':tp,'fillDelay':fill_i-i}
            if b['low']<=tp:return {'result':'TP','r':rr,'bars':j-fill_i+1,'entry':limit,'sl':sl,'tp':tp,'fillDelay':fill_i-i}
    last=rows[end-1]['close'];r=(last-limit)/risk*side
    return {'result':'CUT','r':max(-1,min(rr,r)),'bars':maxhold,'entry':limit,'sl':sl,'tp':tp,'fillDelay':fill_i-i}

def base(data,market):
    out=[]
    for s,rows in data.items():
        for i,r in enumerate(rows):
            if i<100 or m.day(r['ts'])>=HIDDEN:continue
            if r.get('adx') is None or r.get('ema100') is None or r.get('r18') is None:continue
            if market=='FX' and r.get('factorNorm') is None:continue
            if market=='CRYPTO' and r.get('breadth') is None:continue
            side=1 if r['ema20']>r['ema50'] and r['r6']>0 else (-1 if r['ema20']<r['ema50'] and r['r6']<0 else 0)
            if not side:continue
            ar=r['rsi'] if side==1 else 100-r['rsi']
            z={'symbol':s,'rows':rows,'i':i,'ts':r['ts'],'day':m.day(r['ts']),'hour':m.hour(r['ts']),'side':side,'adx':r['adx'],'mom':abs(r['mom6atr']),'dist':r['emaDistAtr'],'long':int(m.sign(r['r18'])==side),'ar':ar,
               'b6':int((side==1 and r['close']>r['prevHigh6']) or (side==-1 and r['close']<r['prevLow6'])),
               'b18':int((side==1 and r['close']>r['prevHigh18']) or (side==-1 and r['close']<r['prevLow18']))}
            if market=='FX':
                z['factor']=side*r['factorNorm'];z['raw']=r['adx']/30+z['mom']+.75*z['factor']+.25*z['long']-.18*z['dist']
            else:
                ba=r['breadth'] if side==1 else 1-r['breadth'];z.update({'breadthA':ba,'btcA':side*r['btcR6'],'relA':side*r['rel6']});z['raw']=r['adx']/30+z['mom']+1.6*(ba-.5)+42*z['relA']+.25*(z['btcA']>0)+.2*z['long']-.18*z['dist']
            out.append(z)
    return out

def exec_cache(base,market):
    cache={}
    configs=[]
    for mode in ('MARKET','LIMIT'):
      offs=(0,) if mode=='MARKET' else (.20,.35,.50,.70,.90)
      exps=(1,) if mode=='MARKET' else (1,2,3)
      for rr in (1.0,1.5):
       for risk in (.65,.8,1.0,1.2,1.4):
        for hold in (6,9,12,18):
         for off in offs:
          for exp in exps:configs.append((mode,rr,risk,hold,off,exp))
    for cfg in configs:
        mode,rr,risk,hold,off,exp=cfg;arr=[]
        for z in base:
            o=m.trade_outcome(z['rows'],z['i'],z['side'],rr,risk,hold) if mode=='MARKET' else limit_outcome(z['rows'],z['i'],z['side'],rr,risk,hold,off,exp)
            if not o:continue
            q={k:v for k,v in z.items() if k not in ('rows','i')};q.update(o);q['rr']=rr;q['mode']=mode
            arr.append(q)
        cache[cfg]=arr
    return cache

def select(events,p,market):
    q=[]
    for e in events:
        if market=='FX' and p['session']>=0 and e['hour']!=p['session']:continue
        if e['adx']<p['adx'] or e['mom']<p['mom'] or e['dist']>p['dist'] or e['ar']<p['rsi_lo'] or e['ar']>p['rsi_hi']:continue
        if p['long'] and not e['long']:continue
        if p['break']==1 and not e['b6']:continue
        if p['break']==2 and not e['b18']:continue
        if market=='FX':
            if e['factor']<p['factor']:continue
            sc=e['raw']
        else:
            if e['breadthA']<p['breadth'] or e['btcA']<p['btc'] or e['relA']<p['rel']:continue
            sc=e['raw']
        q.append((sc,e))
    by=defaultdict(list)
    for sc,e in q:by[e['day']].append((sc,e))
    out=[]
    for d,z in by.items():out.extend([e for _,e in sorted(z,key=lambda x:x[0],reverse=True)[:p['topk']]])
    return out

def ev(rows):return {n:m.stats(rows,a,b) for n,a,b in m.FOLDS}
def objective(e,market):
    mins={'DEV':22 if market=='FX' else 26,'JUNE':6,'JULY':6}
    hit=all(e[k]['n']>=mins[k] and e[k]['wr']>=80 and e[k]['meanR']>0 and e[k]['resolvedRate']>=70 for k in mins)
    pen=sum(max(0,mins[k]-e[k]['n'])*4 for k in mins);w=[e[k]['wr'] for k in mins]
    return (int(hit),min(w)-pen,statistics.mean(w),statistics.mean(e[k]['meanR'] for k in mins),sum(e[k]['n'] for k in mins))

def rp(rng,market):
    p={'session':rng.choice([-1,-1,0,4,8,12,16,20]),'adx':rng.choice([14,17,20,23,26,29,32,36,40]),'mom':rng.choice([.15,.3,.45,.6,.8,1,1.25,1.5,1.8,2.2]),'dist':rng.choice([.2,.3,.45,.6,.8,1,1.25,1.5]),'long':rng.choice([False,True,True]),'rsi_lo':rng.choice([44,47,50,52,54]),'rsi_hi':rng.choice([60,64,68,72,76,80]),'break':rng.choice([0,0,0,1,1,2]),'topk':rng.choice([1,1,1,2])}
    if market=='FX':p['factor']=rng.choice([-.25,0,.2,.4,.6,.8,1,1.25,1.5,2])
    else:
        p['breadth']=rng.choice([.5,.54,.58,.62,.66,.7,.74,.78,.82,.86,.9]);p['btc']=rng.choice([-.01,0,0,.001,.003,.006,.01]);p['rel']=rng.choice([-.02,-.01,-.005,0,.003,.006,.01,.015,.02,.03])
    return p

def mutate(rng,p,market):
    q=dict(p);x=rp(rng,market);ks=list(x)
    for k in rng.sample(ks,rng.choice([1,1,2,2,3])):q[k]=x[k]
    return q

def evolve(cache,market,iters=50000):
    rng=random.Random(4404 if market=='FX' else 4405);configs=list(cache);pop=[];best=None;seen=set()
    for t in range(iters):
        if pop and rng.random()<.78:
            seed=rng.choice(pop[:min(15,len(pop))]);cfg=seed[1];p=mutate(rng,seed[2],market)
            if rng.random()<.12:cfg=rng.choice(configs)
        else:cfg=rng.choice(configs);p=rp(rng,market)
        key=(cfg,json.dumps(p,sort_keys=True))
        if key in seen:continue
        seen.add(key);rows=select(cache[cfg],p,market);e=ev(rows);o=objective(e,market);it=(o,cfg,p,e)
        pop.append(it);pop.sort(key=lambda x:x[0],reverse=True);pop=pop[:35]
        if best is None or o>best[0]:
            best=it;print('BEST',market,t,cfg,json.dumps(p,sort_keys=True),json.dumps({k:m.compact(v) for k,v in e.items()}),flush=True)
        if o[0]:return best,t+1
    return best,iters

def pack(x):
    if not x:return None
    o,c,p,e=x;return {'qualified':bool(o[0]),'objective':o,'execution':{'mode':c[0],'rr':c[1],'risk':c[2],'hold':c[3],'offset':c[4],'expiry':c[5]},'params':p,'folds':{k:m.compact(v) for k,v in e.items()}}

def main():
    print(json.dumps({'version':VERSION,'providerCreditsUsed':0,'hiddenHoldoutEvaluated':False}),flush=True)
    fx={};cr={};fe={};ce={};src={}
    for s in m.FX:
        try:fx[s]=m.indicators(m.fetch_fx(s));print('FX',s,len(fx[s]),flush=True)
        except Exception as e:fe[s]=str(e);print('FX_FAIL',s,str(e)[:90],flush=True)
    m.add_context(fx,'FX')
    for s in m.CRYPTO:
        try:r,q=m.fetch_crypto(s);cr[s]=m.indicators(r);src[s]=q;print('CR',s,q,len(r),flush=True)
        except Exception as e:ce[s]=str(e);print('CR_FAIL',s,str(e)[:90],flush=True)
    m.add_context(cr,'CRYPTO')
    print('COVERAGE',json.dumps({'fxLoaded':len(fx),'fxRequested':len(m.FX),'fxFailed':fe,'cryptoLoaded':len(cr),'cryptoRequested':len(m.CRYPTO),'cryptoFailed':ce,'sources':src}),flush=True)
    f=evolve(exec_cache(base(fx,'FX'),'FX'),'FX',50000);c=evolve(exec_cache(base(cr,'CRYPTO'),'CRYPTO'),'CRYPTO',50000)
    out={'version':VERSION,'providerCreditsUsed':0,'hiddenHoldoutEvaluated':False,'coverage':{'fxLoaded':len(fx),'fxRequested':len(m.FX),'cryptoLoaded':len(cr),'cryptoRequested':len(m.CRYPTO)},'forex':pack(f[0]),'crypto':pack(c[0]),'bothQualifiedForLock':bool(f[0] and c[0] and f[0][0][0] and c[0][0][0]),'iterations':{'fx':f[1],'crypto':c[1]},'integrity':'All symbols scanned; LIMIT unfilled = NO_TRADE; same-bar ambiguous outcome scored SL first; Aug excluded.'}
    print('FINAL_EXECUTION',json.dumps(out,indent=2),flush=True)
if __name__=='__main__':main()
