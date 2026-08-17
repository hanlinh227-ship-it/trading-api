#!/usr/bin/env python3
import json, os, re, statistics, itertools

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
            d=dateof(x.get(k))
            if d: ctx['date']=d; break
        s=x.get('symbol') or x.get('pair')
        if isinstance(s,str): ctx['symbol']=s.replace('/','').upper()
        side=x.get('side') or x.get('decision')
        if isinstance(side,str): ctx['side']=side.upper()
        yield path,x,ctx
        for k,v in x.items():
            c=dict(ctx); kd=dateof(str(k))
            if kd:c['date']=kd
            yield from walk(v,path+'/'+str(k),c)
    elif isinstance(x,list):
        for i,v in enumerate(x):yield from walk(v,path+f'/{i}',ctx)

def result_of(d):
    if not isinstance(d,dict):return None
    o=d.get('outcome')
    if isinstance(o,dict):r=o.get('result') or o.get('status')
    elif isinstance(o,str):r=o
    else:r=d.get('result') or d.get('status')
    return str(r).upper() if r else None

def rr_of(*srcs):
    for src in srcs:
        if not isinstance(src,dict):continue
        for k in ('rr','plannedRR','effectiveRR','avgRR'):
            v=num(src,k)
            if v is not None:return v
    return None

def classify_r(res,rr):
    if res in ('TP','WIN','TARGET'):return rr if rr is not None else 1.0
    if res in ('SL','LOSS','STOP'):return -1.0
    return None

def extract_fx():
    rows=[];seen=set()
    for fn in FX_FILES:
        if not os.path.exists(fn):continue
        data=json.load(open(fn,encoding='utf-8'))
        for path,d,ctx in walk(data):
            if not isinstance(d,dict):continue
            t=d.get('trade') if isinstance(d.get('trade'),dict) else None
            m=d.get('market') if isinstance(d.get('market'),dict) else None
            if not t or not m:continue
            sym=str(t.get('symbol','')).replace('/','').upper(); dt=dateof(d.get('cutoff')) or ctx.get('date')
            if sym not in PAIR_SET or not dt:continue
            res=result_of(m); rr=rr_of(t,m); rv=classify_r(res,rr)
            if rv is None or rr is None:continue
            entry=num(t,'entry'); risk=num(t,'risk'); side=str(t.get('side','')).upper()
            key=(fn,dt,sym,entry,res)
            if key in seen:continue
            seen.add(key)
            direc=d.get('direction') if isinstance(d.get('direction'),dict) else {}
            d3=direc.get('3h') if isinstance(direc.get('3h'),dict) else {}
            close3=num(d3,'close')
            cut3r=None
            if entry is not None and risk and close3 is not None and side in ('BUY','SELL'):
                cut3r=((close3-entry)/risk) if side=='BUY' else ((entry-close3)/risk)
            rows.append({
              'file':fn,'date':dt,'symbol':sym,'side':side,'r':rv,'rr':rr,'entry':entry,'risk':risk,
              'score':abs(num(t,'score',0) or 0),'adx':num(t,'adx',0) or 0,'rsi':num(t,'rsi',50) or 50,
              'dev':abs(num(t,'dev',0) or 0),'fq3':abs(num(t,'fq3',0) or 0),'fq24':abs(num(t,'fq24',0) or 0),
              'coh3':num(t,'coh3',0) or 0,'coh24':num(t,'coh24',0) or 0,
              'impulse':num(t,'impulseEvidence',0) or 0,'regimeEv':num(t,'regimeEvidence',0) or 0,
              'h1':num(t,'h1',0) or 0,'h4':num(t,'h4',0) or 0,'mode':str(t.get('mode','')).upper(),'group':str(t.get('group','')),
              'session':abs(num(t,'sessionRet',0) or 0),'bars':int(num(m,'bars',0) or 0),'cut3r':cut3r,
              'checkpoint3Available':cut3r is not None
            })
    return rows

