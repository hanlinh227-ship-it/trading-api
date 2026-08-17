#!/usr/bin/env python3
import json, os, re, statistics, itertools
from collections import defaultdict

FX_FILES=[
 'data/blind_backtest_forex_f4.json','data/blind_backtest_forex_f4_allpairs_dynamic.json',
 'data/blind_backtest_forex_f5_horizon.json','data/blind_backtest_forex_f6.json',
 'data/blind_backtest_forex_f6_dual_horizon.json','data/blind_backtest_forex_f8.json',
 'data/blind_backtest_forex_f8_holdout2.json','data/blind_backtest_forex_f10_loo.json',
 'data/blind_backtest_forex_f11_day_conflict.json']
CR_FILES=['data/blind_backtest_v24_validation.json','data/blind_backtest_v26.json','data/blind_backtest_v27_final.json','data/final_market_vs_limit_blind.json']
PAIR_SET={"EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD","EURJPY","EURGBP","EURCHF","EURAUD","EURNZD","EURCAD","GBPJPY","GBPCHF","GBPAUD","GBPNZD","GBPCAD","AUDJPY","AUDNZD","AUDCAD","AUDCHF","NZDJPY","NZDCAD","NZDCHF","CADJPY","CADCHF","CHFJPY"}
DATE_RE=re.compile(r'20\d\d-\d\d-\d\d')

def num(d,k,default=None):
    if not isinstance(d,dict): return default
    v=d.get(k,default)
    return float(v) if isinstance(v,(int,float)) and not isinstance(v,bool) else default

def dateof(x):
    if not isinstance(x,str): return None
    m=DATE_RE.search(x); return m.group(0) if m else None

def walk(x,path='',ctx=None):
    ctx=dict(ctx or {})
    if isinstance(x,dict):
        for k in ('cutoff','signalTime','entryTime','date'):
            d=dateof(x.get(k));
            if d: ctx['date']=d; break
        s=x.get('symbol') or x.get('pair')
        if isinstance(s,str): ctx['symbol']=s.replace('/','').upper()
        side=x.get('side') or x.get('decision')
        if isinstance(side,str): ctx['side']=side.upper()
        yield path,x,ctx
        for k,v in x.items():
            c=dict(ctx); kd=dateof(str(k))
            if kd: c['date']=kd
            yield from walk(v,path+'/'+str(k),c)
    elif isinstance(x,list):
        for i,v in enumerate(x): yield from walk(v,path+f'/{i}',ctx)

def result_of(d):
    if not isinstance(d,dict): return None
    o=d.get('outcome')
    if isinstance(o,dict): r=o.get('result') or o.get('status')
    elif isinstance(o,str): r=o
    else: r=d.get('result') or d.get('status')
    return str(r).upper() if r else None

def rr_of(d,parent=None):
    for src in (d,parent or {}):
        for k in ('rr','plannedRR','effectiveRR','avgRR'):
            v=num(src,k)
            if v is not None:return v
    return None

def classify_r(res,rr):
    if res in ('TP','WIN','TARGET'): return rr if rr is not None else 1.0
    if res in ('SL','LOSS','STOP'): return -1.0
    return None

def extract_fx():
    rows=[];seen=set()
    for fn in FX_FILES:
        if not os.path.exists(fn): continue
        data=json.load(open(fn,encoding='utf-8'))
        for path,d,ctx in walk(data):
            if not isinstance(d,dict):continue
            sym=ctx.get('symbol')
            if sym not in PAIR_SET or not ctx.get('date'):continue
            m=d.get('market') if isinstance(d.get('market'),dict) else None
            if m is None and result_of(d) and any(k in d for k in ('entry','sl','tp','rr','plannedRR')):m=d
            if not isinstance(m,dict):continue
            res=result_of(m); rr=rr_of(m,d); rv=classify_r(res,rr)
            if rv is None or rr is None:continue
            # keep only trade-like records, avoid summaries
            if not any(k in d for k in ('entry','score','mode','impulseEvidence','regimeEvidence','sl','tp')) and not any(k in m for k in ('entry','sl','tp')):continue
            key=(fn,ctx['date'],sym,ctx.get('side'),num(m,'entry',num(d,'entry')),res)
            if key in seen:continue
            seen.add(key)
            side=ctx.get('side') or d.get('side') or ''
            h1=num(d,'h1',0) or 0; h4=num(d,'h4',0) or 0
            rows.append({
              'file':fn,'date':ctx['date'],'symbol':sym,'side':str(side).upper(),'r':rv,'rr':rr,
              'score':abs(num(d,'score',0) or 0),'adx':num(d,'adx',0) or 0,'rsi':num(d,'rsi',50) or 50,
              'dev':abs(num(d,'dev',0) or 0),'fq3':abs(num(d,'fq3',0) or 0),'fq24':abs(num(d,'fq24',0) or 0),
              'coh3':num(d,'coh3',0) or 0,'coh24':num(d,'coh24',0) or 0,
              'impulse':num(d,'impulseEvidence',0) or 0,'regimeEv':num(d,'regimeEvidence',0) or 0,
              'h1':h1,'h4':h4,'mode':str(d.get('mode','')).upper(),'group':str(d.get('group','')),
              'session':abs(num(d,'sessionRet',0) or 0),
              'hourlyAvailable': isinstance(d.get('hourlyReviews'),list) and len(d.get('hourlyReviews'))>0
            })
    return rows

