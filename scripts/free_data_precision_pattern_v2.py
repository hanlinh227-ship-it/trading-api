#!/usr/bin/env python3
import json, math, statistics
from collections import defaultdict
import scripts.free_data_precision_evolver_v1 as m

VERSION='FREE_DATA_PRECISION_PATTERN_V2'

def b3(x,a,b):
    return 0 if x<a else (1 if x<b else 2)
def b4(x,a,b,c):
    return 0 if x<a else (1 if x<b else (2 if x<c else 3))
def session(h):
    return 0 if h in (0,4) else (1 if h in (8,12) else 2)

def enrich_trade(rows,i,side,rr,risk,hold,market,symbol):
    o=m.trade_outcome(rows,i,side,rr,risk,hold)
    if not o:return None
    r=rows[i]; exit_i=min(len(rows)-1,i+o['bars'])
    aligned_rsi=r['rsi'] if side==1 else 100-r['rsi']
    common={'symbol':symbol,'ts':r['ts'],'exitTs':rows[exit_i]['ts'],'day':m.day(r['ts']),'side':side,'result':o['result'],'r':o['r'],'rr':rr,
            'adx':r['adx'],'mom':abs(r['mom6atr']),'dist':r['emaDistAtr'],'long':1 if m.sign(r['r18'])==side else 0,'ar':aligned_rsi}
    if market=='FX':
        common.update({'factor':side*r['factorNorm'],'sess':session(m.hour(r['ts']))})
        common['exact']=(side,common['sess'],b3(common['adx'],22,30),b3(common['mom'],.55,1.1),b4(common['factor'],0,.5,1.1),b3(common['dist'],.4,.9),common['long'],b3(common['ar'],52,64))
        common['mid']=(side,common['sess'],b4(common['factor'],0,.5,1.1),common['long'],b3(common['adx'],22,30))
        common['broad']=(side,common['sess'],b3(common['factor'],0,.75),common['long'])
        common['rawScore']=common['adx']/30+common['mom']+.55*max(-1,min(2,common['factor']))+.25*common['long']-.15*common['dist']
    else:
        ba=r['breadth'] if side==1 else 1-r['breadth']; bt=side*r['btcR6']; rel=side*r['rel6']
        common.update({'breadthA':ba,'btcA':bt,'relA':rel})
        common['exact']=(side,b4(ba,.5,.62,.76),1 if bt>0 else 0,b3(common['adx'],22,30),b3(common['mom'],.55,1.1),b4(rel,0,.005,.015),b3(common['dist'],.4,.9),common['long'],b3(common['ar'],52,64))
        common['mid']=(side,b4(ba,.5,.62,.76),1 if bt>0 else 0,b4(rel,0,.005,.015),common['long'])
        common['broad']=(side,b4(ba,.5,.62,.76),1 if bt>0 else 0)
        common['rawScore']=common['adx']/30+common['mom']+1.2*max(0,ba-.5)+35*rel+.2*(bt>0)+.2*common['long']-.15*common['dist']
    return common

def base_events(data,market,rr,risk,hold):
    out=[]
    for s,rows in data.items():
        for i,r in enumerate(rows):
            if i<100 or m.day(r['ts'])>=m.HIDDEN_START:continue
            if r.get('adx') is None or r.get('ema100') is None:continue
            if market=='FX' and r.get('factorNorm') is None:continue
            if market=='CRYPTO' and r.get('breadth') is None:continue
            side=1 if r['ema20']>r['ema50'] and r['r6']>0 else (-1 if r['ema20']<r['ema50'] and r['r6']<0 else 0)
            if not side or r['adx']<14 or abs(r['mom6atr'])<.15 or r['emaDistAtr']>1.8:continue
            z=enrich_trade(rows,i,side,rr,risk,hold,market,s)
            if z:out.append(z)
    return sorted(out,key=lambda x:(x['ts'],x['symbol']))

def posterior(st,key,alpha,base):
    w,n=st.get(key,(0,0));return (w+alpha*base)/(n+alpha),n

