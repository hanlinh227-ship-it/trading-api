#!/usr/bin/env python3
import json, os, math, statistics, itertools
from collections import defaultdict
from scripts.offline_crossmarket_rolling_blind_v4 import extract_crypto

# Crypto-only profile families. Each symbol is mapped to the drivers that matter most for that asset.
PROFILE={
'BTC':'BTC_CORE','ETH':'ETH_CORE','SOL':'SOL_ECOSYSTEM','HYPE':'PERP_DEX','SHIB':'MEME','TRX':'L1_PAYMENTS','XRP':'PAYMENTS',
'AAVE':'DEFI','ADA':'L1','ALGO':'L1','APT':'L1','ARB':'L2','ATOM':'INTERCHAIN','AVAX':'L1','BCH':'BTC_BETA','BONK':'SOL_MEME',
'CRV':'DEFI','DOGE':'MEME','DOT':'INTERCHAIN','ETC':'POW_L1','FIL':'STORAGE','FLOKI':'MEME','HBAR':'ENTERPRISE_L1','INJ':'PERP_DEX',
'JTO':'SOL_DEFI','JUP':'SOL_DEFI','KAITO':'AI_INFOFI','LDO':'ETH_STAKING','LINK':'ORACLE_RWA','LTC':'BTC_BETA','MOODENG':'MEME',
'NEAR':'L1_AI','ONDO':'RWA','OP':'L2','ORDI':'BTC_ECOSYSTEM','PENGU':'MEME','PEPE':'MEME','PNUT':'MEME','POL':'L2',
'POPCAT':'MEME','RENDER':'AI_COMPUTE','S':'L1','STX':'BTC_ECOSYSTEM','SUI':'L1','TAO':'AI_COMPUTE','TIA':'MODULAR','TON':'MESSAGING_L1',
'TRUMP':'MEME','UNI':'DEFI','WIF':'SOL_MEME','WLD':'AI_IDENTITY','AIXBT':'AI_INFOFI','ASTER':'PERP_DEX','FARTCOIN':'MEME','GRASS':'AI_DATA',
'IP':'IP_RWA','LIT':'IDENTITY','PUMP':'SOL_MEME','VIRTUAL':'AI_AGENT','XPL':'L1','ZEC':'PRIVACY'
}

FAMILY_WEIGHTS={
'BTC_CORE':(1.35,1.05,.85,.55),'ETH_CORE':(1.20,1.20,1.00,.65),'SOL_ECOSYSTEM':(1.15,1.15,.95,.80),
'SOL_DEFI':(1.10,1.20,1.00,.85),'SOL_MEME':(1.25,1.05,.70,1.15),'MEME':(1.30,.95,.65,1.25),
'DEFI':(1.05,1.20,1.10,.80),'L2':(1.10,1.15,1.00,.85),'L1':(1.10,1.10,1.05,.80),'L1_AI':(1.10,1.10,1.00,.90),
'PERP_DEX':(1.15,1.10,.95,.95),'AI_INFOFI':(1.20,1.00,.85,1.00),'AI_COMPUTE':(1.15,1.10,.95,.90),
'AI_DATA':(1.20,1.00,.85,.95),'AI_AGENT':(1.20,1.00,.85,1.05),'AI_IDENTITY':(1.15,1.05,.90,.95),
'RWA':(1.00,1.20,1.15,.75),'ORACLE_RWA':(1.00,1.20,1.20,.75),'BTC_BETA':(1.25,1.00,.85,.80),
'BTC_ECOSYSTEM':(1.25,1.05,.90,.85),'INTERCHAIN':(1.05,1.10,1.05,.75),'STORAGE':(1.10,1.05,.95,.80),
'ETH_STAKING':(1.05,1.20,1.10,.75),'PAYMENTS':(1.00,1.10,1.00,.75),'L1_PAYMENTS':(1.00,1.10,1.00,.75),
'ENTERPRISE_L1':(1.00,1.10,1.05,.70),'POW_L1':(1.15,1.00,.90,.75),'MODULAR':(1.10,1.10,1.00,.80),
'MESSAGING_L1':(1.10,1.05,.95,.80),'PRIVACY':(1.10,1.00,.90,.75),'IDENTITY':(1.05,1.05,1.00,.75),
'IP_RWA':(1.00,1.15,1.10,.80)
}

def base_symbol(sym): return sym[:-4] if sym.endswith('USDT') else sym

def prep(rows):
    out=[]
    for r in rows:
        if r['rr']<1.0: continue
        z=dict(r); coin=base_symbol(r['symbol']); fam=PROFILE.get(coin,'L1')
        z['coin']=coin; z['family']=fam; z['targetRR']=min(r['rr'],1.5); z['targetR']=z['targetRR'] if r['r']>0 else -1.0
        wb,wm,wh,wc=FAMILY_WEIGHTS.get(fam,(1,1,1,.8))
        breadth=r.get('breadth')
        align=0.0
        if breadth is not None:
            align=(breadth-.5)*(1 if r['side']=='BUY' else -1)*2
        micro_align=0.0 if r['micro']==0 else (1.0 if (r['side']=='BUY' and r['micro']>0) or (r['side']=='SELL' and r['micro']<0) else -1.0)
        # Profile-aware pre-outcome strength; different families weight market beta, macro/HTF and chase differently.
        z['profileStrength']=wb*align + wm*(r['macro']/6.0) + wh*(r['htf']/10.0) + .55*micro_align - wc*r['chase']
        out.append(z)
    return out