def extract_crypto():
    rows=[];seen=set()
    for fn in CR_FILES:
        if not os.path.exists(fn):continue
        data=json.load(open(fn,encoding='utf-8'))
        # inherit top-level breadth when present
        top_breadth=num(data,'priceBreadth')
        for path,d,ctx in walk(data):
            if not isinstance(d,dict):continue
            sym=ctx.get('symbol'); dt=ctx.get('date')
            if not sym or not sym.endswith('USDT') or not dt:continue
            m=d.get('market') if isinstance(d.get('market'),dict) else None
            if m is None and result_of(d) and any(k in d for k in ('entry','sl','tp','rr','plannedRR')):m=d
            if not isinstance(m,dict):continue
            res=result_of(m); rr=rr_of(m,d); rv=classify_r(res,rr)
            if rv is None or rr is None:continue
            entry=num(m,'entry',num(d,'entry'))
            key=(fn,dt,sym,ctx.get('side'),entry,res)
            if key in seen:continue
            seen.add(key)
            model=d.get('model') if isinstance(d.get('model'),dict) else {}
            breadth=num(d,'priceBreadth',num(m,'priceBreadth',top_breadth))
            rows.append({
              'file':fn,'date':dt,'symbol':sym,'side':str(ctx.get('side') or d.get('side') or d.get('decision') or '').upper(),
              'r':rv,'rr':rr,'score':abs(num(d,'score',num(d,'macroScore',0)) or 0),
              'macro':abs(num(d,'macroScore',0) or 0),'micro':num(d,'microScore',0) or 0,
              'htf':abs(num(model,'htfScore',0) or 0),'chase':abs(num(model,'chaseAdjustment',0) or 0),
              'breadth':breadth,'regime':str(model.get('regime') or d.get('marketRegime') or d.get('modelRegime') or 'unknown').lower(),
              'hourlyAvailable': isinstance(d.get('hourlyReviews'),list) and len(d.get('hourlyReviews'))>0
            })
    return rows

def summary(rows):
    if not rows:return {'n':0}
    wins=sum(r['r']>0 for r in rows); losses=sum(r['r']<0 for r in rows); n=wins+losses
    return {'n':len(rows),'dates':len(set(r['date'] for r in rows)),'wins':wins,'losses':losses,
            'wr':round(100*wins/n,2) if n else None,'meanR':round(statistics.mean(r['r'] for r in rows),3),
            'avgRR':round(statistics.mean(r['rr'] for r in rows),3),
            'hourlyReplayable':sum(r.get('hourlyAvailable') for r in rows)}

# ---------- selective entry gates; pre-outcome only ----------
def fx_candidates():
    for p in itertools.product((0,0.5,1,1.5,2.5),(0,15,20,25),(0,0.35,0.55,0.75),(0,0.35,0.55,0.75),(0,2,3,4),(0,3,4),(0,0.6,1.0),('ANY','IMPULSE_3H','REGIME_24H')):
        yield p

def fx_pass(r,p):
    sc,adx,c3,c24,imp,reg,dev,mode=p
    if not 1.0<=r['rr']<=1.5:return False
    if r['score']<sc or r['adx']<adx or r['coh3']<c3 or r['coh24']<c24:return False
    if r['impulse']<imp or r['regimeEv']<reg or r['dev']>dev and dev>0:return False
    if mode!='ANY' and r['mode']!=mode:return False
    return True

def cr_candidates():
    for p in itertools.product(('ANY','ALIGN','BULL70','BULL85','BEAR30','BEAR15'),('ANY','BUY','SELL'),(0,1,2.5,4),(0,2,4,6),(0,3,6,10),('ANY','trend','transition','range'),('ANY','AGREE')):
        yield p

