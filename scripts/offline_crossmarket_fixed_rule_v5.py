#!/usr/bin/env python3
import json, os, math, statistics, itertools
from scripts.offline_crossmarket_rolling_blind_v4 import extract_fx, extract_crypto

def target_r(r):
    # Conservative remap into requested RR band: original winner at RR>1.5 necessarily crossed 1.5 first.
    # Original loser remains loser; never infer a TP conversion without path data.
    if r['rr'] < 1.0: return None
    tr=min(r['rr'],1.5)
    return tr if r['r']>0 else -1.0

def prep(rows):
    out=[]
    for r in rows:
        z=dict(r); z['targetRR']=min(r['rr'],1.5) if r['rr']>=1.0 else None; z['targetR']=target_r(r)
        if z['targetR'] is not None: out.append(z)
    return out

def sm(rows,key='targetR'):
    vals=[r[key] for r in rows if r.get(key) is not None]
    if not vals:return {'n':0}
    w=sum(v>0 for v in vals);l=sum(v<0 for v in vals);n=w+l
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':l,'wr':round(100*w/n,2),
            'meanR':round(statistics.mean(vals),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def wilson(w,n,z=1.2816):
    if not n:return 0
    p=w/n;den=1+z*z/n
    return (p+z*z/(2*n)-z*math.sqrt((p*(1-p)+z*z/(4*n))/n))/den

def robust(rows):
    s=sm(rows)
    if s['n']==0:return None
    by=[]
    for d in sorted(set(r['date'] for r in rows)):
        x=[r for r in rows if r['date']==d]
        if len(x)>=3:by.append(sm(x)['wr'])
    med=statistics.median(by) if by else s['wr'];pos=sum(x>=50 for x in by)/len(by) if by else 0
    return {'summary':s,'medianDayWR':round(med,2),'positiveDayRate':round(pos,3),'wilson80LB':round(100*wilson(s['wins'],s['n']),2)}

def fx_candidates():
    groups=('ANY','USD_MAJOR','JPY_CROSS','EUROPE_CROSS','COMMODITY_CROSS','MIXED_CROSS')
    for p in itertools.product(groups,('ANY','IMPULSE_3H','REGIME_24H'),('ANY','BUY','SELL'),(0,.5,1,1.5,2.5),(0,15,20,25),(0,.35,.55,.75),(0,2,3,4),(0,.6,1.0,1.4),('ANY','H1','H1H4')):
        yield p

def fxpass(r,p):
    g,mode,side,score,adx,coh,imp,maxdev,align=p
    if g!='ANY' and r['group']!=g:return False
    if mode!='ANY' and r['mode']!=mode:return False
    if side!='ANY' and r['side']!=side:return False
    if r['score']<score or r['adx']<adx or r['coh3']<coh or r['impulse']<imp:return False
    if maxdev and r['dev']>maxdev:return False
    sg=1 if r['side']=='BUY' else -1
    if align=='H1' and r['h1']!=sg:return False
    if align=='H1H4' and not (r['h1']==sg and r['h4']==sg):return False
    return True

def cr_candidates():
    for p in itertools.product(('ANY','ALIGN','BULL60','BULL70','BULL85','BEAR40','BEAR30','BEAR15'),('ANY','BUY','SELL'),(0,1,2.5,4),(0,2,4,6),(0,3,6,10),('ANY','trend','transition','range'),('ANY','AGREE')):
        yield p

def crpass(r,p):
    bm,side,score,macro,htf,rg,mm=p;b=r.get('breadth');s=r['side']
    if bm!='ANY':
        if b is None:return False
        if bm=='ALIGN' and ((b>=.5 and s!='BUY') or (b<.5 and s!='SELL')):return False
        if bm=='BULL60' and b<.60:return False
        if bm=='BULL70' and b<.70:return False
        if bm=='BULL85' and b<.85:return False
        if bm=='BEAR40' and b>.40:return False
        if bm=='BEAR30' and b>.30:return False
        if bm=='BEAR15' and b>.15:return False
    if side!='ANY' and s!=side:return False
    if r['score']<score or r['macro']<macro or r['htf']<htf:return False
    if rg!='ANY' and r['regime']!=rg:return False
    if mm=='AGREE' and r['micro']!=0:
        if s=='BUY' and r['micro']<=0:return False
        if s=='SELL' and r['micro']>=0:return False
    return True

def choose(dev,cands,fn,minn,mindates):
    best=None
    for p in cands():
        sel=[r for r in dev if fn(r,p)]
        if len(sel)<minn or len(set(r['date'] for r in sel))<mindates:continue
        rb=robust(sel);s=rb['summary']
        # one frozen rule: favor statistical lower bound, day stability, expectancy, then raw WR
        score=(rb['wilson80LB'],rb['positiveDayRate'],rb['medianDayWR'],s['meanR'],s['wr'],min(s['n'],200))
        if best is None or score>best[0]:best=(score,p,rb)
    return best

def split_test(rows,cands,fn,dev_frac,minn,mindates):
    dates=sorted(set(r['date'] for r in rows));cut=max(mindates,int(len(dates)*dev_frac));devdates=dates[:cut];valdates=dates[cut:]
    dev=[r for r in rows if r['date'] in devdates];val=[r for r in rows if r['date'] in valdates]
    best=choose(dev,cands,fn,minn,mindates)
    ds=[r for r in dev if best and fn(r,best[1])];vs=[r for r in val if best and fn(r,best[1])]
    return {'devDates':devdates,'validationDates':valdates,'rule':best[1] if best else None,'development':robust(ds) if ds else None,'validation':robust(vs) if vs else None},vs,ds

def managed(rows,th):
    out=[]
    for r in rows:
        z=dict(r);z['managedOutcome']='TP' if r['targetR']>0 else 'SL';z['managedR']=r['targetR']
        # Only if trade survived beyond H+3 and H+3 close exists.
        if r.get('checkpoint3Available') and r.get('bars',0)>12 and r.get('cut3r') is not None and r['cut3r']<=th:
            z['managedOutcome']='CUT';z['managedR']=r['cut3r']
        out.append(z)
    return out

def msm(rows):
    if not rows:return {'n':0}
    tp=sum(r['managedOutcome']=='TP' for r in rows);sl=sum(r['managedOutcome']=='SL' for r in rows);cut=sum(r['managedOutcome']=='CUT' for r in rows)
    den=tp+sl
    return {'n':len(rows),'TP':tp,'SL':sl,'CUT':cut,'cutRate':round(100*cut/len(rows),2),'wrExcludingCut':round(100*tp/den,2) if den else None,
            'meanManagedRIncludingCut':round(statistics.mean(r['managedR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def choose_h3(dev):
    best=None
    for th in (-.1,-.2,-.3,-.4,-.5,-.6,-.75):
        x=managed(dev,th);s=msm(x)
        # prevent trivial WR inflation: at least 20 TP+SL and cut rate <=45%; expectancy matters.
        if s['TP']+s['SL']<20 or s['cutRate']>45:continue
        score=(1 if (s['wrExcludingCut'] or 0)>=80 else 0,s['wrExcludingCut'] or 0,s['meanManagedRIncludingCut'],-s['cutRate'])
        if best is None or score>best[0]:best=(score,th,s)
    return best

def main():
    fx=prep(extract_fx());cr=prep(extract_crypto())
    fxt,fxval,fxdev=split_test(fx,fx_candidates,fxpass,.5,30,3)
    crt,crval,crdev=split_test(cr,cr_candidates,crpass,.5,40,4)
    h=choose_h3(fxdev);hval=msm(managed(fxval,h[1])) if h and fxval else {'n':0}
    out={'version':'CROSSMARKET FIXED RULE V5','providerCreditsUsed':0,
         'method':'Single rule frozen on chronological development half; untouched later half validation. Original RR above 1.5 is conservatively capped to 1.5: original winners stay wins; original losers are never converted without path evidence.',
         'FOREX':{'all':sm(fx),'fixedRule':fxt,'H3Rule':{'threshold':h[1] if h else None,'development':h[2] if h else None,'validation':hval}},
         'CRYPTO':{'all':sm(cr),'fixedRule':crt,'hourlyManagement':'NOT_REPLAYABLE_FROM_COMMITTED_OLD_DATA'}}
    fw=hval.get('wrExcludingCut') if hval else None;fr=hval.get('avgRR') if hval else None
    out['FOREX']['targetMet']=bool(hval.get('n',0)>=20 and (fw or 0)>=80 and 1.0<=(fr or 0)<=1.5 and hval.get('meanManagedRIncludingCut',-9)>0)
    cv=(crt.get('validation') or {}).get('summary') if crt.get('validation') else None
    out['CRYPTO']['targetMet']=bool(cv and cv['n']>=20 and cv['wr']>=80 and 1.0<=cv['avgRR']<=1.5 and cv['meanR']>0)
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crossmarket_fixed_rule_v5.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