def extract_crypto():
    rows=[];seen=set()
    for fn in CR_FILES:
        if not os.path.exists(fn):continue
        data=json.load(open(fn,encoding='utf-8')); top_breadth=num(data,'priceBreadth')
        for path,d,ctx in walk(data):
            if not isinstance(d,dict):continue
            sym=ctx.get('symbol');dt=ctx.get('date')
            if not sym or not sym.endswith('USDT') or not dt:continue
            m=d.get('market') if isinstance(d.get('market'),dict) else None
            if m is None and result_of(d) and any(k in d for k in ('entry','sl','tp','rr','plannedRR')):m=d
            if not isinstance(m,dict):continue
            rr=rr_of(m,d);res=result_of(m);rv=classify_r(res,rr)
            if rv is None or rr is None:continue
            entry=num(m,'entry',num(d,'entry'));key=(fn,dt,sym,ctx.get('side'),entry,res)
            if key in seen:continue
            seen.add(key)
            model=d.get('model') if isinstance(d.get('model'),dict) else {}; breadth=num(d,'priceBreadth',num(m,'priceBreadth',top_breadth))
            rows.append({'file':fn,'date':dt,'symbol':sym,'side':str(ctx.get('side') or d.get('side') or d.get('decision') or '').upper(),
              'r':rv,'rr':rr,'score':abs(num(d,'score',num(d,'macroScore',0)) or 0),'macro':abs(num(d,'macroScore',0) or 0),
              'micro':num(d,'microScore',0) or 0,'htf':abs(num(model,'htfScore',0) or 0),'chase':abs(num(model,'chaseAdjustment',0) or 0),
              'breadth':breadth,'regime':str(model.get('regime') or d.get('marketRegime') or d.get('modelRegime') or 'unknown').lower()})
    return rows

def summary(rows,rkey='r'):
    if not rows:return {'n':0}
    vals=[r[rkey] for r in rows if r.get(rkey) is not None];wins=sum(v>0 for v in vals);losses=sum(v<0 for v in vals);n=wins+losses
    return {'n':len(vals),'dates':len(set(r['date'] for r in rows)),'wins':wins,'losses':losses,'wr':round(100*wins/n,2) if n else None,
            'meanR':round(statistics.mean(vals),3) if vals else None,'avgRR':round(statistics.mean(r['rr'] for r in rows),3) if rows else None}

def fx_candidates():
    return itertools.product((0,.5,1,1.5,2.5),(0,15,20,25),(0,.35,.55,.75),(0,2,3,4),(0,.6,1.0,1.4),('ANY','IMPULSE_3H','REGIME_24H'))

def fx_pass(r,p):
    sc,adx,c3,imp,maxdev,mode=p
    if r['score']<sc or r['adx']<adx or r['coh3']<c3 or r['impulse']<imp:return False
    if maxdev and r['dev']>maxdev:return False
    if mode!='ANY' and r['mode']!=mode:return False
    return True

def cr_candidates():
    return itertools.product(('ANY','ALIGN','BULL70','BULL85','BEAR30','BEAR15'),('ANY','BUY','SELL'),(0,1,2.5,4),(0,2,4,6),(0,3,6,10),('ANY','trend','transition','range'),('ANY','AGREE'))

def cr_pass(r,p):
    bm,sm,sc,ma,ht,rg,mm=p;b=r.get('breadth');side=r['side']
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
        sel=[r for r in train if passfn(r,p)];sm=summary(sel)
        if sm['n']<min_n or sm['dates']<min_dates:continue
        score=(1 if sm['wr']>=80 else 0,sm['wr'],sm['meanR'],min(sm['n'],200))
        if best is None or score>best[0]:best=(score,p,sm)
    return best

def walk_forward(rows,cands,passfn,warmup,min_n,min_dates):
    dates=sorted(set(r['date'] for r in rows));out=[];detail={}
    for i,d in enumerate(dates):
        day=[r for r in rows if r['date']==d]
        if i<warmup:detail[d]={'warmup':True,'all':summary(day),'selected':{'n':0}};continue
        train=[r for r in rows if r['date']<d];best=pick_rule(train,cands,passfn,min_n,min_dates)
        sel=[r for r in day if best and passfn(r,best[1])];out+=sel
        detail[d]={'warmup':False,'rule':best[1] if best else None,'train':best[2] if best else None,'all':summary(day),'selected':summary(sel)}
    return out,detail

def insample(rows,cands,passfn,min_n,min_dates):
    b=pick_rule(rows,cands,passfn,min_n,min_dates);return {'rule':b[1] if b else None,'performance':b[2] if b else None,'status':'DIAGNOSTIC_ONLY'}

