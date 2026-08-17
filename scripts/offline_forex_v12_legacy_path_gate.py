#!/usr/bin/env python3
import json, os, math, statistics, itertools

DYN='data/blind_backtest_forex_f4_allpairs_dynamic.json'
ORG='data/blind_backtest_forex_f4.json'

def num(x,k,default=0):
    v=x.get(k,default) if isinstance(x,dict) else default
    return float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) else default

def rsummary(rows):
    if not rows:return {'n':0}
    w=sum(r['y'] for r in rows);n=len(rows)
    return {'n':n,'dates':len(set(r['date'] for r in rows)),'wins':w,'losses':n-w,'wr':round(100*w/n,2),
            'meanR':round(statistics.mean(r['targetR'] for r in rows),3),'avgRR':round(statistics.mean(r['targetRR'] for r in rows),3)}

def enrich(date,sym,side,score,adx,rsi,d6,d24,d72,rr,res,chase=None,source=''):
    if res not in ('TP','SL') or rr is None or rr<1:return None
    sg=1 if side=='BUY' else -1
    a6=sg*d6;a24=sg*d24;a72=sg*d72
    return {'date':date[:10],'symbol':sym,'side':side,'score':abs(score),'adx':adx,'rsi':rsi,'d6a':a6,'d24a':a24,'d72a':a72,
            'agree':sum(v>0 for v in (a6,a24,a72)),'shortLongGap':a6-(a24+a72)/2,'longMean':(a24+a72)/2,
            'chase':chase,'targetRR':min(rr,1.5),'y':1 if res=='TP' else 0,'targetR':min(rr,1.5) if res=='TP' else -1.0,'source':source}

def extract_dynamic():
    data=json.load(open(DYN,encoding='utf-8'));out=[];seen=set()
    def walk(x):
        if isinstance(x,dict):
            f=x.get('feature');m=x.get('market');cut=x.get('cutoff')
            if isinstance(f,dict) and isinstance(m,dict) and isinstance(cut,str):
                res=str(m.get('result','')).upper();sym=str(f.get('symbol','')).upper();side=str(f.get('side','')).upper()
                key=(cut,sym,num(f,'entry'),res)
                if sym and side in ('BUY','SELL') and key not in seen:
                    seen.add(key);r=enrich(cut,sym,side,num(f,'score'),num(f,'adx'),num(f,'rsi',50),num(f,'d6'),num(f,'d24'),num(f,'d72'),num(f,'rr',None),res,num(f,'chaseATR',None),'F4_DYNAMIC')
                    if r:out.append(r)
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(data);return out

def extract_original():
    data=json.load(open(ORG,encoding='utf-8'));dates=[str(x)[:10] for x in data.get('method',{}).get('validationDates',[])];out=[];seen=set()
    def walk(x):
        if isinstance(x,dict):
            ts=x.get('trades')
            if isinstance(ts,list) and dates:
                for i,t in enumerate(ts):
                    if not isinstance(t,dict) or i>=len(dates):continue
                    m=t.get('market');
                    if not isinstance(m,dict):continue
                    sym=str(t.get('symbol','')).upper();side=str(t.get('side','')).upper();res=str(m.get('result','')).upper();rr=num(m,'plannedRR',None)
                    key=(dates[i],sym,num(t,'entry'),res)
                    if sym and side in ('BUY','SELL') and key not in seen:
                        seen.add(key);r=enrich(dates[i],sym,side,num(t,'score'),num(t,'h1ADX'),num(t,'h1RSI',50),num(t,'d6Strength'),num(t,'d24Strength'),num(t,'d72Strength'),rr,res,None,'F4_ORIGINAL')
                        if r:out.append(r)
            for k,v in x.items():
                if k!='trades':walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(data);return out

