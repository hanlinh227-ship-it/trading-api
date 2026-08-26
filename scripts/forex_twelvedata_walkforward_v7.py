#!/usr/bin/env python3
"""PAPER_ONLY V7: strict random OOS validation + safe 3AI strategy DSL.

Canonical guarantees:
- all V5 extracted functions receive the V4 primitives they reference;
- random windows are wide enough for TRAIN + TEST trading days;
- optional BACKTEST_SYMBOLS is supported for deployment smoke tests only;
- strategy results remain strict and are never converted from infrastructure errors.
"""
import ast
import json
import os
import random
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

BASE = Path(__file__).with_name('forex_twelvedata_walkforward_v5.py')
OUT = 'data/forex-twelvedata-walkforward-latest.json'
KEY = os.environ.get('TWELVEDATA_API_KEY', '').strip()
if not KEY:
    raise SystemExit('TWELVEDATA_API_KEY missing')

DEFAULT_SYMS = ['EUR/USD','GBP/USD','USD/JPY','USD/CHF','AUD/USD','NZD/USD','USD/CAD','EUR/JPY','GBP/JPY','EUR/GBP','XAU/USD']
_symbol_override = [x.strip().upper() for x in os.environ.get('BACKTEST_SYMBOLS','').split(',') if x.strip()]
SYMS = _symbol_override or DEFAULT_SYMS
RRS = (1, 2)
STOPS = (.8, 1., 1.2, 1.5, 1.8, 2.2)
SEED = int(os.environ.get('BACKTEST_SEED') or random.SystemRandom().randrange(1, 2**31 - 1))
RNG = random.Random(SEED)
BLOCKS = int(os.environ.get('BACKTEST_RANDOM_BLOCKS', '10'))
# 35 calendar days protects 6 train + 10 OOS trading days across weekends/holiday clusters.
BLOCK_DAYS = max(35, int(os.environ.get('BACKTEST_BLOCK_DAYS', '35')))
TEST = int(os.environ.get('BACKTEST_TEST_DAYS_PER_BLOCK', '10'))
TRAIN = int(os.environ.get('BACKTEST_TRAIN_DAYS_PER_BLOCK', '6'))
TARGET_DAYS = BLOCKS * TEST
MIN_TRADES = int(os.environ.get('BACKTEST_MIN_TEST_DAYS', '18'))
TARGET = float(os.environ.get('BACKTEST_TARGET_WR', '80'))
MODE = os.environ.get('FOREX_RESEARCH_MODE', 'ACCEPTANCE').upper()
SOURCE_SHA = os.environ.get('GITHUB_SHA', '')
START = datetime.fromisoformat(os.environ.get('BACKTEST_START', '2025-01-06')).replace(tzinfo=timezone.utc)
END = datetime.fromisoformat(os.environ.get('BACKTEST_END', '2026-07-31')).replace(tzinfo=timezone.utc)
LEGACY = {'TREND_CONTINUATION','MOMENTUM_BREAKOUT','PULLBACK_TREND','MEAN_REVERSION','HYBRID_REGIME'}
ALLOWED = LEGACY | {'CUSTOM_RULESET'}
DEFAULT = {
    'method':'TREND_CONTINUATION','minProb':.72,'minLocal':.82,
    'sessions':[6,7,8,9,10,12,13,14,15,16],
    'stopMin':.8,'stopMax':2.2,'trendMin':.06,'momentumMin':.02,'extensionMax':1.35,
}

# Extract definitions only; never execute the V5 driver.
tree = ast.parse(BASE.read_text())
ns = {}
exec(compile(ast.Module([n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef))], []), str(BASE), 'exec'), ns)
ns.update(
    BASE=Path(__file__).with_name('forex_twelvedata_walkforward_v4.py'), OUT=OUT, KEY=KEY,
    SYMS=SYMS, SEED=SEED, RNG=RNG, WINDOWS=BLOCKS, DAYS=BLOCK_DAYS,
    MIN_TRADES=MIN_TRADES, TARGET=TARGET, SOURCE_SHA=SOURCE_SHA, MODE=MODE,
    START=START, END=END, HOURS=DEFAULT['sessions'], STOPS=STOPS, RRS=RRS,
    ALLOWED=ALLOWED, DEFAULT_CELL=DEFAULT, MIN_PROB={1:.72,2:.72}, MIN_LOCAL={1:.82,2:.82},
)
N = ns['load_v4_primitives']()
ns['N'] = N
fetch = N['fetch']
enrich = N['enrich']
day_groups = N['day_groups']
outcome = N['outcome']
idx_for_hour = N['idx_for_hour']
metrics = N['metrics']
V5_METHOD_OK = ns['method_ok']
V5_QUALITY = ns['quality']

