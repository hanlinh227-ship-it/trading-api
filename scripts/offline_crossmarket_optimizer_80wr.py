#!/usr/bin/env python3
import json, os, re, statistics, itertools, math
from collections import defaultdict

PAIR_SET={
"EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
"EURJPY","EURGBP","EURCHF","EURAUD","EURNZD","EURCAD","GBPJPY",
"GBPCHF","GBPAUD","GBPNZD","GBPCAD","AUDJPY","AUDNZD","AUDCAD",
"AUDCHF","NZDJPY","NZDCAD","NZDCHF","CADJPY","CADCHF","CHFJPY"}
FOREX_FILES=[
 'data/blind_backtest_forex_f8.json',
 'data/blind_backtest_forex_f8_holdout2.json',
 'data/blind_backtest_forex_f10_loo.json',
 'data/blind_backtest_forex_f11_day_conflict.json',
]
CRYPTO_FILES=[
 'data/blind_backtest_v24_validation.json',
 'data/blind_backtest_v26.json',
 'data/blind_backtest_v27_final.json',
 'data/final_market_vs_limit_blind.json',
]
DATE_RE=re.compile(r'20\d\d-\d\d-\d\d')

def n(x,k,default=None):
    if not isinstance(x,dict): return default
    v=x.get(k,default)
    return v if isinstance(v,(int,float)) and not isinstance(v,bool) else default

def first_date(x):
    if isinstance(x,str):
        m=DATE_RE.search(x)
        return m.group(0) if m else None
    return None

def walk(x,path='',ctx=None):
    ctx=dict(ctx or {})
    if isinstance(x,dict):
        # only historical/event fields; never generatedAt
        for k in ('cutoff','signalTime','entryTime','date'):
            d=first_date(x.get(k))
            if d: ctx['date']=d; break
        sym=x.get('symbol') or x.get('pair')
        if isinstance(sym,str): ctx['symbol']=sym.replace('/','').upper()
        side=x.get('side') or x.get('decision')
        if isinstance(side,str): ctx['side']=side.upper()
        yield path,x,ctx
        for k,v in x.items():
            c=dict(ctx)
            kd=first_date(str(k))
            if kd: c['date']=kd
            yield from walk(v,path+'/'+str(k),c)
    elif isinstance(x,list):
        for i,v in enumerate(x): yield from walk(v,path+f'/{i}',ctx)

def outcome_result(m):
    if not isinstance(m,dict): return None
    o=m.get('outcome')
    if isinstance(o,dict): return (o.get('result') or o.get('status') or '').upper()
    if isinstance(o,str): return o.upper()
    r=m.get('result')
    return r.upper() if isinstance(r,str) else None

def rr_of(m):
    if not isinstance(m,dict): return None
    for k in ('rr','plannedRR','effectiveRR','avgPlannedRR','medianPlannedRR','avgEffectiveRR','avgRR'):
        v=n(m,k)
        if v is not None: return float(v)
    return None

def r_value(m,is_limit=False):
    if not isinstance(m,dict): return None
    res=outcome_result(m) or (m.get('status','').upper() if isinstance(m.get('status'),str) else '')
    if res in ('TP','WIN','TARGET'): return rr_of(m) or 1.0
    if res in ('SL','LOSS','STOP'): return -1.0
    if is_limit and (res in ('NO_FILL','NOT_FILLED','TARGET_BEFORE_FILL','CANCELLED') or m.get('filled') is False): return 0.0
    return None

# ---------- FOREX ----------
def table_score(path,table,fn):
    p=path.lower(); keys=[k for k in table if k in PAIR_SET]
    s=10 if len(keys)>=20 else -100
    for bad in ('development','pairmodelselection','selection','candidate','models'):
        if bad in p:s-=15
    for good in ('validation','holdout','bypair','bysymbol','baseline','recommended','f8'):
        if good in p:s+=2
    # F10 file should expose frozen F8 comparator, not LOO candidate.
    if 'f10_loo' in fn:
        if 'f8' in p or 'baseline' in p:s+=8
        if 'loo' in p:s-=5
    # F11 selectedThreshold=null => validation is frozen F8; prefer validation/f8.
    if 'f11_day_conflict' in fn:
        if 'validation' in p or 'f8' in p:s+=6
        if 'development' in p:s-=10
    return s

def extract_forex_table(fn):
    if not os.path.exists(fn): return None,None
    data=json.load(open(fn,encoding='utf-8'))
    cand=[]
    for path,d,_ in walk(data):
        if not isinstance(d,dict):continue
        keys=[k for k in d if k in PAIR_SET]
        if len(keys)<20:continue
        valid=sum(isinstance(d[k],dict) and isinstance(d[k].get('market'),dict) for k in keys)
        if valid<20:continue
        cand.append((table_score(path,d,fn),path,d))
    if not cand:return None,None
    cand.sort(key=lambda z:(z[0],-len(z[1])),reverse=True)
    return cand[0][1],cand[0][2]

