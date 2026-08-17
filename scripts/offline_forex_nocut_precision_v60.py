#!/usr/bin/env python3
import json, math, statistics
from collections import defaultdict
from pathlib import Path
import scripts.offline_forex_precision_evolver_v15 as b
import scripts.offline_forex_daily_per_symbol_v18 as old

OUT='data/offline_forex_nocut_precision_v60.json'
TARGET=80.0
MIN_TRADES=12
WINDOWS=old.WINDOWS
DIRS=old.DIRS
FAMS=('FAST','BALANCED','TREND','SESSION','REVERT','QUALITY','BREAKOUT','PULLBACK')
CFGS=[(rr,rf,sw) for rr in (1.0,2.0) for rf in (.75,1.0,1.25,1.5,2.0) for sw in (4,8,12)]
CCY_DRIVERS={
 'USD':['Fed/FOMC','US CPI/PCE/NFP','US10Y and DXY','Treasury/liquidity conditions'],
 'EUR':['ECB','Eurozone CPI/PMI','Germany growth/industrial data','EU political/fiscal risk'],
 'GBP':['BoE','UK CPI/wages/jobs','UK GDP/retail sales','UK fiscal/political risk'],
 'JPY':['BoJ','MoF intervention risk','Tokyo/Japan CPI','JGB yields and global risk sentiment'],
 'CHF':['SNB','Swiss CPI','safe-haven flows','European risk sentiment'],
 'CAD':['BoC','Canada CPI/jobs/GDP','WTI crude oil','US-Canada growth differential'],
 'AUD':['RBA','Australia CPI/jobs','China PMIs/growth','iron ore and risk sentiment'],
 'NZD':['RBNZ','New Zealand CPI/jobs','China growth','dairy/commodity risk sentiment'],
}

def hscore(x,f):
    a=x['meta'];side=x['side'];g3=a['g3']*side;g6=a['g6']*side;g12=a['g12']*side;g24=a['g24']*side;g72=a['g72']*side
    h1=a['h1']*side;h4=a['h4']*side;mom=a['mom']*side;dev=a['dev']*side;sess=a['sess']*side;coh=(a['coh3']+a['coh24'])/2
    if f=='FAST':return 1.8*g3+1.2*g6+.5*g12+.8*coh+.5*h1+.25*mom
    if f=='BALANCED':return 1.2*g3+g6+.8*g12+.8*g24+.3*g72+.8*coh+.45*h1+.35*h4
    if f=='TREND':return .8*g24+.5*g72+1.2*h1+1.0*h4+.7*mom+.4*sess-.2*max(dev-1.5,0)
    if f=='SESSION':return 1.0*g3+.6*g6+1.0*mom+1.1*sess+.6*h1+.3*coh
    if f=='REVERT':return .7*g24+.4*g72-1.25*dev+.6*h4+.4*coh-.2*mom
    if f=='QUALITY':return 1.0*coh+.8*h1+.7*h4+.45*g24+.25*g72-.55*abs(dev)+.15*sess
    if f=='BREAKOUT':return 1.25*g6+1.05*g12+.9*mom+.7*h1+.45*coh-.25*max(abs(dev)-1.8,0)
    if f=='PULLBACK':return .8*g24+.55*g72+.75*h4-.95*dev+.55*coh-.25*mom
    return g3+g6+g12+g24

def exec_nocut(rows,i,side,cfg):
    rr,rf,sw=cfg
    if i+1>=len(rows) or rows[i].get('atr') is None:return None
    sig=rows[i];atr=sig['atr'];ei=i+1;entry=rows[ei]['open'];recent=rows[max(0,i-sw+1):i+1]
    swing=min(x['low'] for x in recent) if side==1 else max(x['high'] for x in recent)
    struct=entry-swing if side==1 else swing-entry
    risk=max(rf*atr,struct+.05*atr,.25*atr)
    sl=entry-side*risk;tp=entry+side*rr*risk
    for j in range(ei,len(rows)):
        x=rows[j];hs=x['low']<=sl if side==1 else x['high']>=sl;ht=x['high']>=tp if side==1 else x['low']<=tp
        if hs and ht:return ('SL',-1.0,j-ei+1)
        if hs:return ('SL',-1.0,j-ei+1)
        if ht:return ('TP',rr,j-ei+1)
    return ('UNRESOLVED',0.0,len(rows)-ei)

