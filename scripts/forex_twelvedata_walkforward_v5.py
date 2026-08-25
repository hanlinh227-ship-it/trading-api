#!/usr/bin/env python3
"""PAPER_ONLY multi-method Forex walk-forward research engine.
Reuses the tested V4 data/features/outcome/KNN primitives, but replaces strategy selection.
Hard coverage rule: every valid OOS day must contain at least one entry per symbol.
"""
import ast,json,math,os,random,time
from pathlib import Path
from datetime import datetime,timedelta,timezone
from collections import defaultdict

BASE=Path(__file__).with_name('forex_twelvedata_walkforward_v4.py')
OUT='data/forex-twelvedata-walkforward-latest.json'
KEY=os.environ.get('TWELVEDATA_API_KEY','').strip()
if not KEY: raise SystemExit('TWELVEDATA_API_KEY missing')
SYMS=['EUR/USD','GBP/USD','USD/JPY','USD/CHF','AUD/USD','NZD/USD','USD/CAD','EUR/JPY','GBP/JPY','EUR/GBP','XAU/USD']
RRS=(1,2); STOPS=(0.8,1.0,1.2,1.5,1.8,2.2)
SEED=int(os.environ.get('BACKTEST_SEED') or random.SystemRandom().randrange(1,2**31-1)); RNG=random.Random(SEED)
WINDOWS=int(os.environ.get('BACKTEST_WINDOWS','6')); DAYS=int(os.environ.get('BACKTEST_WINDOW_DAYS','24'))
MIN_TRADES=int(os.environ.get('BACKTEST_MIN_TEST_DAYS','18')); TARGET=float(os.environ.get('BACKTEST_TARGET_WR','80'))
SOURCE_SHA=os.environ.get('GITHUB_SHA',''); MODE=os.environ.get('FOREX_RESEARCH_MODE','ACCEPTANCE').upper()
START=datetime.fromisoformat(os.environ.get('BACKTEST_START','2025-01-06')).replace(tzinfo=timezone.utc)
END=datetime.fromisoformat(os.environ.get('BACKTEST_END','2026-07-31')).replace(tzinfo=timezone.utc)
ALLOWED={'TREND_CONTINUATION','MOMENTUM_BREAKOUT','PULLBACK_TREND','MEAN_REVERSION','HYBRID_REGIME'}
DEFAULT_CELL={'method':'TREND_CONTINUATION','minProb':0.72,'minLocal':0.82,'sessions':[6,7,8,9,10,12,13,14,15,16],'stopMin':0.8,'stopMax':2.2,'trendMin':0.06,'momentumMin':0.02,'extensionMax':1.35}

def load_v4_primitives():
    tree=ast.parse(BASE.read_text())
    keep=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef))]
    ns={}; exec(compile(ast.Module(body=keep,type_ignores=[]),str(BASE),'exec'),ns)
    ns.update({'KEY':KEY,'OUT':OUT,'SYMS':SYMS,'SEED':SEED,'RNG':RNG,'WINDOWS':WINDOWS,'DAYS':DAYS,'MIN_TRADES':MIN_TRADES,'TARGET':TARGET,
               'SOURCE_SHA':SOURCE_SHA,'START':START,'END':END,'HOURS':DEFAULT_CELL['sessions'],'STOPS':STOPS,'RRS':RRS,
               'MIN_PROB':{1:.72,2:.72},'MIN_LOCAL':{1:.82,2:.82}})
    return ns
N=load_v4_primitives()
fetch,enrich,day_groups,features,outcome,samples_for_day,predict,metrics=N['fetch'],N['enrich'],N['day_groups'],N['features'],N['outcome'],N['samples_for_day'],N['predict'],N['metrics']

def profile():
    raw=os.environ.get('FOREX_STRATEGY_PROFILE_JSON','').strip()
    if not raw:return {'defaults':{'1':dict(DEFAULT_CELL),'2':dict(DEFAULT_CELL)},'symbols':{}}
    return json.loads(raw)
PROFILE=profile()

def cell(sym,rr):
    key=sym.replace('/',''); c=dict(DEFAULT_CELL)
    c.update((PROFILE.get('defaults') or {}).get(str(rr)) or {})
    c.update((((PROFILE.get('symbols') or {}).get(key) or {}).get(str(rr)) or {}))
    c['method']=str(c.get('method','TREND_CONTINUATION')).upper()
    if c['method'] not in ALLOWED: raise ValueError('invalid method '+c['method'])
    c['sessions']=[int(h) for h in c.get('sessions',DEFAULT_CELL['sessions']) if 0<=int(h)<=23]
    c['minProb']=min(.96,max(.50,float(c.get('minProb',.72)))); c['minLocal']=min(1,max(.50,float(c.get('minLocal',.82))))
    c['stopMin']=max(.6,float(c.get('stopMin',.8))); c['stopMax']=min(3.0,float(c.get('stopMax',2.2)))
    c['trendMin']=min(.6,max(-.2,float(c.get('trendMin',.06)))); c['momentumMin']=min(.8,max(-.5,float(c.get('momentumMin',.02))))
    c['extensionMax']=min(3,max(.3,float(c.get('extensionMax',1.35))))
    return c

