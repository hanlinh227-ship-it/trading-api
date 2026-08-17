#!/usr/bin/env python3
import json, math, random, statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
from scripts.offline_crypto_v28_separate import PROFILE

SNAP='data/provider_snapshots/crypto_4h_feb_jul_2026.json'
OUT='data/offline_crypto_precision_v36.json'
SYMBOLS='BTC ETH SOL HYPE SHIB TRX XRP AAVE ADA ALGO APT ARB ATOM AVAX BCH BONK CRV DOGE DOT ETC FIL FLOKI HBAR INJ JTO JUP KAITO LDO LINK LTC MOODENG NEAR ONDO OP ORDI PENGU PEPE PNUT POL POPCAT RENDER S STX SUI TAO TIA TON TRUMP UNI WIF WLD AIXBT ASTER FARTCOIN GRASS IP LIT PUMP VIRTUAL XPL ZEC'.split()
FAMILIES=sorted(set(PROFILE.get(s,'OTHER') for s in SYMBOLS)|{'OTHER'})
MONTHS=[('MAY','2026-05-01','2026-05-31'),('JUNE','2026-06-01','2026-06-30'),('JULY','2026-07-01','2026-07-31')]


def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def day(t):return t.date().isoformat()
def sg(x):return 1 if x>0 else -1 if x<0 else 0

def ema(v,n):
    out=[None]*len(v)
    if len(v)<n:return out
    e=sum(v[:n])/n;out[n-1]=e;k=2/(n+1)
    for i in range(n,len(v)):e=v[i]*k+e*(1-k);out[i]=e
    return out

def enrich(raw):
    rows=[{'dt':dt(x[0]),'open':x[1],'high':x[2],'low':x[3],'close':x[4]} for x in raw]
    c=[x['close'] for x in rows];e20=ema(c,20);e50=ema(c,50);tr=[0.0]*len(rows);atr=[None]*len(rows);rsi=[None]*len(rows);adx=[None]*len(rows)
    plus=[0.0]*len(rows);minus=[0.0]*len(rows)
    for i in range(1,len(rows)):
        tr[i]=max(rows[i]['high']-rows[i]['low'],abs(rows[i]['high']-c[i-1]),abs(rows[i]['low']-c[i-1]))
        up=rows[i]['high']-rows[i-1]['high'];dn=rows[i-1]['low']-rows[i]['low'];plus[i]=up if up>dn and up>0 else 0;minus[i]=dn if dn>up and dn>0 else 0
    if len(rows)>15:
        a=sum(tr[1:15])/14;pg=sum(plus[1:15])/14;mg=sum(minus[1:15])/14;ag=sum(max(c[i]-c[i-1],0) for i in range(1,15))/14;al=sum(max(c[i-1]-c[i],0) for i in range(1,15))/14;dx=[]
        for i in range(14,len(rows)):
            if i>14:
                a=(a*13+tr[i])/14;pg=(pg*13+plus[i])/14;mg=(mg*13+minus[i])/14;d=c[i]-c[i-1];ag=(ag*13+max(d,0))/14;al=(al*13+max(-d,0))/14
            atr[i]=a;rsi[i]=100 if al==0 else 100-100/(1+ag/al);pdi=100*pg/a if a else 0;mdi=100*mg/a if a else 0;den=pdi+mdi;dxv=100*abs(pdi-mdi)/den if den else 0;dx.append(dxv)
            if len(dx)>=14:adx[i]=sum(dx[-14:])/14
    # Completed UTC-day EMA state, mapped only after the daily candle closes.
    buckets=defaultdict(list)
    for i,r in enumerate(rows):buckets[r['dt'].date().isoformat()].append((i,r))
    daily=[]
    for d in sorted(buckets):
        z=buckets[d]
        if len(z)>=5:daily.append({'last_i':z[-1][0],'close':z[-1][1]['close']})
    dc=[x['close'] for x in daily];d20=ema(dc,20);d50=ema(dc,50);dmap={}
    for j,x in enumerate(daily):
        if d20[j] is not None and d50[j] is not None:
            st=1 if x['close']>d20[j]>d50[j] else -1 if x['close']<d20[j]<d50[j] else (1 if x['close']>d20[j] else -1);dmap[x['last_i']]=st
    lastd=0
    for i,r in enumerate(rows):
        if i in dmap:lastd=dmap[i]
        r.update({'ema20':e20[i],'ema50':e50[i],'atr':atr[i],'rsi':rsi[i],'adx':adx[i],'d1':lastd})
        if i>=18 and atr[i] and c[i]>0:
            r['ret8']=math.log(c[i]/c[i-2]) if c[i-2]>0 else 0;r['ret24']=math.log(c[i]/c[i-6]) if c[i-6]>0 else 0;r['ret72']=math.log(c[i]/c[i-18]) if c[i-18]>0 else 0
            r['mom24atr']=(c[i]-c[i-6])/atr[i];r['dev']=(c[i]-e20[i])/atr[i] if e20[i] else 0
    return rows