def candidates():
    return itertools.product(('ANY','BUY','SELL'),(0,1.5,2.5,3.5,4.5),(0,15,20,25,30),(1,2,3),(-99,-.25,0,.15,.3),(-99,-.25,0,.15,.3),(-99,-.25,0,.15,.3),(999,.4,.7,1.0,1.5),('ANY','RSI_NOT_EXTREME','RSI_SIDE'))

def passed(r,p,allow_missing_chase=False):
    side,score,adx,agree,d6,d24,d72,maxchase,rsimode=p
    if side!='ANY' and r['side']!=side:return False
    if r['score']<score or r['adx']<adx or r['agree']<agree or r['d6a']<d6 or r['d24a']<d24 or r['d72a']<d72:return False
    if maxchase<900:
        if r['chase'] is None:
            if not allow_missing_chase:return False
        elif r['chase']>maxchase:return False
    if rsimode=='RSI_NOT_EXTREME' and not (25<=r['rsi']<=75):return False
    if rsimode=='RSI_SIDE':
        if r['side']=='BUY' and r['rsi']<45:return False
        if r['side']=='SELL' and r['rsi']>55:return False
    return True

def dayrob(rows):
    vals=[]
    for d in sorted(set(r['date'] for r in rows)):
        s=rsummary([r for r in rows if r['date']==d]);
        if s['n']>=3:vals.append(s['wr'])
    return (statistics.median(vals) if vals else 0,sum(x>=50 for x in vals)/len(vals) if vals else 0)

def choose(train,common_only=False):
    best=None
    for p in candidates():
        if common_only and p[7]<900:continue
        z=[r for r in train if passed(r,p)];s=rsummary(z)
        if s['n']<15 or s['dates']<2:continue
        med,pos=dayrob(z);score=(1 if s['wr']>=80 else 0,pos,med,s['wr'],s['meanR'],min(s['n'],40))
        if best is None or score>best[0]:best=(score,p,s)
    return best

def main():
    dyn=extract_dynamic();org=extract_original();dd=sorted(set(r['date'] for r in dyn));train_dates=dd[:3]
    train=[r for r in dyn if r['date'] in train_dates]
    best_common=choose(train,True);best_chase=choose(train,False)
    # Truly later/outside training dates. Avoid double counting Jul20 dynamic vs original by using original on its five validation dates + dynamic Jul28 only.
    org_val=org
    dyn_future=[r for r in dyn if r['date']=='2026-07-28']
    common_external=org_val+dyn_future
    p=best_common[1] if best_common else None;external=[r for r in common_external if p and passed(r,p,allow_missing_chase=True)]
    # Chase rule can only be validated on dynamic Jul20/Jul28 where chase exists.
    pc=best_chase[1] if best_chase else None;dyn_val=[r for r in dyn if r['date'] in dd[3:]];chase_val=[r for r in dyn_val if pc and passed(r,pc)]
    out={'version':'FOREX V12 LEGACY PATH QUALITY GATE','providerCreditsUsed':0,
      'method':'Forex-only path-quality confirmation using older committed F4 trade-level data. Development is first 3 F4-dynamic dates only. Common multi-horizon/ADX/RSI gate is then frozen and checked on F4-original validation dates plus Jul28 dynamic; chase-aware variant checked separately on later dynamic dates.',
      'developmentDates':train_dates,'dynamicRows':len(dyn),'originalRows':len(org),
      'commonRule':p,'commonDevelopment':best_common[2] if best_common else None,'commonExternalValidation':rsummary(external),
      'commonExternalByDate':{d:rsummary([r for r in external if r['date']==d]) for d in sorted(set(r['date'] for r in external))},
      'chaseRule':pc,'chaseDevelopment':best_chase[2] if best_chase else None,'chaseDynamicValidation':rsummary(chase_val),
      'targetMet':False}
    v=out['commonExternalValidation'];out['targetMet']=bool(v.get('n',0)>=20 and v.get('dates',0)>=4 and v.get('wr',0)>=80 and 1<=v.get('avgRR',0)<=1.5 and v.get('meanR',-9)>0)
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_forex_v12_legacy_path_gate.json','w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()
