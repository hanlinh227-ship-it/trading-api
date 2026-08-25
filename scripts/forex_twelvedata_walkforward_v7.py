#!/usr/bin/env python3
"""PAPER_ONLY Forex V7: 100 random OOS days + sandboxed strategy DSL.

V7 keeps the V6 acceptance contract while allowing 3AI research to invent NEW
entry/quality logic without arbitrary code execution. A CUSTOM_RULESET cell may
use safe boolean expressions over an expanded feature dictionary.

Hard invariants remain immutable: exactly 100 random OOS days/symbol, >=1 entry
per tested day, no lookahead, pessimistic same-bar SL/TP, all failures retained.
"""
import ast,json,math,os,random,time
from pathlib import Path
from datetime import datetime,timedelta,timezone

BASE=Path(__file__).with_name('forex_twelvedata_walkforward_v5.py')
OUT='data/forex-twelvedata-walkforward-latest.json'
KEY=os.environ.get('TWELVEDATA_API_KEY','').strip()
if not KEY: raise SystemExit('TWELVEDATA_API_KEY missing')
SYMS=['EUR/USD','GBP/USD','USD/JPY','USD/CHF','AUD/USD','NZD/USD','USD/CAD','EUR/JPY','GBP/JPY','EUR/GBP','XAU/USD']
RRS=(1,2); STOPS=(0.8,1.0,1.2,1.5,1.8,2.2)
SEED=int(os.environ.get('BACKTEST_SEED') or random.SystemRandom().randrange(1,2**31-1)); RNG=random.Random(SEED)
BLOCKS=int(os.environ.get('BACKTEST_RANDOM_BLOCKS','10'))
BLOCK_DAYS=int(os.environ.get('BACKTEST_BLOCK_DAYS','24'))
TEST_DAYS_PER_BLOCK=int(os.environ.get('BACKTEST_TEST_DAYS_PER_BLOCK','10'))
TRAIN_DAYS_PER_BLOCK=int(os.environ.get('BACKTEST_TRAIN_DAYS_PER_BLOCK','6'))
TARGET_DAYS=BLOCKS*TEST_DAYS_PER_BLOCK
MIN_TRADES=int(os.environ.get('BACKTEST_MIN_TEST_DAYS','18')); TARGET=float(os.environ.get('BACKTEST_TARGET_WR','80'))
SOURCE_SHA=os.environ.get('GITHUB_SHA',''); MODE=os.environ.get('FOREX_RESEARCH_MODE','ACCEPTANCE').upper()
START=datetime.fromisoformat(os.environ.get('BACKTEST_START','2025-01-06')).replace(tzinfo=timezone.utc)
END=datetime.fromisoformat(os.environ.get('BACKTEST_END','2026-07-31')).replace(tzinfo=timezone.utc)
LEGACY={'TREND_CONTINUATION','MOMENTUM_BREAKOUT','PULLBACK_TREND','MEAN_REVERSION','HYBRID_REGIME'}
ALLOWED=LEGACY|{'CUSTOM_RULESET'}
DEFAULT_CELL={'method':'TREND_CONTINUATION','minProb':0.72,'minLocal':0.82,'sessions':[6,7,8,9,10,12,13,14,15,16],
 'stopMin':0.8,'stopMax':2.2,'trendMin':0.06,'momentumMin':0.02,'extensionMax':1.35}

# Reuse tested V5/V4 primitives, but do not execute their drivers.
tree=ast.parse(BASE.read_text()); keep=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef))]
G={}; exec(compile(ast.Module(body=keep,type_ignores=[]),str(BASE),'exec'),G)
G.update({'BASE':Path(__file__).with_name('forex_twelvedata_walkforward_v4.py'),'OUT':OUT,'KEY':KEY,'SYMS':SYMS,'SEED':SEED,'RNG':RNG,
          'WINDOWS':BLOCKS,'DAYS':BLOCK_DAYS,'MIN_TRADES':MIN_TRADES,'TARGET':TARGET,'SOURCE_SHA':SOURCE_SHA,'MODE':MODE,
          'START':START,'END':END,'HOURS':DEFAULT_CELL['sessions'],'STOPS':STOPS,'RRS':RRS,'ALLOWED':ALLOWED,'DEFAULT_CELL':DEFAULT_CELL,
          'MIN_PROB':{1:.72,2:.72},'MIN_LOCAL':{1:.82,2:.82}})