def maps(data):return {s:{r['dt']:(i,r) for i,r in enumerate(rows)} for s,rows in data.items()}

def regime_at(mp,t):
    eligible={}
    for s in SYMBOLS:
        q=mp[s].get(t)
        if q and q[1].get('ret24') is not None and q[1].get('adx') is not None:eligible[s]=q
    if len(eligible)<20:return None
    rets=[q[1]['ret24'] for q in eligible.values()];breadth=sum(x>0 for x in rets)/len(rets);med=statistics.median(rets);disp=statistics.pstdev(rets) or 1e-9
    btc=eligible.get('BTC');btc24=btc[1]['ret24'] if btc else med;btc72=btc[1]['ret72'] if btc else 0
    return eligible,{'breadth':breadth,'median24':med,'dispersion24':disp,'btc24':btc24,'btc72':btc72,'eligible':len(eligible)}

def features(sym,row,reg,side):
    h4=1 if row['close']>row['ema20']>row['ema50'] else -1 if row['close']<row['ema20']<row['ema50'] else (1 if row['close']>row['ema20'] else -1)
    ar=row['rsi'] if side==1 else 100-row['rsi'];ba=reg['breadth'] if side==1 else 1-reg['breadth'];rel24=side*(row['ret24']-reg['btc24']);rel72=side*(row['ret72']-reg['btc72'])
    family=PROFILE.get(sym,'OTHER');f=[side*h4,side*row['d1'],row['adx']/50,ar/100,side*row['mom24atr']/4,side*row['dev']/3,ba,side*reg['btc24']*20,side*reg['btc72']*10,rel24*20,rel72*10,abs(reg['median24'])*20,reg['dispersion24']*20,reg['eligible']/61]
    f += [1.0 if family==x else 0.0 for x in FAMILIES]
    f += [1.0 if sym==x else 0.0 for x in SYMBOLS]
    meta={'h4':h4,'d1':row['d1'],'adx':row['adx'],'rsi':row['rsi'],'mom':row['mom24atr'],'dev':row['dev'],'breadth':reg['breadth'],'btc24':reg['btc24'],'btc72':reg['btc72'],'rel24':row['ret24']-reg['btc24'],'rel72':row['ret72']-reg['btc72'],'family':family}
    return f,meta

def execute(rows,i,side,cfg):
    mode,rr,rf,sw,hold,off,exp,cut_after,cut_r=cfg;sig=rows[i];atr=sig['atr']
    if not atr or i+1>=len(rows):return None
    if mode=='MARKET':entry_i=i+1;entry=rows[entry_i]['open']
    else:
        entry=sig['close']-side*off*atr;entry_i=None
        for j in range(i+1,min(len(rows),i+1+exp)):
            if rows[j]['low']<=entry<=rows[j]['high']:entry_i=j;break
        if entry_i is None:return None
    recent=rows[max(0,i-sw+1):i+1];swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);struct=(entry-swing) if side==1 else (swing-entry);risk=max(rf*atr,struct+.08*atr)
    if risk<=0 or risk>3.2*atr:return None
    sl=entry-side*risk;tp=entry+side*rr*risk;end=min(len(rows),entry_i+hold)
    for j in range(entry_i,end):
        b=rows[j];hs=b['low']<=sl if side==1 else b['high']>=sl;ht=b['high']>=tp if side==1 else b['low']<=tp
        if hs and ht:return {'result':'SL','r':-1.0,'bars':j-entry_i+1,'ambiguous':True}
        if hs:return {'result':'SL','r':-1.0,'bars':j-entry_i+1}
        if ht:return {'result':'TP','r':rr,'bars':j-entry_i+1}
        age=j-entry_i+1
        if cut_after and age>=cut_after and b.get('ema20') is not None:
            cur=(b['close']-entry)/risk*side;broken=(b['close']-b['ema20'])*side<0
            if broken and cur<=cut_r:return {'result':'CUT','r':max(-1,cur),'bars':age,'cutReason':'4H_EMA20_THESIS_BREAK'}
    last=rows[max(entry_i,min(len(rows)-1,end-1))]['close'];cur=(last-entry)/risk*side
    return {'result':'CUT','r':max(-1,min(rr,cur)),'bars':end-entry_i,'cutReason':'TIMEOUT'}