FEATURES = ['t1','t2','m3','m12','m36','rsi','ext','pos','vol','body','bar','hourSin','hourCos','stopNorm','rrNorm','ema8Slope','ema20Slope','atrRegime','compression','wickPressure','rangePosition','impulseRatio']
ENTRY_NAMES = set(FEATURES) | {'rr'}
QUALITY_NAMES = ENTRY_NAMES | {'pr','local','edge'}
WEIGHTS = [1.2,1.2,.65,.95,.8,.75,.9,.55,.25,.25,.2,.15,.15,.55,.7,.75,.65,.35,.35,.3,.45,.45]

def features(rows, i, side, stop, rr):
    x = N['features'](rows, i, side, stop, rr)
    r = rows[i]
    a = max(r['atr'], 1e-12)
    j12 = max(0, i-12)
    r12 = rows[j12:i+1]
    r36 = rows[max(0,i-36):i+1]
    av = sum(z['atr'] for z in r36) / max(1, len(r36))
    rg12 = max(z['h'] for z in r12) - min(z['l'] for z in r12)
    rg36 = max(z['h'] for z in r36) - min(z['l'] for z in r36)
    upper = r['h'] - max(r['o'], r['c'])
    lower = min(r['o'], r['c']) - r['l']
    past = rows[:i+1]
    hi = max(z['h'] for z in past)
    lo = min(z['l'] for z in past)
    extra = [
        side*(r['e8']-rows[j12]['e8'])/a,
        side*(r['e20']-rows[j12]['e20'])/a,
        min(3,r['atr']/max(av,1e-12)),
        min(3,rg12/max(rg36,1e-12)*3),
        side*(lower-upper)/a,
        ((r['c']-lo)/max(hi-lo,1e-12)-.5)*side*2,
        side*(r['c']-rows[j12]['c'])/max(rg12,1e-12),
    ]
    return x + extra

def dist(a, b):
    return sum(w*(x-y)**2 for w,x,y in zip(WEIGHTS,a,b))

def predict(x, train, k=25):
    ds = sorted(((dist(x,z['x']),z['y']) for z in train), key=lambda z:z[0])[:min(k,len(train))]
    if not ds:
        return .5,.5,0
    num,den = 1.5,3.
    for d,y in ds:
        w = 1/(.06+d)
        num += w*y
        den += w
    n = min(7,len(ds))
    return num/den, sum(y for _,y in ds[:n])/n, len(ds)

def samples_for_day(rows):
    out = []
    for h in range(24):
        i = idx_for_hour(rows,h)
        if i is None:
            continue
        for side in (-1,1):
            for stop in STOPS:
                for rr in RRS:
                    y,r,_,_,_ = outcome(rows,i,side,stop,rr)
                    out.append({'x':features(rows,i,side,stop,rr),'y':y,'r':r,'h':h,'side':side,'stop':stop,'rr':rr})
    return out

raw = os.environ.get('FOREX_STRATEGY_PROFILE_JSON','').strip()
PROFILE = json.loads(raw) if raw else {'defaults':{'1':dict(DEFAULT),'2':dict(DEFAULT)},'symbols':{}}
ns['PROFILE'] = PROFILE