N=G['load_v4_primitives'](); G['N']=N
fetch,enrich,day_groups,outcome,idx_for_hour,metrics=N['fetch'],N['enrich'],N['day_groups'],N['outcome'],N['idx_for_hour'],N['metrics']

FEATURE_NAMES=['t1','t2','m3','m12','m36','rsi','ext','pos','vol','body','bar','hourSin','hourCos','stopNorm','rrNorm',
               'ema8Slope','ema20Slope','atrRegime','compression','wickPressure','rangePosition','impulseRatio']

def features(rows,i,side,stop,rr):
    # Original 15 features, preserving legacy semantics.
    x=N['features'](rows,i,side,stop,rr)
    r=rows[i]; a=max(r['atr'],1e-12); c=r['c']
    j12=max(0,i-12); j36=max(0,i-36)
    ema8s=side*(r['e8']-rows[j12]['e8'])/a
    ema20s=side*(r['e20']-rows[j12]['e20'])/a
    recent_atr=[z['atr'] for z in rows[max(0,i-36):i+1]]
    atr_reg=min(3.0,r['atr']/max(sum(recent_atr)/max(1,len(recent_atr)),1e-12))
    r12=rows[max(0,i-12):i+1]; r36=rows[max(0,i-36):i+1]
    range12=max(z['h'] for z in r12)-min(z['l'] for z in r12)
    range36=max(z['h'] for z in r36)-min(z['l'] for z in r36)
    compression=min(3.0,range12/max(range36,1e-12)*3.0)
    upper=r['h']-max(r['o'],r['c']); lower=min(r['o'],r['c'])-r['l']
    wick=side*(lower-upper)/a
    past=rows[:i+1]; hi=max(z['h'] for z in past); lo=min(z['l'] for z in past)
    rp=((c-lo)/max(hi-lo,1e-12)-.5)*side*2
    impulse=side*(c-rows[j12]['c'])/max(range12,1e-12)
    return x+[ema8s,ema20s,atr_reg,compression,wick,rp,impulse]

# Dynamic distance makes the expanded features participate in KNN rather than
# silently being ignored by V4's fixed 15-weight zip.
DIST_WEIGHTS=[1.2,1.2,.65,.95,.8,.75,.9,.55,.25,.25,.2,.15,.15,.55,.7,.75,.65,.35,.35,.30,.45,.45]
def dist(a,b):return sum(w*(x-y)*(x-y) for w,x,y in zip(DIST_WEIGHTS,a,b))
def predict(x,train,k=25):
    ds=sorted(((dist(x,z['x']),z['y']) for z in train),key=lambda q:q[0])[:min(k,len(train))]
    if not ds:return .5,.5,0
    num=1.5;den=3.0
    for d,y in ds:
        w=1/(0.06+d);num+=w*y;den+=w
    p=num/den; n=min(7,len(ds)); local=sum(y for _,y in ds[:n])/n
    return p,local,len(ds)

def samples_for_day(rows):
    s=[]
    for h in DEFAULT_CELL['sessions']:
        i=idx_for_hour(rows,h)
        if i is None:continue
        for side in (-1,1):
            for stop in STOPS:
                for rr in RRS:
                    y,r,mfe,mae,why=outcome(rows,i,side,stop,rr)
                    s.append({'x':features(rows,i,side,stop,rr),'y':y,'r':r,'h':h,'side':side,'stop':stop,'rr':rr})
    return s

raw=os.environ.get('FOREX_STRATEGY_PROFILE_JSON','').strip()
PROFILE=json.loads(raw) if raw else {'defaults':{'1':dict(DEFAULT_CELL),'2':dict(DEFAULT_CELL)},'symbols':{}}
G['PROFILE']=PROFILE

def cell(sym,rr):
    key=sym.replace('/',''); c=dict(DEFAULT_CELL)
    c.update((PROFILE.get('defaults') or {}).get(str(rr)) or {})
    c.update((((PROFILE.get('symbols') or {}).get(key) or {}).get(str(rr)) or {}))
    c['method']=str(c.get('method','TREND_CONTINUATION')).upper()
    if c['method'] not in ALLOWED:raise ValueError('invalid method '+c['method'])
    c['sessions']=[int(h) for h in c.get('sessions',DEFAULT_CELL['sessions']) if 0<=int(h)<=23]
    c['minProb']=min(.96,max(.50,float(c.get('minProb',.72)))); c['minLocal']=min(1,max(.50,float(c.get('minLocal',.82))))
    c['stopMin']=max(.6,float(c.get('stopMin',.8))); c['stopMax']=min(3.0,float(c.get('stopMax',2.2)))
    c['trendMin']=min(.6,max(-.2,float(c.get('trendMin',.06)))); c['momentumMin']=min(.8,max(-.5,float(c.get('momentumMin',.02))))
    c['extensionMax']=min(3,max(.3,float(c.get('extensionMax',1.35))))
    return c

