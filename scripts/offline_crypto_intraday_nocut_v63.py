#!/usr/bin/env python3
import json, statistics
from collections import defaultdict
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier
import scripts.offline_crypto_precision_evolver_v36 as v
import scripts.offline_crypto_daily_per_symbol_v37 as b
from scripts.offline_crypto_v28_separate import PROFILE

OUT='data/offline_crypto_intraday_nocut_v63.json'
TARGET=80.0
WINDOWS={'ALL':(0,4,8,12,16),'EARLY':(0,4),'MID':(8,12),'LATE':(12,16)}
DIRS=('BOTH','BUY','SELL')
MONTHS=[('MAY','2026-05-01','2026-05-31'),('JUNE','2026-06-01','2026-06-30'),('JULY','2026-07-01','2026-07-31')]
CFGS=[(rr,rf,sw) for rr in (1.0,2.0) for rf in (.60,.75,1.0,1.25,1.5,2.0) for sw in (3,5,8)]
MODEL_SPECS=[('HGB',4,12),('HGB',5,20),('ET',10,8),('ET',14,5)]
THRESH=(.55,.62,.70,.78)
MARGINS=(0.0,.06)
MAXTRADES=(1,2,3)
PROFILE_DRIVERS={
 'BTC_CORE':['BTC ETF/treasury demand','miner/on-chain flows','macro liquidity and rates','BTC dominance'],
 'ETH_CORE':['ETH ETF/staking flows','Ethereum upgrades','L2 activity and fees','ETH/BTC relative strength'],
 'SOL_ECOSYSTEM':['Solana network activity','SOL ecosystem launches','validator/staking flows','SOL/BTC and SOL/ETH relative strength'],
 'MEME':['social attention velocity','whale/exchange flows','meme-sector breadth','listing/delisting catalysts'],
 'SOL_MEME':['Solana meme breadth','DEX volume/liquidity','social attention and whales','SOL trend'],
 'DEFI':['protocol TVL/fees','governance/upgrades','token incentives/unlocks','ETH and DeFi breadth'],
 'L1':['chain upgrades/adoption','staking/validator flows','ecosystem TVL/activity','BTC market regime'],
 'L2':['rollup activity/fees','token unlocks','Ethereum roadmap','L2 relative strength'],
 'AI_COMPUTE':['AI/compute narrative catalysts','network demand/revenue','token unlocks','AI-sector breadth'],
 'AI_INFOFI':['AI/InfoFi product growth','attention/data demand','token unlocks/listings','AI-sector breadth'],
 'AI_AGENT':['AI-agent adoption','ecosystem integrations','token unlocks/listings','AI-sector breadth'],
 'AI_DATA':['AI data demand','network usage','token unlocks/listings','AI-sector breadth'],
 'RWA':['RWA adoption/partnerships','regulation','token unlocks','RWA sector flows'],
 'ORACLE_RWA':['oracle integrations','RWA/DeFi adoption','staking/token economics','ETH/DeFi regime'],
 'INTERCHAIN':['IBC/interchain activity','ecosystem upgrades','staking/unlocks','L1 sector breadth'],
 'BTC_ECOSYSTEM':['BTC ecosystem activity','BTC trend/dominance','protocol upgrades','token unlocks'],
 'BTC_BETA':['BTC trend/dominance','relative beta to BTC','payments/adoption news','liquidity flows'],
 'PERP_DEX':['perp DEX volume/OI','protocol incentives','token unlocks','market leverage regime'],
 'L1_PAYMENTS':['payments adoption','chain usage','staking/network changes','BTC risk regime'],
 'PAYMENTS':['payments/remittance adoption','regulation','institutional partnerships','BTC risk regime'],
 'ETH_STAKING':['ETH staking flows','LST/LRT market share','Ethereum upgrades','DeFi liquidity'],
 'SOL_DEFI':['Solana DeFi TVL/volume','SOL trend','protocol incentives','token unlocks'],
 'POW_L1':['PoW miner/hashrate economics','chain upgrades','BTC correlation','exchange liquidity'],
 'STORAGE':['storage demand/network usage','protocol upgrades','token unlocks','AI/data narrative'],
 'MODULAR':['modular/data-availability adoption','ecosystem integrations','token unlocks','L1/L2 breadth'],
 'PRIVACY':['privacy regulation','network adoption','exchange listing access','BTC market regime'],
 'IDENTITY':['identity/adoption integrations','network activity','token unlocks/listings','sector flows'],
 'IP_RWA':['IP/RWA partnerships','licensing/adoption','token unlocks','RWA sector flows'],
 'MESSAGING_L1':['messaging ecosystem growth','chain usage','token unlocks/listings','BTC market regime'],
 'OTHER':['project announcements','token unlocks/listings','exchange/on-chain flows','BTC market regime'],
}