def fx_entry(sym,d,source):
    m=d.get('market',{})
    wins=n(m,'wins'); losses=n(m,'losses'); resolved=n(m,'resolved')
    if resolved is None and wins is not None and losses is not None: resolved=wins+losses
    wr=n(m,'winRateResolved')
    if wr is None and resolved and wins is not None: wr=100*wins/resolved
    exp=n(m,'expectancyR')
    rr=rr_of(m)
    dirs=[]
    for k in ('direction3','direction6','direction8','direction12','direction24','chosenDirection','dir12','dir24'):
        v=d.get(k)
        if isinstance(v,dict):
            a=n(v,'accuracy')
            if a is not None:dirs.append(a)
    return {'symbol':sym,'source':source,'wins':wins or 0,'losses':losses or 0,'resolved':resolved or 0,
            'wr':wr,'exp':exp,'rr':rr,'dir':statistics.mean(dirs) if dirs else None}

def fx_summarize(obs):
    obs=[x for x in obs if x.get('exp') is not None]
    if not obs:return {'nPairs':0}
    wins=sum(x['wins'] for x in obs); losses=sum(x['losses'] for x in obs); resolved=wins+losses
    exps=[]
    for x in obs:
        w=max(1,x['resolved']); exps += [x['exp']]*w
    rrs=[x['rr'] for x in obs if x.get('rr') is not None]
    return {'nPairs':len(obs),'resolved':resolved,'wins':wins,'losses':losses,
            'winRateResolved':round(100*wins/resolved,2) if resolved else None,
            'meanExpectancyR':round(statistics.mean(exps),3) if exps else None,
            'avgRR':round(statistics.mean(rrs),3) if rrs else None}

def fx_prior_stats(pair,train_sources,blocks):
    xs=[blocks[s].get(pair) for s in train_sources if blocks.get(s) and blocks[s].get(pair)]
    xs=[x for x in xs if x.get('exp') is not None]
    if not xs:return None
    exps=[x['exp'] for x in xs]; wrs=[x['wr'] for x in xs if x.get('wr') is not None]
    dirs=[x['dir'] for x in xs if x.get('dir') is not None]; rrs=[x['rr'] for x in xs if x.get('rr') is not None]
    return {'n':len(xs),'meanExp':statistics.mean(exps),'posRate':sum(e>0 for e in exps)/len(exps),
            'meanWR':statistics.mean(wrs) if wrs else None,'meanDir':statistics.mean(dirs) if dirs else None,
            'meanRR':statistics.mean(rrs) if rrs else None}

def fx_params():
    for pos,exp,wr,dr,rr in itertools.product(
        (0.34,0.5,0.67,1.0),(-0.05,0.0,0.05,0.15,0.30),(35,40,45,50,55,60),(0,50,55,60,65,70),(1.0,1.2,1.5)):
        yield (pos,exp,wr,dr,rr)

def fx_pass(st,p):
    if not st:return False
    pos,exp,wr,dr,rr=p
    if st['n']<2:return False
    if st['posRate']<pos or st['meanExp']<exp:return False
    if st['meanWR'] is not None and st['meanWR']<wr:return False
    if dr and (st['meanDir'] is None or st['meanDir']<dr):return False
    if st['meanRR'] is not None and st['meanRR']<rr:return False
    return True

def fx_inner_score(param,train_sources,blocks):
    held=[]
    for h in train_sources:
        tr=[s for s in train_sources if s!=h]
        for pair in PAIR_SET:
            st=fx_prior_stats(pair,tr,blocks)
            if fx_pass(st,param) and pair in blocks[h]:held.append(blocks[h][pair])
    sm=fx_summarize(held)
    if sm.get('resolved',0)<20 or sm.get('nPairs',0)<5:return None
    if sm.get('avgRR') is not None and sm['avgRR']<1.0:return None
    return sm