def build_events(data,mp,cfg):
    times=sorted(set().union(*(set(x) for x in mp.values())))
    out=[];scan_slots=0;elig_scans=0
    for t in times:
        d=day(t)
        if d<'2026-02-10' or d>'2026-07-31':continue
        regpack=regime_at(mp,t)
        if not regpack:continue
        eligible,reg=regpack;scan_slots+=61
        for sym in SYMBOLS:
            q=eligible.get(sym)
            if not q:continue
            i,row=q;elig_scans+=1
            for side in (1,-1):
                feat,meta=features(sym,row,reg,side);o=execute(data[sym],i,side,cfg)
                if o:out.append({'symbol':sym,'time':t,'day':d,'side':side,'x':feat,'meta':meta,**o})
    return out,scan_slots,elig_scans

def model(train,kind,depth,leaf):
    q=[x for x in train if x['result'] in ('TP','SL')]
    if len(q)<150:return None
    X=np.asarray([x['x'] for x in q],float);y=np.asarray([x['result']=='TP' for x in q],int)
    if len(set(y))<2:return None
    if kind=='ET':m=ExtraTreesClassifier(n_estimators=240,max_depth=depth,min_samples_leaf=leaf,max_features=.65,class_weight='balanced_subsample',n_jobs=-1,random_state=360817)
    else:m=HistGradientBoostingClassifier(max_iter=170,max_leaf_nodes=2**depth-1,min_samples_leaf=leaf,learning_rate=.05,l2_regularization=3.5,random_state=360817)
    m.fit(X,y);return m

def select_month(events,train_end,a,b,hp):
    kind,depth,leaf,th,margin,topk=hp;tr=[x for x in events if x['day']<=train_end];te=[x for x in events if a<=x['day']<=b];mdl=model(tr,kind,depth,leaf)
    if mdl is None or not te:return []
    pr=mdl.predict_proba(np.asarray([x['x'] for x in te],float))[:,1];g=defaultdict(list)
    for e,p in zip(te,pr):g[(e['time'],e['symbol'])].append((float(p),e))
    cand=[]
    for k,z in g.items():
        z=sorted(z,key=lambda x:x[0],reverse=True);best=z[0];other=z[1][0] if len(z)>1 else 0
        if best[0]>=th and best[0]-other>=margin:
            q=dict(best[1]);q['prob']=best[0];q['edge']=best[0]-other;cand.append(q)
    # Crypto can produce many correlated signals; choose only highest independent candidates per UTC day.
    by=defaultdict(list)
    for x in cand:by[x['day']].append(x)
    out=[]
    for d,z in by.items():out.extend(sorted(z,key=lambda x:(x['prob'],x['edge']),reverse=True)[:topk])
    return out

def sm(z):
    tp=sum(x['result']=='TP' for x in z);sl=sum(x['result']=='SL' for x in z);cuts=[x for x in z if x['result']=='CUT'];den=tp+sl
    return {'n':len(z),'tp':tp,'sl':sl,'cut':len(cuts),'wr':round(100*tp/den,2) if den else 0,'meanR':round(statistics.mean(x['r'] for x in z),3) if z else -9,'avgCutR':round(statistics.mean(x['r'] for x in cuts),3) if cuts else None,'cutRate':round(100*len(cuts)/len(z),2) if z else 0,'symbolsTraded':len(set(x['symbol'] for x in z))}