def cr_pass(r,p):
    bm,sm,sc,ma,ht,rg,mm=p
    if not 1.0<=r['rr']<=1.5:return False
    b=r.get('breadth'); side=r['side']
    if bm!='ANY':
        if b is None:return False
        if bm=='ALIGN' and ((b>=.5 and side!='BUY') or (b<.5 and side!='SELL')):return False
        if bm=='BULL70' and b<.70:return False
        if bm=='BULL85' and b<.85:return False
        if bm=='BEAR30' and b>.30:return False
        if bm=='BEAR15' and b>.15:return False
    if sm!='ANY' and side!=sm:return False
    if r['score']<sc or r['macro']<ma or r['htf']<ht:return False
    if rg!='ANY' and r['regime']!=rg:return False
    if mm=='AGREE' and r['micro']!=0:
        if side=='BUY' and r['micro']<=0:return False
        if side=='SELL' and r['micro']>=0:return False
    return True

def pick_rule(train,cands,passfn,min_n,min_dates):
    best=None
    for p in cands():
        sel=[r for r in train if passfn(r,p)]
        sm=summary(sel)
        if sm['n']<min_n or sm['dates']<min_dates:continue
        # robustness first: target 80, then expectancy, then sample; never use current holdout
        score=(1 if sm['wr']>=80 else 0, sm['wr'], sm['meanR'], min(sm['n'],200))
        if best is None or score>best[0]:best=(score,p,sm)
    return best

def walk_forward(rows,cands,passfn,warmup=5,min_n=25,min_dates=3):
    dates=sorted(set(r['date'] for r in rows)); out=[]; detail={}
    for i,d in enumerate(dates):
        day=[r for r in rows if r['date']==d]
        if i<warmup:
            detail[d]={'warmup':True,'all':summary(day),'selected':{'n':0}};continue
        train=[r for r in rows if r['date']<d]
        best=pick_rule(train,cands,passfn,min_n,min_dates)
        sel=[r for r in day if best and passfn(r,best[1])]
        out+=sel
        detail[d]={'warmup':False,'rule':best[1] if best else None,'train':best[2] if best else None,'all':summary(day),'selected':summary(sel)}
    return summary(out),detail

def insample(rows,cands,passfn,min_n=40,min_dates=4):
    b=pick_rule(rows,cands,passfn,min_n,min_dates)
    return {'rule':b[1] if b else None,'performance':b[2] if b else None,'status':'DIAGNOSTIC_ONLY'}

def main():
    fx=extract_fx(); cr=extract_crypto()
    fxwf,fxd=walk_forward(fx,fx_candidates,fx_pass,warmup=5,min_n=30,min_dates=3)
    crwf,crd=walk_forward(cr,cr_candidates,cr_pass,warmup=4,min_n=25,min_dates=3)
    out={'version':'CROSSMARKET ROLLING BLIND V4','providerCreditsUsed':0,
         'integrity':{'entryFiltersPreOutcomeOnly':True,'chronologicalWalkForward':True,'rrPromotionBand':[1.0,1.5],
                      'hourlyHoldCutRequiresStoredHourlySnapshots':True,'noOracleHourlyCuts':True},
         'FOREX':{'all':summary(fx),'walkForwardEntrySelected':fxwf,'inSampleCeiling':insample(fx,fx_candidates,fx_pass),'byDate':fxd},
         'CRYPTO':{'all':summary(cr),'walkForwardEntrySelected':crwf,'inSampleCeiling':insample(cr,cr_candidates,cr_pass),'byDate':crd}}
    for k in ('FOREX','CRYPTO'):
        s=out[k]['walkForwardEntrySelected']
        out[k]['hourlyManagementValidationAvailable']=s.get('hourlyReplayable',0)>0
        out[k]['targetMet']=bool(s.get('n',0)>=20 and (s.get('wr') or 0)>=80 and 1.0<=(s.get('avgRR') or 0)<=1.5 and out[k]['hourlyManagementValidationAvailable'])
    out['promotion']={k:('PASS' if out[k]['targetMet'] else 'NOT_YET') for k in ('FOREX','CRYPTO')}
    os.makedirs('data',exist_ok=True)
    json.dump(out,open('data/offline_crossmarket_rolling_blind_v4.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps({'providerCreditsUsed':0,'FOREX':{'all':out['FOREX']['all'],'walkForward':fxwf,'inSample':out['FOREX']['inSampleCeiling'],'targetMet':out['FOREX']['targetMet']},'CRYPTO':{'all':out['CRYPTO']['all'],'walkForward':crwf,'inSample':out['CRYPTO']['inSampleCeiling'],'targetMet':out['CRYPTO']['targetMet']}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