def run_forex():
    blocks={}; paths={}
    for fn in FOREX_FILES:
        path,t=extract_forex_table(fn)
        if not t:continue
        paths[fn]=path; blocks[fn]={}
        for pair in PAIR_SET:
            d=t.get(pair)
            if isinstance(d,dict) and isinstance(d.get('market'),dict):blocks[fn][pair]=fx_entry(pair,d,fn)
    sources=list(blocks)
    baseline=[]; qualified=[]; folds={}; chosen=[]
    for outer in sources:
        train=[s for s in sources if s!=outer]
        best=None
        for p in fx_params():
            sm=fx_inner_score(p,train,blocks)
            if not sm:continue
            # target 80% first; then expectancy; avoid trivial tiny sample.
            wr=sm.get('winRateResolved') or 0; ex=sm.get('meanExpectancyR') or -9; cnt=sm.get('resolved',0)
            score=((1 if wr>=80 else 0),wr,ex,min(cnt,100))
            if best is None or score>best[0]:best=(score,p,sm)
        base=list(blocks[outer].values()); baseline+=base
        q=[]
        if best:
            for pair in PAIR_SET:
                st=fx_prior_stats(pair,train,blocks)
                if fx_pass(st,best[1]) and pair in blocks[outer]:q.append(blocks[outer][pair])
        qualified+=q
        folds[outer]={'tablePath':paths.get(outer),'chosenParam':best[1] if best else None,
                      'innerCV':best[2] if best else None,'baseline':fx_summarize(base),'heldoutQualified':fx_summarize(q)}
        if best:chosen.append(best[1])
    return {'sources':sources,'tablePaths':paths,'baselineAll':fx_summarize(baseline),
            'nestedHeldoutQualified':fx_summarize(qualified),'folds':folds,
            'targetMet':bool(qualified and (fx_summarize(qualified).get('winRateResolved') or 0)>=80 and (fx_summarize(qualified).get('avgRR') or 0)>=1.0),
            'note':'Nested leave-one-block: threshold set chosen only from inner CV of remaining blocks; outer block excluded.'}

# ---------- CRYPTO ----------
def extract_crypto_rows():
    rows=[];seen=set()
    for fn in CRYPTO_FILES:
        if not os.path.exists(fn):continue
        data=json.load(open(fn,encoding='utf-8'))
        for path,d,ctx in walk(data):
            if not isinstance(d,dict):continue
            sym=ctx.get('symbol');date=ctx.get('date')
            if not sym or not sym.endswith('USDT') or not date:continue
            # canonical trade record either contains market outcome or is itself market trade.
            m=d.get('market') if isinstance(d.get('market'),dict) else None
            if m is None and outcome_result(d) and any(k in d for k in ('entry','sl','tp','plannedRR','rr')):m=d
            if not isinstance(m,dict):continue
            rv=r_value(m)
            if rv is None:continue
            side=ctx.get('side') or d.get('side') or d.get('decision') or ''
            score=n(d,'score',n(d,'macroScore',0.0)) or 0.0
            macro=n(d,'macroScore',score) or 0.0
            micro=n(d,'microScore',0.0) or 0.0
            breadth=n(d,'priceBreadth')
            if breadth is None:
                # ancestors often hold breadth; ctx does not carry numeric state, so infer from model if copied.
                breadth=n(m,'priceBreadth')
            regime=d.get('marketRegime') or d.get('modelRegime')
            model=d.get('model') if isinstance(d.get('model'),dict) else {}
            modelreg=model.get('regime') if isinstance(model.get('regime'),str) else regime
            htf=n(model,'htfScore',0.0) or 0.0
            chase=n(model,'chaseAdjustment',0.0) or 0.0
            rr=rr_of(m) or n(d,'plannedRR') or 1.0
            entry=n(m,'entry',n(d,'entry'))
            key=(fn,date,sym,side,entry,rv)
            if key in seen:continue
            seen.add(key)
            rows.append({'file':fn,'date':date,'symbol':sym,'side':str(side).upper(),'r':rv,'rr':float(rr),
                         'score':float(score),'macro':float(macro),'micro':float(micro),'breadth':breadth,
                         'regime':str(modelreg or regime or 'unknown').lower(),'htf':float(htf),'chase':float(chase)})
    return rows

def crypto_summary(rows):
    if not rows:return {'n':0}
    vals=[r['r'] for r in rows];wins=sum(x>0 for x in vals);losses=sum(x<0 for x in vals);resolved=wins+losses
    rrs=[r['rr'] for r in rows]
    dates=len(set(r['date'] for r in rows))
    return {'n':len(rows),'dates':dates,'resolved':resolved,'wins':wins,'losses':losses,
            'winRateResolved':round(100*wins/resolved,2) if resolved else None,
            'meanR':round(statistics.mean(vals),3),'avgRR':round(statistics.mean(rrs),3) if rrs else None}

def crypto_candidates():
    # Interpretable pre-outcome gates only. No MFE/MAE/direction/outcome-derived fields.
    breadth_modes=['ANY','BULL55','BULL70','BULL80','BULL90','BEAR45','BEAR30','BEAR20','BEAR10','EXTREME','ALIGN']
    side_modes=['ANY','BUY','SELL','BREADTH_ALIGN']
    scoremins=[0,0.75,1.5,2.5,3.5]
    macromins=[0,1.5,3.0,5.0]
    htfmins=[0,3,6,10]
    regimes=['ANY','trend','transition','range']
    micro_modes=['ANY','AGREE']
    for x in itertools.product(breadth_modes,side_modes,scoremins,macromins,htfmins,regimes,micro_modes):yield x