def online_select(events, market, cfg):
    broad=defaultdict(lambda:[0,0]);mid=defaultdict(lambda:[0,0]);exact=defaultdict(lambda:[0,0]);globalst=[0,0]
    pending=[];qualified=[]
    byts=defaultdict(list)
    for e in events:byts[e['ts']].append(e)
    for ts in sorted(byts):
        still=[]
        for e in pending:
            if e['exitTs']<ts:
                y=1 if e['result']=='TP' else 0 if e['result']=='SL' else None
                if y is not None:
                    globalst[0]+=y;globalst[1]+=1
                    for st,k in ((broad,e['broad']),(mid,e['mid']),(exact,e['exact'])):
                        st[k][0]+=y;st[k][1]+=1
            else: still.append(e)
        pending=still
        gp=(globalst[0]+3)/(globalst[1]+6)
        for e in byts[ts]:
            pb,nb=posterior(broad,e['broad'],cfg['ab'],gp)
            pm,nm=posterior(mid,e['mid'],cfg['am'],pb)
            pe,ne=posterior(exact,e['exact'],cfg['ae'],pm)
            eff=ne+cfg['midWeight']*nm+cfg['broadWeight']*nb
            # confidence blend rewards exact support but remains conservative under sparse patterns
            p=(pe*max(1,ne)+pm*cfg['midWeight']*max(1,nm)+pb*cfg['broadWeight']*max(1,nb))/(max(1,ne)+cfg['midWeight']*max(1,nm)+cfg['broadWeight']*max(1,nb))
            se=math.sqrt(max(1e-6,p*(1-p)/(eff+4)))
            lower=p-cfg['z']*se
            e2=dict(e);e2.update({'pred':p,'lower':lower,'support':eff,'rankScore':lower+.02*e['rawScore']})
            if eff>=cfg['support'] and p>=cfg['pmin'] and lower>=cfg['lower']:
                qualified.append(e2)
            pending.append(e)
    byday=defaultdict(list)
    for e in qualified:byday[e['day']].append(e)
    sel=[]
    for d,z in byday.items():sel.extend(sorted(z,key=lambda x:x['rankScore'],reverse=True)[:cfg['topk']])
    return sel

def evstats(rows):return {name:m.stats(rows,a,b) for name,a,b in m.FOLDS}

def obj(ev,market):
    req={'DEV':25 if market=='FX' else 30,'JUNE':6,'JULY':6}
    qs=all(ev[k]['n']>=req[k] and ev[k]['wr']>=80 and ev[k]['meanR']>0 and ev[k]['resolvedRate']>=70 for k in req)
    pen=sum(max(0,req[k]-ev[k]['n'])*3 for k in req)
    worst=min(ev[k]['wr'] for k in req if ev[k]['n']) if any(ev[k]['n'] for k in req) else 0
    avg=sum(ev[k]['wr'] for k in req)/3
    return (1 if qs else 0,worst-pen,avg,sum(ev[k]['meanR'] for k in req)/3,sum(ev[k]['n'] for k in req))

def search(data,market):
    best=None;count=0
    for rr in (1.0,1.5):
      for risk in (.7,1.0,1.3):
       for hold in (6,9,12,18):
        events=base_events(data,market,rr,risk,hold)
        for pmin in (.68,.72,.76,.80,.84,.88):
         for lower in (.50,.55,.60,.65,.70,.75):
          if lower>pmin:continue
          for support in (4,6,8,12,16):
           for topk in (1,2):
            for z in (.0,.5,1.0):
             cfg={'pmin':pmin,'lower':lower,'support':support,'topk':topk,'z':z,'ab':8,'am':6,'ae':4,'midWeight':.45,'broadWeight':.2}
             rows=online_select(events,market,cfg);ev=evstats(rows);o=obj(ev,market);count+=1
             item=(o,{'rr':rr,'risk':risk,'hold':hold,**cfg},ev)
             if best is None or o>best[0]:best=item
             if o[0]:return best,count
    return best,count

def pack(x):
    if not x:return None
    o,p,e=x;return {'qualified':bool(o[0]),'objective':o,'params':p,'folds':{k:m.compact(v) for k,v in e.items()}}

def main():
    print(json.dumps({'version':VERSION,'providerCreditsUsed':0,'hiddenHoldoutEvaluated':False}))
    fx={};cr={};failfx={};failcr={};src={}
    for s in m.FX:
        try:fx[s]=m.indicators(m.fetch_fx(s));print('FX',s,len(fx[s]))
        except Exception as e:failfx[s]=str(e);print('FX_FAIL',s,str(e)[:100])
    m.add_context(fx,'FX')
    for s in m.CRYPTO:
        try:
            r,q=m.fetch_crypto(s);cr[s]=m.indicators(r);src[s]=q;print('CR',s,q,len(r))
        except Exception as e:failcr[s]=str(e);print('CR_FAIL',s,str(e)[:100])
    m.add_context(cr,'CRYPTO')
    print('COVERAGE',json.dumps({'fx':[len(fx),len(m.FX),failfx],'crypto':[len(cr),len(m.CRYPTO),failcr]}))
    f,nf=search(fx,'FX');c,nc=search(cr,'CRYPTO')
    out={'version':VERSION,'providerCreditsUsed':0,'hiddenHoldoutEvaluated':False,'coverage':{'fx':len(fx),'fxRequested':len(m.FX),'crypto':len(cr),'cryptoRequested':len(m.CRYPTO)},'forex':pack(f),'crypto':pack(c),'bothQualifiedForLock':bool(f and c and f[0][0] and c[0][0]),'searches':{'fx':nf,'crypto':nc},'integrity':'Online pattern outcomes are only added after their exit timestamp; August is excluded.'}
    print('FINAL_PATTERN',json.dumps(out,indent=2))
if __name__=='__main__':main()