def exec_intraday(rows,i,side,cfg):
    rr,rf,sw=cfg
    if i+1>=len(rows) or rows[i].get('atr') is None:return None
    sig=rows[i];atr=sig['atr'];ei=i+1;entry=rows[ei]['open'];eday=rows[ei]['dt'].date();recent=rows[max(0,i-sw+1):i+1]
    swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent);struct=entry-swing if side==1 else swing-entry;risk=max(rf*atr,struct+.05*atr,.20*atr)
    if risk<=0 or risk>4*atr:return None
    sl=entry-side*risk;tp=entry+side*rr*risk;lastj=ei
    for j in range(ei,len(rows)):
        if rows[j]['dt'].date()!=eday:break
        lastj=j;x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
        if hs and ht:return ('SL',-1.0,j-ei+1)
        if hs:return ('SL',-1.0,j-ei+1)
        if ht:return ('TP',rr,j-ei+1)
    return ('TIMEOUT',0.0,lastj-ei+1)

def build_base(raw,rows):
    cfg=(1.0,1.0,5);out=[]
    for e in raw:
        if e['time'].hour==20:continue
        o=exec_intraday(rows,e['i'],e['side'],cfg)
        if o:q=dict(e);q['label']=1 if o[0]=='TP' else 0;out.append(q)
    return out

def fit(train,spec,seed):
    if len(train)<120:return None
    X=np.asarray([x['x'] for x in train],float);y=np.asarray([x['label'] for x in train],int)
    if len(set(y))<2:return None
    kind,d,l=spec
    if kind=='ET':m=ExtraTreesClassifier(n_estimators=220,max_depth=d,min_samples_leaf=l,max_features=.75,class_weight='balanced_subsample',n_jobs=-1,random_state=seed)
    else:m=HistGradientBoostingClassifier(max_iter=150,max_leaf_nodes=2**d-1,min_samples_leaf=l,learning_rate=.05,l2_regularization=4.0,random_state=seed)
    m.fit(X,y);return m

def score_period(base,train_end,a,z,spec,seed):
    tr=[x for x in base if x['day']<=train_end];te=[x for x in base if a<=x['day']<=z];m=fit(tr,spec,seed)
    if m is None or not te:return []
    p=m.predict_proba(np.asarray([x['x'] for x in te],float))[:,1];return [dict(x,prob=float(q)) for x,q in zip(te,p)]

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
            z=sorted(times[t],key=lambda q:q['prob'],reverse=True);best=z[0];other=z[1]['prob'] if len(z)>1 else 0.0;edge=best['prob']-other;is_last=ti==len(ordered)-1
            if best['prob']>=thr and edge>=margin:
                chosen.append(best)
                if len(chosen)>=maxtrades:break
            elif is_last and not chosen:chosen.append(best)
        if not chosen and ordered:chosen=[sorted(times[ordered[-1]],key=lambda q:q['prob'],reverse=True)[0]]
        out.extend(chosen)
    return out

def expected_days(scored,window,direction):
    h=set(WINDOWS[window]);return len(set(x['day'] for x in scored if x['time'].hour in h and (direction=='BOTH' or (direction=='BUY' and x['side']==1) or (direction=='SELL' and x['side']==-1))))

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
    scored_by_spec={spec:score_period(base,'2026-03-31','2026-04-01','2026-04-30',spec,seed+i) for i,spec in enumerate(MODEL_SPECS)};best=None;bp=None
    for spec,scored in scored_by_spec.items():
      if not scored:continue
      for w in WINDOWS:
       for d in DIRS:
        exp=expected_days(scored,w,d)
        if exp<20:continue
        for th in THRESH:
         for ma in MARGINS:
          for mt in MAXTRADES:
            sel=choose_day(scored,w,d,th,ma,mt)
            for cfg in CFGS:
                s=eval_sel(sel,rows,cfg,exp);q=rank(s)
                if best is None or q>best:best=q;bp=(spec,w,d,th,ma,mt,cfg,s)
    return bp