def sm(rows):
    if not rows:return {'n':0}
    w=sum(r['targetR']>0 for r in rows); l=sum(r['targetR']<0 for r in rows); n=w+l
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':l,'wr':round(100*w/n,2),
            'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def wilson(w,n,z=1.2816):
    if n<=0:return 0.0
    p=w/n;den=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/den

def states(rows):
    by=defaultdict(list)
    for r in rows: by[r['date']].append(r)
    out={}
    for d,x in by.items():
        b=[r['breadth'] for r in x if r.get('breadth') is not None]
        breadth=statistics.median(b) if b else None
        out[d]={'breadth':breadth,
                'medianHTF':statistics.median(r['htf'] for r in x),
                'medianMacro':statistics.median(r['macro'] for r in x),
                'medianStrength':statistics.median(r['profileStrength'] for r in x),
                'buyShare':sum(r['side']=='BUY' for r in x)/max(1,len(x))}
    return out

def candidates():
    for p in itertools.product(
      ('ANY','ALIGN','EXTREME_ALIGN','BULL_CONT','BEAR_CONT','MID'),
      (-1.0,-.25,.25,.75,1.25,1.75),(0,1.5,3,5),(0,3,6,10),('ANY','AGREE'),(999,1.5,.75,.35),
      ('ANY','MEME_BETA','STRUCTURAL','BTC_LINKED','AI','DEFI_L2')):
        yield p

def bucket(f):
    if f in ('MEME','SOL_MEME'):return 'MEME_BETA'
    if f in ('BTC_CORE','BTC_BETA','BTC_ECOSYSTEM'):return 'BTC_LINKED'
    if f.startswith('AI_') or f in ('L1_AI',):return 'AI'
    if f in ('DEFI','SOL_DEFI','L2','ETH_STAKING','ORACLE_RWA','RWA'):return 'DEFI_L2'
    return 'STRUCTURAL'

def passed(r,p,st):
    bm,minstrength,minmacro,minhtf,micro,maxchase,fam=p
    s=st[r['date']]; b=s['breadth']; side=r['side']
    if r['profileStrength']<minstrength or r['macro']<minmacro or r['htf']<minhtf:return False
    if micro=='AGREE' and r['micro']!=0:
        if side=='BUY' and r['micro']<=0:return False
        if side=='SELL' and r['micro']>=0:return False
    if maxchase<900 and r['chase']>maxchase:return False
    if fam!='ANY' and bucket(r['family'])!=fam:return False
    if bm!='ANY':
        if b is None:return False
        align=(b>=.5 and side=='BUY') or (b<.5 and side=='SELL')
        if bm=='ALIGN' and not align:return False
        if bm=='EXTREME_ALIGN' and not (((b>=.80) and side=='BUY') or ((b<=.20) and side=='SELL')):return False
        if bm=='BULL_CONT' and not (b>=.65 and side=='BUY'):return False
        if bm=='BEAR_CONT' and not (b<=.35 and side=='SELL'):return False
        if bm=='MID' and not (.35<=b<=.65):return False
    return True

def choose(dev,st):
    best=None
    for p in candidates():
        z=[r for r in dev if passed(r,p,st)]; s=sm(z)
        if s['n']<28 or s['dates']<4:continue
        by=[]
        for d in sorted(set(r['date'] for r in z)):
            q=sm([r for r in z if r['date']==d])
            if q['n']>=4:by.append(q['wr'])
        med=statistics.median(by) if by else s['wr']; pos=sum(v>=50 for v in by)/max(1,len(by)); lb=100*wilson(s['wins'],s['n'])
        score=(lb,pos,med,s['meanR'],s['wr'],min(s['n'],140))
        if best is None or score>best[0]:best=(score,p,s,{'medianDayWR':round(med,2),'positiveDayRate':round(pos,3),'wilsonLB':round(lb,2)})
    return best

def by_family(rows):
    out={}
    for f in sorted(set(r['family'] for r in rows)):
        z=[r for r in rows if r['family']==f]
        if z: out[f]=sm(z)
    return out

def main():
    rows=prep(extract_crypto()); dates=sorted(set(r['date'] for r in rows)); cut=len(dates)//2
    devdates=dates[:cut]; valdates=dates[cut:]
    dev=[r for r in rows if r['date'] in devdates]; val=[r for r in rows if r['date'] in valdates]
    st=states(rows);best=choose(dev,st)
    ds=[r for r in dev if best and passed(r,best[1],st)];vs=[r for r in val if best and passed(r,best[1],st)]
    out={'version':'CRYPTO V28 SEPARATE PROFILE-AWARE','providerCreditsUsed':0,
         'method':'Crypto-only continuation of V24/Apr16 ingredients. BTC/market breadth context + HTF/macro/micro + anti-chase are weighted by coin profile family. One rule frozen on chronological development half; later half untouched validation.',
         'profiles':PROFILE,'devDates':devdates,'validationDates':valdates,'baselineValidation':sm(val),
         'rule':best[1] if best else None,'development':sm(ds),'developmentRobustness':best[3] if best else None,
         'validation':sm(vs),'validationByFamily':by_family(vs),'targetMet':False,
         'hourlyManagement':'NOT_REPLAYABLE_FROM_COMMITTED_OLD_CRYPTO_DATA'}
    v=out['validation'];out['targetMet']=bool(v.get('n',0)>=20 and (v.get('wr') or 0)>=80 and 1.0<=(v.get('avgRR') or 0)<=1.5 and v.get('meanR',-9)>0)
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crypto_v28_separate.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps({k:out[k] for k in ('version','providerCreditsUsed','devDates','validationDates','baselineValidation','rule','development','developmentRobustness','validation','validationByFamily','targetMet','hourlyManagement')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