def wf(events,hp):
    out={};allz=[]
    for name,te,a,b in [('MAY','2026-04-30','2026-05-01','2026-05-31'),('JUNE','2026-05-31','2026-06-01','2026-06-30'),('JULY','2026-06-30','2026-07-01','2026-07-31')]:
        z=select_month(events,te,a,b,hp);out[name]=sm(z);allz+=z
    out['COMBINED']=sm(allz);return out

def quality(f):
    c=f['COMBINED'];ms=[f[x] for x in ('MAY','JUNE','JULY')];enough=c['n']>=24 and all(x['n']>=5 for x in ms)
    hit=enough and c['wr']>=80 and c['meanR']>0 and c['cutRate']<=50 and all(x['wr']>=65 for x in ms)
    pen=sum(max(0,5-x['n'])*5 for x in ms)+max(0,24-c['n'])*2
    return (int(hit),c['wr']-pen,min(x['wr'] for x in ms),c['meanR'],-c['cutRate'],c['n'])

def configs():
    out=[]
    for mode in ('MARKET','LIMIT'):
      offs=(0,) if mode=='MARKET' else (.2,.35,.5,.7)
      exps=(1,) if mode=='MARKET' else (1,2)
      for rr in (1.0,1.5):
       for rf in (.65,.8,1.0,1.2):
        for sw in (3,5,8):
         for hold in (4,6,9,12):
          for off in offs:
           for exp in exps:
            for ca in (0,1,2,3):
             for cr in ((0,) if ca==0 else (-.15,-.3,-.45)):out.append((mode,rr,rf,sw,hold,off,exp,ca,cr))
    return out

def main():
    doc=json.load(open(SNAP,encoding='utf-8'))
    if doc.get('coverageCount')!=61 or set(doc.get('data',{}))!=set(SYMBOLS):raise RuntimeError('Snapshot not 61/61')
    data={s:enrich(doc['data'][s]) for s in SYMBOLS};mp=maps(data);cfgs=configs();rng=random.Random(36080);rng.shuffle(cfgs)
    hps=[(k,d,l,t,m,kd) for k in ('ET','HGB') for d in (3,5,7) for l in (8,15,25,40) for t in (.62,.66,.7,.74,.78,.82,.86,.9,.93) for m in (0,.04,.08,.12,.16) for kd in (1,2)]
    best=None;payload=None;tested=0
    for cfg in cfgs[:160]:
        events,slots,elig=build_events(data,mp,cfg)
        if len(events)<300:continue
        hs=list(hps);rng.shuffle(hs)
        for hp in hs[:50]:
            folds=wf(events,hp);q=quality(folds);tested+=1
            if best is None or q>best:
                best=q;payload={'execution':{'mode':cfg[0],'rr':cfg[1],'riskFloorATR':cfg[2],'swingBars4H':cfg[3],'maxHoldBars4H':cfg[4],'limitOffsetATR':cfg[5],'limitExpiryBars4H':cfg[6],'cutAfterBars4H':cfg[7],'cutRThreshold':cfg[8]},'model':{'kind':hp[0],'depth':hp[1],'leaf':hp[2],'threshold':hp[3],'sideMargin':hp[4],'topKPerDay':hp[5]},'folds':folds,'quality':q,'eventCount':len(events),'requestedScanSlots':slots,'eligibleScanSlots':elig}
                print('BEST',tested,json.dumps(payload),flush=True)
            if q[0]:break
        if best and best[0]:break
    res={'version':'CRYPTO_PRECISION_V36','providerCreditsUsed':0,'snapshot':SNAP,'scanUniverse':SYMBOLS,'scanUniverseCount':61,'snapshotCoverageCount':61,'allSymbolsLoaded':True,'hiddenFinalAugustFetched':False,'testedCandidates':tested,'best':payload,'preAugustTargetMet':bool(best and best[0]),'promotionRule':'Require combined May-Jul TP/SL WR >=80, planned RR exactly 1.0 or1.5, positive expectancy incl CUT, <=50% CUT rate, >=24 selected and >=5/month; final Aug untouched.'}
    Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(res,open(OUT,'w'),indent=2);print('FINAL',json.dumps(res,indent=2),flush=True)
if __name__=='__main__':main()