SAFE_NAMES=set(FEATURE_NAMES)|{'pr','local','edge','rr'}
SAFE_FUNCS={'abs':abs,'min':min,'max':max}
ALLOWED_AST=(ast.Expression,ast.BoolOp,ast.And,ast.Or,ast.UnaryOp,ast.Not,ast.USub,ast.UAdd,ast.BinOp,ast.Add,ast.Sub,ast.Mult,ast.Div,
             ast.Compare,ast.Gt,ast.GtE,ast.Lt,ast.LtE,ast.Eq,ast.NotEq,ast.Name,ast.Load,ast.Constant,ast.Call)

def safe_expr(expr,env):
    if not isinstance(expr,str) or len(expr)>700:raise ValueError('invalid DSL expression')
    t=ast.parse(expr,mode='eval')
    for n in ast.walk(t):
        if not isinstance(n,ALLOWED_AST):raise ValueError('forbidden DSL AST '+type(n).__name__)
        if isinstance(n,ast.Name) and n.id not in SAFE_NAMES and n.id not in SAFE_FUNCS:raise ValueError('forbidden name '+n.id)
        if isinstance(n,ast.Call):
            if not isinstance(n.func,ast.Name) or n.func.id not in SAFE_FUNCS:raise ValueError('forbidden call')
            if n.keywords:raise ValueError('keywords forbidden')
    return eval(compile(t,'<forex-dsl>','eval'),{'__builtins__':{}},{**SAFE_FUNCS,**env})

def env_for(x,pr=.5,local=.5,rr=1):
    e={k:float(v) for k,v in zip(FEATURE_NAMES,x)};e.update(pr=float(pr),local=float(local),edge=float(pr)*(rr+1)-1,rr=float(rr));return e

def legacy_method_ok(x,c,rr):
    # Use V5's tested implementation for built-in families.
    return G['method_ok'](x,c,rr)

def method_ok(x,c,rr):
    if c['method']!='CUSTOM_RULESET':return legacy_method_ok(x,c,rr)
    expr=c.get('entryExpr') or 'True'
    try:return bool(safe_expr(expr,env_for(x,rr=rr)))
    except Exception:return False

def quality(x,pr,local,c,rr):
    if c['method']!='CUSTOM_RULESET':return G['quality'](x,pr,local,c,rr)
    expr=c.get('qualityExpr') or 'edge + 0.03*local'
    try:return float(safe_expr(expr,env_for(x,pr,local,rr)))
    except Exception:return -1e9

# Rebind functions used by extracted V5 choose/force routines.
G.update({'features':features,'predict':predict,'samples_for_day':samples_for_day,'cell':cell,'method_ok':method_ok,'quality':quality,'PROFILE':PROFILE})
choose,force_daily_entry=G['choose'],G['force_daily_entry']

def random_blocks():
    span=(END-START).days-BLOCK_DAYS;chosen=[]
    for _ in range(50000):
        if len(chosen)>=BLOCKS:break
        a=START+timedelta(days=RNG.randint(0,max(1,span)));b=a+timedelta(days=BLOCK_DAYS)
        if any(not (b<=x or a>=y) for x,y in chosen):continue
        chosen.append((a,b))
    if len(chosen)<BLOCKS:raise RuntimeError('cannot sample random non-overlapping blocks')
    return sorted(chosen)

blocks=random_blocks()
report={'version':'FOREX-TWELVEDATA-WALKFORWARD-7-DSL-100-RANDOM-DAYS','mode':MODE,'sourceSha':SOURCE_SHA,'seed':SEED,
 'generatedAt':datetime.now(timezone.utc).isoformat(),'strategyProfile':PROFILE,'featureNames':FEATURE_NAMES,
 'rules':{'source':'Twelve Data 5min','noLookahead':True,'randomOOSDaysPerSymbol':TARGET_DAYS,'randomBlocks':BLOCKS,
          'testDaysPerBlock':TEST_DAYS_PER_BLOCK,'trainPrefixDaysPerBlock':TRAIN_DAYS_PER_BLOCK,'minimumEntriesPerSymbolPerOOSDay':1,
          'strategyDSL':{'sandboxed':True,'arbitraryPython':False,'customEntryExpr':True,'customQualityExpr':True,'expandedFeatures':FEATURE_NAMES},
          'dailyFallbackPreOutcome':True,'rrEvaluatedIndependently':[1,2],'sameBarSLTP':'SL_FIRST_PESSIMISTIC','timeouts':'LOSS',
          'targetWinrateStrictlyGreaterThan':TARGET,'minimumTradesPerSymbolRR':MIN_TRADES,
          'antiCherryPick':'all selected OOS days/trades/forced flags/failures retained; strategy expressions validated before outcome; fresh OOS only after DEV approval'},
 'blocks':[{'start':a.isoformat(),'end':b.isoformat()} for a,b in blocks],'symbols':{},'pass':False}