def style(sym,bp):
    spec,w,d,th,ma,mt,cfg,dev=bp;prof=PROFILE.get(sym,'OTHER');drivers=PROFILE_DRIVERS.get(prof,PROFILE_DRIVERS['OTHER'])
    return {'styleId':f'{sym}_V63_{prof}_{spec[0]}_{w}_{d}_RR{int(cfg[0])}_RF{cfg[1]}_SW{cfg[2]}','profile':prof,'model':{'kind':spec[0],'depth':spec[1],'leaf':spec[2]},'window':w,'direction':d,'triggerProbability':th,'sideEdge':ma,'maxTradesPerDay':mt,'execution':{'rr':cfg[0],'riskFloorATR':cfg[1],'swingBars4H':cfg[2],'sameBarTPandSL':'SL'},'symbolNewsDrivers':[f'{sym} project/protocol announcements',f'{sym} token unlock and supply schedule',f'{sym} exchange/on-chain/whale flows',*drivers],'liveNewsRule':f'Before each {sym} live entry refresh {sym}-specific headlines, unlock/listing/chain data and BTC regime. Historical V63 score does not fabricate unavailable historical news.','aprilStyleSelection':dev}

def main():
    doc=json.load(open(v.SNAP,encoding='utf-8'));data={s:v.enrich(doc['data'][s]) for s in v.SYMBOLS};mp=v.maps(data);raw=b.build_raw(data,mp);results={}
    for si,sym in enumerate(v.SYMBOLS):
        base=build_base(raw.get(sym,[]),data[sym]);bp=tune_april(sym,base,data[sym],630000+si*100)
        if bp is None:results[sym]={'status':'FAIL','reason':'no style/history'};print('FAIL',sym,'NO_STYLE',flush=True);continue
        sty=style(sym,bp);monthly=[];allsel=[]
        for mi,(name,a,z) in enumerate(MONTHS):
            train_end={'MAY':'2026-04-30','JUNE':'2026-05-31','JULY':'2026-06-30'}[name];scored=score_period(base,train_end,a,z,bp[0],730000+si*100+mi);exp=expected_days(scored,sty['window'],sty['direction']);sel=choose_day(scored,sty['window'],sty['direction'],sty['triggerProbability'],sty['sideEdge'],sty['maxTradesPerDay']);s=eval_sel(sel,data[sym],bp[6],exp);monthly.append({'month':name,**s});allsel.extend(sel)
        expected=sum(x['expectedDays'] for x in monthly);final=eval_sel(allsel,data[sym],bp[6],expected);ok=bool(expected>=80 and rank(final)[0]);results[sym]={'status':'PASS' if ok else 'FAIL','style':sty,'walkForwardMayJuly':final,'monthly':monthly};print('PASS' if ok else 'FAIL',sym,final,flush=True)
    passed=[s for s in v.SYMBOLS if results[s]['status']=='PASS'];failed=[s for s in v.SYMBOLS if results[s]['status']!='PASS'];ans={'version':'CRYPTO_INTRADAY_NOCUT_V63','definition':{'cutUsed':False,'noTradeAllowed':False,'minTradesPerEligibleCalendarDay':1,'maxTradesPerDay':3,'rrAllowed':[1.0,2.0],'timeout':'non-win; fixed UTC intraday end, never TP','wr':'TP/all trades','styleSelection':'April using model trained through March; style frozen May-Jul; model refit monthly only on past data','crypto20UTCSignalExcluded':'entry would start next UTC day'},'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'allPassed':not failed,'results':results};Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(ans,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:ans[k] for k in ('passCount','failCount','failed','allPassed')},indent=2),flush=True)
if __name__=='__main__':main()