def method_ok(x,c,rr):
    t1,t2,m3,m12,m36,rsi,ext,pos,vol,body,bar=x[:11]; method=c['method']; tm=c['trendMin']; mm=c['momentumMin']; em=c['extensionMax']
    trend=(t1>tm and t2>tm*.55 and m12>mm and rsi>0)
    breakout=(m3>max(mm,.05) and m12>max(mm,.05) and bar>.22 and pos>.10 and ext<em)
    pullback=(t1>tm and t2>tm*.45 and -0.55<ext<0.30 and m3>-0.18 and rsi>-0.12)
    meanrev=(ext<-0.38 and rsi<-0.18 and pos<-.15 and abs(t1)<.55 and m3>-0.35)
    if rr==2: trend=trend and t1+t2>max(.16,tm*2.2); breakout=breakout and m12>.08
    if method=='TREND_CONTINUATION': return trend and abs(ext)<em
    if method=='MOMENTUM_BREAKOUT': return breakout
    if method=='PULLBACK_TREND': return pullback
    if method=='MEAN_REVERSION': return meanrev
    return (trend or breakout) if vol>.22 else (pullback or meanrev)

def quality(x,pr,local,c,rr):
    edge=pr*(rr+1)-1; m=c['method']
    if m=='TREND_CONTINUATION': return edge+.08*x[0]+.08*x[1]+.04*x[3]-.02*abs(x[6])+.03*local
    if m=='MOMENTUM_BREAKOUT': return edge+.10*x[2]+.08*x[3]+.05*x[10]+.03*x[7]+.02*local
    if m=='PULLBACK_TREND': return edge+.08*x[0]+.07*x[1]-.04*abs(x[6]+.15)+.03*x[2]+.03*local
    if m=='MEAN_REVERSION': return edge-.07*x[6]-.05*x[5]-.04*x[7]+.02*local
    return edge+.04*x[0]+.04*x[2]+.03*x[3]-.02*abs(x[6])+.03*local

def make_trade(rows,i,side,stop,rr,c,pr,local,q,forced=False,reason=None):
    y,r,mfe,mae,why=outcome(rows,i,side,stop,rr); e=rows[i]
    return {'day':e['t'].date().isoformat(),'entry_time':e['t'].isoformat(),'side':'BUY' if side>0 else 'SELL','rr':rr,'method':c['method'],'stopAtr':stop,
            'predictedWinProb':round(pr,4),'localConsensus':round(local,4),'quality':round(q,4),'forcedDaily':bool(forced),'forcedReason':reason,
            'result':'WIN' if y else 'LOSS','r':r,'mfeR':round(mfe,3),'maeR':round(mae,3),'exitReason':why}

def choose(rows,train,sym,rr):
    c=cell(sym,rr); cand=[]
    for h in c['sessions']:
        i=N['idx_for_hour'](rows,h)
        if i is None: continue
        for side in (-1,1):
            for stop in STOPS:
                if not (c['stopMin']<=stop<=c['stopMax']): continue
                x=features(rows,i,side,stop,rr)
                if not method_ok(x,c,rr): continue
                pr,local,n=predict(x,train); q=quality(x,pr,local,c,rr); cand.append((q,pr,local,n,i,side,stop,x,c))
    if not cand:return None,'NO_METHOD_CANDIDATE'
    q,pr,local,n,i,side,stop,x,c=max(cand,key=lambda z:z[0])
    if pr<c['minProb'] or local<c['minLocal']:return None,f'CONFIDENCE_GATE pr={pr:.3f} local={local:.3f}'
    return make_trade(rows,i,side,stop,rr,c,pr,local,q),None

def force_daily_entry(rows,train,sym):
    """Pre-outcome deterministic fallback: guarantee >=1 entry per valid OOS day.
    It may relax method/confidence gates, but never inspects the outcome before selection.
    """
    cand=[]
    for rr in RRS:
        c=cell(sym,rr)
        hours=c['sessions'] or DEFAULT_CELL['sessions']
        for h in hours:
            i=N['idx_for_hour'](rows,h)
            if i is None: continue
            for side in (-1,1):
                for stop in STOPS:
                    if not (c['stopMin']<=stop<=c['stopMax']): continue
                    x=features(rows,i,side,stop,rr); pr,local,n=predict(x,train)
                    q=quality(x,pr,local,c,rr)
                    # Penalty for breaking the preferred method gate, but never use outcome.
                    if not method_ok(x,c,rr): q-=0.18
                    cand.append((q,pr,local,n,i,side,stop,rr,c))
    if not cand:return None
    q,pr,local,n,i,side,stop,rr,c=max(cand,key=lambda z:z[0])
    return make_trade(rows,i,side,stop,rr,c,pr,local,q,forced=True,reason='DAILY_MIN_ENTRY_FALLBACK')