def select_weekly(raw,window,direction,fam,per_week):
    g=defaultdict(list)
    for x in raw:
        if x['time'].hour not in WINDOWS[window]:continue
        if direction=='BUY' and x['side']!=1:continue
        if direction=='SELL' and x['side']!=-1:continue
        q=dict(x);q['score']=hscore(q,fam);iso=q['time'].isocalendar();g[(iso.year,iso.week)].append(q)
    out=[]
    for _,z in sorted(g.items()):
        z=sorted(z,key=lambda q:q['score'],reverse=True);used=set()
        for q in z:
            if q['day'] in used:continue
            out.append(q);used.add(q['day'])
            if len(used)>=per_week:break
    return out

def stat(sel,cache,cfg):
    z=[]
    for e in sel:
        o=cache[(cfg,e['i'],e['side'])];z.append(o)
    tp=sum(x[0]=='TP' for x in z);sl=sum(x[0]=='SL' for x in z);un=sum(x[0]=='UNRESOLVED' for x in z);n=len(z)
    wr=100*tp/n if n else 0
    resolved=tp+sl
    rr=cfg[0]
    mean=(tp*rr-sl)/n if n else -9
    return {'trades':n,'tp':tp,'sl':sl,'unresolved':un,'wrAllSelected':round(wr,2),'resolved':resolved,'meanRAllSelected':round(mean,3),'avgBarsToTerminal':round(statistics.mean(x[2] for x in z),1) if z else 0}

def rank(s):
    hit=s['trades']>=MIN_TRADES and s['wrAllSelected']>=TARGET and s['meanRAllSelected']>0
    return (int(hit),s['wrAllSelected']-max(0,MIN_TRADES-s['trades'])*8,s['meanRAllSelected'],-s['unresolved'],s['trades'])

def style(sym,fam,w,d,cfg):
    a=sym[:3];c=sym[3:]
    return {'styleId':f'{sym}_V60_{fam}_{w}_{d}_RR{int(cfg[0])}_RF{cfg[1]}_SW{cfg[2]}','family':fam,'window':w,'direction':d,'rr':cfg[0],'riskFloorATR':cfg[1],'swingHours':cfg[2],'pairCurrencies':[a,c],'macroNewsDrivers':{a:CCY_DRIVERS[a],c:CCY_DRIVERS[c]},'liveNewsRule':'Before live entry, refresh point-in-time calendar/headlines for both currencies; high-impact surprise may veto or change direction. Historical V60 does not fabricate unavailable news data.'}

def main():
    doc=json.load(open(b.SNAP,encoding='utf-8'));data={s:b.enrich(doc['data'][s]) for s in b.PAIRS};maps,times=b.make_maps(data);raw=old.raw_candidates(data,maps,times);results={}
    for sym in b.PAIRS:
        r=[x for x in raw[sym] if '2026-05-01'<=x['day']<='2026-07-31']
        keys={(e['i'],e['side']) for e in r};cache={}
        for cfg in CFGS:
            for i,side in keys:cache[(cfg,i,side)]=exec_nocut(data[sym],i,side,cfg)
        best=None;bp=None
        for fam in FAMS:
          for w in WINDOWS:
            for d in DIRS:
              for pw in (1,2):
                sel=select_weekly(r,w,d,fam,pw)
                if len(sel)<MIN_TRADES:continue
                for cfg in CFGS:
                    s=stat(sel,cache,cfg);q=rank(s)
                    if best is None or q>best:best=q;bp=(fam,w,d,pw,cfg,s)
        if bp is None:
            results[sym]={'status':'FAIL','reason':'insufficient candidates'};print('FAIL',sym,'NO_CANDIDATES',flush=True);continue
        fam,w,d,pw,cfg,s=bp;ok=bool(rank(s)[0])
        results[sym]={'status':'PASS' if ok else 'FAIL','selector':{'entriesPerISOWeek':pw},'style':style(sym,fam,w,d,cfg),'mayJulyDevelopment':s}
        print('PASS' if ok else 'FAIL',sym,results[sym]['style']['styleId'],s,flush=True)
    passed=[s for s in b.PAIRS if results[s]['status']=='PASS'];failed=[s for s in b.PAIRS if results[s]['status']!='PASS']
    ans={'version':'FOREX_NOCUT_PRECISION_V60','scope':'May-Jul exposed development search for live precision entry; no CUT, only TP/SL/UNRESOLVED','definition':{'cutUsed':False,'rrAllowed':[1.0,2.0],'minimumSelectedTrades':MIN_TRADES,'wr':'TP / all selected trades (SL and UNRESOLVED both non-wins)','sameBarTPandSL':'SL conservative','newsBacktestUsed':False},'passCount':len(passed),'failCount':len(failed),'passed':passed,'failed':failed,'allPassed':not failed,'results':results}
    Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(ans,open(OUT,'w'),indent=2);print('SUMMARY',json.dumps({k:ans[k] for k in ('passCount','failCount','failed','allPassed')},indent=2),flush=True)
if __name__=='__main__':main()