def cell(sym, rr):
    c = dict(DEFAULT)
    c.update((PROFILE.get('defaults') or {}).get(str(rr)) or {})
    c.update((((PROFILE.get('symbols') or {}).get(sym.replace('/','')) or {}).get(str(rr)) or {}))
    c['method'] = str(c.get('method','TREND_CONTINUATION')).upper()
    if c['method'] not in ALLOWED:
        raise ValueError('invalid method '+c['method'])
    c['sessions'] = [int(h) for h in c.get('sessions',DEFAULT['sessions']) if 0 <= int(h) <= 23]
    c['minProb'] = min(.96,max(.5,float(c.get('minProb',.72))))
    c['minLocal'] = min(1,max(.5,float(c.get('minLocal',.82))))
    c['stopMin'] = max(.6,float(c.get('stopMin',.8)))
    c['stopMax'] = min(3,float(c.get('stopMax',2.2)))
    c['trendMin'] = min(.6,max(-.2,float(c.get('trendMin',.06))))
    c['momentumMin'] = min(.8,max(-.5,float(c.get('momentumMin',.02))))
    c['extensionMax'] = min(3,max(.3,float(c.get('extensionMax',1.35))))
    return c

FUNCS = {'abs':abs,'min':min,'max':max}
AST = (ast.Expression,ast.BoolOp,ast.And,ast.Or,ast.UnaryOp,ast.Not,ast.USub,ast.UAdd,ast.BinOp,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Compare,ast.Gt,ast.GtE,ast.Lt,ast.LtE,ast.Eq,ast.NotEq,ast.Name,ast.Load,ast.Constant,ast.Call)

def safe_eval(expr, env, names):
    if not isinstance(expr,str) or not expr.strip() or len(expr)>700:
        raise ValueError('bad expression')
    t = ast.parse(expr,mode='eval')
    for n in ast.walk(t):
        if not isinstance(n,AST):
            raise ValueError('forbidden AST')
        if isinstance(n,ast.Name) and n.id not in names and n.id not in FUNCS:
            raise ValueError('forbidden name '+n.id)
        if isinstance(n,ast.Call) and (not isinstance(n.func,ast.Name) or n.func.id not in FUNCS or n.keywords):
            raise ValueError('forbidden call')
    return eval(compile(t,'<dsl>','eval'),{'__builtins__':{}},{**FUNCS,**env})

def env_for(x, rr, pr=.5, local=.5):
    e = {k:float(v) for k,v in zip(FEATURES,x)}
    e.update(rr=float(rr),pr=float(pr),local=float(local),edge=float(pr)*(rr+1)-1)
    return e

def method_ok(x,c,rr):
    if c['method'] != 'CUSTOM_RULESET':
        return V5_METHOD_OK(x,c,rr)
    try:
        return bool(safe_eval(c['entryExpr'],env_for(x,rr),ENTRY_NAMES))
    except Exception:
        return False

def quality(x,pr,local,c,rr):
    if c['method'] != 'CUSTOM_RULESET':
        return V5_QUALITY(x,pr,local,c,rr)
    try:
        return float(safe_eval(c['qualityExpr'],env_for(x,rr,pr,local),QUALITY_NAMES))
    except Exception:
        return -1e9

# Canonical fix: V5 choose/force_daily execute in ns globals and require these V4 primitives.
ns.update(
    features=features, predict=predict, samples_for_day=samples_for_day, cell=cell,
    method_ok=method_ok, quality=quality, outcome=outcome, metrics=metrics,
    idx_for_hour=idx_for_hour, PROFILE=PROFILE,
)
choose = ns['choose']
force_daily = ns['force_daily_entry']

def random_blocks():
    if END <= START:
        raise RuntimeError('invalid backtest date range')
    span = (END-START).days - BLOCK_DAYS
    if span < 1:
        raise RuntimeError('date range too short for random block width')
    chosen = []
    for _ in range(100000):
        if len(chosen) >= BLOCKS:
            break
        a = START + timedelta(days=RNG.randint(0,span))
        b = a + timedelta(days=BLOCK_DAYS)
        if b > END:
            continue
        if any(not (b <= x or a >= y) for x,y in chosen):
            continue
        chosen.append((a,b))
    if len(chosen) < BLOCKS:
        raise RuntimeError(f'cannot sample {BLOCKS} non-overlapping {BLOCK_DAYS}-day blocks in range')
    return sorted(chosen)