allpass=True
for sym in SYMS:
    trades=[];src=[];err=None;total_test_days=0;days_with_entry=0;forced_days=0;selected_days=[]
    try:
        for bi,(a,b) in enumerate(blocks):
            rows=enrich(fetch(sym,a,b));groups=day_groups(rows);days=sorted(groups);need=TRAIN_DAYS_PER_BLOCK+TEST_DAYS_PER_BLOCK
            if len(days)<need:raise RuntimeError(f'{sym} block {bi}: only {len(days)} valid days, need {need}')
            train_days=days[:TRAIN_DAYS_PER_BLOCK];pool=days[TRAIN_DAYS_PER_BLOCK:]
            if len(pool)<TEST_DAYS_PER_BLOCK:raise RuntimeError(f'{sym} block {bi}: insufficient OOS pool')
            test_days=sorted(RNG.sample(pool,TEST_DAYS_PER_BLOCK));selected_days.extend(test_days);train=[]
            for d in train_days:train.extend(samples_for_day(groups[d]))
            block_trades=[];block_forced=0
            for d in test_days:
                total_test_days+=1;day_trades=[]
                for rr in RRS:
                    t,_=choose(groups[d],train,sym,rr)
                    if t:trades.append(t);block_trades.append(t);day_trades.append(t)
                if not day_trades:
                    ft=force_daily_entry(groups[d],train,sym)
                    if ft is None:raise RuntimeError(f'{sym} {d}: DAILY_ENTRY_UNAVAILABLE')
                    trades.append(ft);block_trades.append(ft);day_trades.append(ft);forced_days+=1;block_forced+=1
                days_with_entry+=1
            src.append({'block':bi,'trainDays':train_days,'selectedOOSDays':test_days,'testDays':len(test_days),'daysWithEntry':len(test_days),
                        'forcedDailyDays':block_forced,'testMetrics':{'RR1':metrics([x for x in block_trades if x['rr']==1]),'RR2':metrics([x for x in block_trades if x['rr']==2])}})
            time.sleep(float(os.environ.get('TWELVEDATA_INTER_REQUEST_SLEEP','8.2')))
    except Exception as e:err=str(e)
    by={str(rr):metrics([x for x in trades if x['rr']==rr]) for rr in RRS}
    exact_days=(err is None and total_test_days==TARGET_DAYS and len(set(selected_days))==TARGET_DAYS);daily_pass=(exact_days and days_with_entry==TARGET_DAYS)
    rr_pass={str(rr):(err is None and by[str(rr)]['trades']>=MIN_TRADES and by[str(rr)]['winrate']>TARGET and by[str(rr)]['avgR']>0) for rr in RRS}
    passed=daily_pass and all(rr_pass.values());allpass &= passed
    report['symbols'][sym.replace('/','')]={'pass':passed,'rrPass':rr_pass,'dailyEntryPass':daily_pass,'requiredOOSDays':TARGET_DAYS,
      'actualOOSDays':total_test_days,'daysWithEntry':days_with_entry,'dailyEntryCoveragePct':round(100*days_with_entry/TARGET_DAYS,2) if TARGET_DAYS else 0,
      'forcedDailyDays':forced_days,'selectedOOSDays':selected_days,'holdout':{'all':metrics(trades),'byRR':by},
      'activeProfiles':{'1':cell(sym,1),'2':cell(sym,2)},'source':src,'dataError':err,'trades':trades}
    print(sym,by,'OOSdays',total_test_days,'dailyEntries',days_with_entry,'forced',forced_days,'PASS' if passed else 'FAIL',err or '',flush=True)
    os.makedirs('data',exist_ok=True);json.dump(report,open(OUT,'w'),indent=2)
report['pass']=allpass;json.dump(report,open(OUT,'w'),indent=2);print('FINAL_PASS',allpass,'seed',SEED,'requiredDays',TARGET_DAYS)