def crypto_pass(r,p):
    bm,sm,smin,mmin,hmin,rg,mm=p
    b=r.get('breadth');side=r.get('side','')
    if bm!='ANY':
        if b is None:return False
        if bm=='BULL55' and b<.55:return False
        if bm=='BULL70' and b<.70:return False
        if bm=='BULL80' and b<.80:return False
        if bm=='BULL90' and b<.90:return False
        if bm=='BEAR45' and b>.45:return False
        if bm=='BEAR30' and b>.30:return False
        if bm=='BEAR20' and b>.20:return False
        if bm=='BEAR10' and b>.10:return False
        if bm=='EXTREME' and not (b>=.80 or b<=.20):return False
        if bm=='ALIGN':
            if b>=.5 and side!='BUY':return False
            if b<.5 and side!='SELL':return False
    if sm=='BUY' and side!='BUY':return False
    if sm=='SELL' and side!='SELL':return False
    if sm=='BREADTH_ALIGN':
        if b is None:return False
        if b>=.5 and side!='BUY':return False
        if b<.5 and side!='SELL':return False
    if abs(r['score'])<smin or abs(r['macro'])<mmin or abs(r['htf'])<hmin:return False
    if rg!='ANY' and r['regime']!=rg:return False
    if mm=='AGREE' and r['micro']!=0:
        if side=='BUY' and r['micro']<=0:return False
        if side=='SELL' and r['micro']>=0:return False
    return True

def best_crypto_rule(train,minimum=20):
    best=None
    for p in crypto_candidates():
        sel=[r for r in train if crypto_pass(r,p)]
        sm=crypto_summary(sel)
        if sm.get('resolved',0)<minimum or sm.get('dates',0)<2:continue
        if (sm.get('avgRR') or 0)<1.0:continue
        wr=sm.get('winRateResolved') or 0;ex=sm.get('meanR') or -9;ntr=sm.get('resolved',0)
        # valid preference: hit 80 with enough observations first, then robustness/expectancy/sample.
        score=((1 if wr>=80 else 0),wr,ex,min(ntr,150))
        if best is None or score>best[0]:best=(score,p,sm)
    return best

def run_crypto():
    rows=extract_crypto_rows();dates=sorted(set(r['date'] for r in rows))
    wf=[];bydate={};rules=[]
    # 3-date warmup. Rule for each date sees only earlier dates.
    for i,date in enumerate(dates):
        day=[r for r in rows if r['date']==date]
        if i<3:
            bydate[date]={'warmup':True,'all':crypto_summary(day),'selected':{'n':0}}
            continue
        train=[r for r in rows if r['date']<date]
        best=best_crypto_rule(train,minimum=max(20,min(50,int(len(train)*.05))))
        sel=[r for r in day if best and crypto_pass(r,best[1])]
        wf+=sel
        bydate[date]={'warmup':False,'all':crypto_summary(day),'chosenRule':best[1] if best else None,
                      'trainPerformance':best[2] if best else None,'selected':crypto_summary(sel)}
        if best:rules.append(best[1])
    # In-sample ceiling is diagnostic only and never promotable.
    ins=best_crypto_rule(rows,minimum=max(40,int(len(rows)*.08)))
    wfs=crypto_summary(wf)
    return {'rows':len(rows),'dates':dates,'all':crypto_summary(rows),'walkForwardSelected':wfs,
            'inSampleCeiling':{'rule':ins[1] if ins else None,'performance':ins[2] if ins else None,'status':'DIAGNOSTIC_ONLY_NOT_VALIDATION'},
            'byDate':bydate,'targetMet':bool((wfs.get('winRateResolved') or 0)>=80 and (wfs.get('avgRR') or 0)>=1.0 and wfs.get('resolved',0)>=20),
            'note':'Chronological walk-forward after 3-date warmup. Each date rule is chosen only from earlier dates.'}

def main():
    out={'version':'CROSSMARKET 80WR OFFLINE OPTIMIZER V1','providerCreditsUsed':0,
         'constraints':{'targetWinRate':80.0,'minimumAvgRR':1.0,'preferredAvgRR':1.5,'noProviderCalls':True,
                        'noOutcomeDerivedEntryFeatures':True,'noHindsightPromotion':True},
         'FOREX':run_forex(),'CRYPTO':run_crypto()}
    out['promotion']={
      'FOREX':'PASS' if out['FOREX']['targetMet'] else 'FAIL_DO_NOT_FORCE_80',
      'CRYPTO':'PASS' if out['CRYPTO']['targetMet'] else 'FAIL_DO_NOT_FORCE_80',
      'rule':'Only held-out/walk-forward >=80% with avgRR>=1.0 and non-trivial sample may be promoted. In-sample 80% is rejected.'
    }
    os.makedirs('data',exist_ok=True)
    with open('data/offline_crossmarket_optimizer_80wr.json','w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