blocks = random_blocks()
report = {
    'version':'FOREX-TWELVEDATA-WALKFORWARD-7-DSL-100-RANDOM-DAYS','mode':MODE,'seed':SEED,
    'generatedAt':datetime.now(timezone.utc).isoformat(),'strategyProfile':PROFILE,'featureNames':FEATURES,
    'rules':{
        'source':'Twelve Data 5min','noLookahead':True,'randomOOSDaysPerSymbol':TARGET_DAYS,
        'minimumEntriesPerSymbolPerOOSDay':1,
        'strategyDSL':{'sandboxed':True,'arbitraryPython':False,'entryExprNames':sorted(ENTRY_NAMES),'qualityExprNames':sorted(QUALITY_NAMES)},
        'sameBarSLTP':'SL_FIRST_PESSIMISTIC','timeouts':'LOSS','targetWinrateStrictlyGreaterThan':TARGET,
        'antiCherryPick':'all OOS days/trades/failures retained; fresh OOS only after DEV approval',
        'calendarBlockDays':BLOCK_DAYS,
    },
    'symbols':{},'pass':False,
}

allpass = True
for sym in SYMS:
    trades=[]; sources=[]; err=None; days_n=entry_days=forced=0; selected=[]
    try:
        for bi,(a,b) in enumerate(blocks):
            rows = enrich(fetch(sym,a,b))
            g = day_groups(rows)
            days = sorted(g)
            if len(days) < TRAIN+TEST:
                raise RuntimeError(f'{sym} block {bi}: insufficient valid days got={len(days)} need={TRAIN+TEST} window={a.date()}..{b.date()}')
            tr = days[:TRAIN]
            pool = days[TRAIN:]
            te = sorted(RNG.sample(pool,TEST))
            selected += te
            train = []
            for d in tr:
                train += samples_for_day(g[d])
            bt=[]; bf=0
            for d in te:
                days_n += 1
                dt=[]
                for rr in RRS:
                    t,_ = choose(g[d],train,sym,rr)
                    if t:
                        trades.append(t); bt.append(t); dt.append(t)
                if not dt:
                    t = force_daily(g[d],train,sym)
                    if t is None:
                        raise RuntimeError(f'{sym} {d}: DAILY_ENTRY_UNAVAILABLE')
                    trades.append(t); bt.append(t); forced += 1; bf += 1
                entry_days += 1
            sources.append({'block':bi,'trainDays':tr,'selectedOOSDays':te,'forcedDailyDays':bf,'testMetrics':{'RR1':metrics([x for x in bt if x['rr']==1]),'RR2':metrics([x for x in bt if x['rr']==2])}})
            time.sleep(float(os.environ.get('TWELVEDATA_INTER_REQUEST_SLEEP','8.2')))
    except Exception as e:
        err = f'{type(e).__name__}: {e}'
    by = {str(rr):metrics([x for x in trades if x['rr']==rr]) for rr in RRS}
    daily = err is None and days_n==TARGET_DAYS and entry_days==TARGET_DAYS and len(set(selected))==TARGET_DAYS
    rp = {str(rr):(err is None and by[str(rr)]['trades']>=MIN_TRADES and by[str(rr)]['winrate']>TARGET and by[str(rr)]['avgR']>0) for rr in RRS}
    passed = daily and all(rp.values())
    allpass &= passed
    report['symbols'][sym.replace('/','')] = {
        'pass':passed,'rrPass':rp,'dailyEntryPass':daily,'requiredOOSDays':TARGET_DAYS,
        'actualOOSDays':days_n,'daysWithEntry':entry_days,'dailyEntryCoveragePct':round(100*entry_days/TARGET_DAYS,2),
        'forcedDailyDays':forced,'selectedOOSDays':selected,'holdout':{'all':metrics(trades),'byRR':by},
        'activeProfiles':{'1':cell(sym,1),'2':cell(sym,2)},'source':sources,'dataError':err,'trades':trades,
    }
    print(sym,by,'days',days_n,'forced',forced,'PASS' if passed else 'FAIL',err or '',flush=True)
    os.makedirs('data',exist_ok=True)
    json.dump(report,open(OUT,'w'),indent=2)
report['pass'] = allpass
json.dump(report,open(OUT,'w'),indent=2)
print('FINAL_PASS',allpass,'seed',SEED)