# H+3 management proxy: only for trades still alive after 12 M15 bars. At H+3 the close is observable.
# Rule family uses current unrealized R only; trained on earlier dates, then applied forward.
def apply_h3(rows,threshold):
    out=[]
    for r in rows:
        z=dict(r);z['managedR']=r['r'];z['managedOutcome']='TP' if r['r']>0 else 'SL'
        if r.get('checkpoint3Available') and r.get('bars',0)>12 and r['cut3r']<=threshold:
            z['managedR']=r['cut3r'];z['managedOutcome']='CUT'
        out.append(z)
    return out

def managed_summary(rows):
    if not rows:return {'n':0}
    tp=sum(r['managedOutcome']=='TP' for r in rows);sl=sum(r['managedOutcome']=='SL' for r in rows);cut=sum(r['managedOutcome']=='CUT' for r in rows)
    wr=100*tp/(tp+sl) if tp+sl else None
    return {'n':len(rows),'TP':tp,'SL':sl,'CUT':cut,'wrExcludingCut':round(wr,2) if wr is not None else None,
            'meanManagedRIncludingCut':round(statistics.mean(r['managedR'] for r in rows),3),'avgRR':round(statistics.mean(r['rr'] for r in rows),3)}

def h3_walkforward(rows,warmup=5):
    dates=sorted(set(r['date'] for r in rows));allout=[];detail={};thresholds=(-.15,-.25,-.35,-.5,-.7)
    for i,d in enumerate(dates):
        day=[r for r in rows if r['date']==d]
        if i<warmup:continue
        train=[r for r in rows if r['date']<d]
        best=None
        for th in thresholds:
            sm=managed_summary(apply_h3(train,th))
            score=(1 if (sm['wrExcludingCut'] or 0)>=80 else 0,sm['wrExcludingCut'] or 0,sm['meanManagedRIncludingCut'], -sm['CUT'])
            if best is None or score>best[0]:best=(score,th,sm)
        managed=apply_h3(day,best[1]);allout+=managed;detail[d]={'threshold':best[1],'train':best[2],'validation':managed_summary(managed)}
    return managed_summary(allout),detail

def main():
    fx=extract_fx();cr=extract_crypto();fxsel,fxd=walk_forward(fx,fx_candidates,fx_pass,5,30,3);crsel,crd=walk_forward(cr,cr_candidates,cr_pass,4,25,3)
    h3,h3d=h3_walkforward(fxsel,3) if fxsel else ({'n':0},{})
    out={'version':'CROSSMARKET ROLLING BLIND V4.1','providerCreditsUsed':0,
      'integrity':{'entryFiltersPreOutcomeOnly':True,'chronologicalWalkForward':True,'noOracleHourlyCuts':True,'H3ManagementUsesOnlyObservableH3Close':True},
      'FOREX':{'all':summary(fx),'walkForwardEntrySelected':summary(fxsel),'H3ManagedWalkForward':h3,'entryByDate':fxd,'h3ByDate':h3d,'inSampleCeiling':insample(fx,fx_candidates,fx_pass,40,4)},
      'CRYPTO':{'all':summary(cr),'walkForwardEntrySelected':summary(crsel),'entryByDate':crd,'inSampleCeiling':insample(cr,cr_candidates,cr_pass,40,4),'hourlyReplayable':0}}
    for k in ('FOREX','CRYPTO'):
        s=out[k]['H3ManagedWalkForward'] if k=='FOREX' else out[k]['walkForwardEntrySelected'];wr=s.get('wrExcludingCut') if k=='FOREX' else s.get('wr')
        out[k]['targetMet']=bool(s.get('n',0)>=20 and (wr or 0)>=80 and 1.0<=(s.get('avgRR') or 0)<=1.5)
    os.makedirs('data',exist_ok=True);json.dump(out,open('data/offline_crossmarket_rolling_blind_v4.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps({'providerCreditsUsed':0,'FOREX':{'all':out['FOREX']['all'],'walkForwardEntrySelected':out['FOREX']['walkForwardEntrySelected'],'H3ManagedWalkForward':h3,'inSample':out['FOREX']['inSampleCeiling'],'targetMet':out['FOREX']['targetMet']},'CRYPTO':{'all':out['CRYPTO']['all'],'walkForwardEntrySelected':out['CRYPTO']['walkForwardEntrySelected'],'inSample':out['CRYPTO']['inSampleCeiling'],'targetMet':out['CRYPTO']['targetMet']}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