def random_windows():
    span=(END-START).days-DAYS; chosen=[]
    for _ in range(30000):
        if len(chosen)>=WINDOWS:break
        a=START+timedelta(days=RNG.randint(0,max(1,span))); b=a+timedelta(days=DAYS)
        if any(not (b<=x or a>=y) for x,y in chosen):continue
        chosen.append((a,b))
    if len(chosen)<WINDOWS:raise RuntimeError('cannot sample non-overlapping windows')
    return sorted(chosen)

windows=random_windows(); report={'version':'FOREX-TWELVEDATA-WALKFORWARD-5-MULTI-METHOD-DAILY-ENTRY','mode':MODE,'sourceSha':SOURCE_SHA,'seed':SEED,'generatedAt':datetime.now(timezone.utc).isoformat(),
 'strategyProfile':PROFILE,'rules':{'source':'Twelve Data 5min','noLookahead':True,'methods':sorted(ALLOWED),'allowNoTradePerRR':True,'minimumEntriesPerSymbolPerValidOOSDay':1,
 'dailyFallbackPreOutcome':True,'sameBarSLTP':'SL_FIRST_PESSIMISTIC','timeouts':'LOSS','targetWinrateStrictlyGreaterThan':TARGET,'minimumTradesPerSymbolRR':MIN_TRADES,
 'antiCherryPick':'method/session/filter and any daily fallback are selected before outcome; every trade, forcedDaily flag, window and failed round persisted'},
 'windows':[{'start':a.isoformat(),'end':b.isoformat()} for a,b in windows],'symbols':{},'pass':False}
allpass=True
for sym in SYMS:
    trades=[]; src=[]; err=None; total_test_days=0; days_with_entry=0; forced_days=0
    try:
        for wi,(a,b) in enumerate(windows):
            rows=enrich(fetch(sym,a,b)); g=day_groups(rows); days=sorted(g); cut=max(3,int(len(days)*.60)); tr=days[:cut]; te=days[cut:]; train=[]
            for d in tr: train.extend(samples_for_day(g[d]))
            wt=[]; abst={'1':0,'2':0}; reasons=defaultdict(int); window_days_with_entry=0; window_forced=0
            for d in te:
                total_test_days+=1; day_trades=[]
                for rr in RRS:
                    t,why=choose(g[d],train,sym,rr)
                    if t:trades.append(t); wt.append(t); day_trades.append(t)
                    else:abst[str(rr)]+=1; reasons[why]+=1
                if not day_trades:
                    ft=force_daily_entry(g[d],train,sym)
                    if ft is None: raise RuntimeError(f'{sym} {d}: DAILY_ENTRY_UNAVAILABLE')
                    trades.append(ft); wt.append(ft); day_trades.append(ft); forced_days+=1; window_forced+=1
                if day_trades: days_with_entry+=1; window_days_with_entry+=1
                train.extend(samples_for_day(g[d]))
            src.append({'window':wi,'trainDays':len(tr),'testDays':len(te),'daysWithEntry':window_days_with_entry,'forcedDailyDays':window_forced,
                        'dailyEntryCoveragePct':round(100*window_days_with_entry/len(te),2) if te else 0,'abstentionsByRR':abst,'abstentionReasons':dict(reasons),
                        'testMetrics':{'RR1':metrics([x for x in wt if x['rr']==1]),'RR2':metrics([x for x in wt if x['rr']==2])}})
            time.sleep(float(os.environ.get('TWELVEDATA_INTER_REQUEST_SLEEP','8.2')))
    except Exception as e:err=str(e)
    by={str(rr):metrics([x for x in trades if x['rr']==rr]) for rr in RRS}
    daily_cov=round(100*days_with_entry/total_test_days,2) if total_test_days else 0
    daily_pass=(err is None and total_test_days>0 and days_with_entry==total_test_days)
    rp={str(rr):(err is None and by[str(rr)]['trades']>=MIN_TRADES and by[str(rr)]['winrate']>TARGET and by[str(rr)]['avgR']>0) for rr in RRS}
    passed=daily_pass and all(rp.values()); allpass &= passed
    report['symbols'][sym.replace('/','')]={'pass':passed,'rrPass':rp,'dailyEntryPass':daily_pass,'validOOSTestDays':total_test_days,'daysWithEntry':days_with_entry,
        'dailyEntryCoveragePct':daily_cov,'forcedDailyDays':forced_days,'holdout':{'all':metrics(trades),'byRR':by},'activeProfiles':{'1':cell(sym,1),'2':cell(sym,2)},'source':src,'dataError':err,'trades':trades}
    print(sym,by,'dailyCoverage',daily_cov,'forcedDays',forced_days,'PASS' if passed else 'FAIL',err or '',flush=True)
    os.makedirs('data',exist_ok=True); json.dump(report,open(OUT,'w'),indent=2)
report['pass']=allpass; json.dump(report,open(OUT,'w'),indent=2); print('FINAL_PASS',allpass,'seed',SEED)
