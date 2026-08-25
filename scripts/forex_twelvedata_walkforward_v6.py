#!/usr/bin/env python3
"""PAPER_ONLY Forex 100-random-day OOS acceptance engine.

Acceptance contract:
- exactly 100 random OOS trading days per symbol (10 random non-overlapping blocks x 10 random days)
- every symbol must produce >=1 entry on every OOS day
- RR1 and RR2 are still scored independently
- no lookahead; daily fallback is selected before outcome
- all failures are persisted by the outer research loop
"""
import ast,json,os,random,time
from pathlib import Path
from datetime import datetime,timedelta,timezone
from collections import defaultdict

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
ALLOWED={'TREND_CONTINUATION','MOMENTUM_BREAKOUT','PULLBACK_TREND','MEAN_REVERSION','HYBRID_REGIME'}
DEFAULT_CELL={'method':'TREND_CONTINUATION','minProb':0.72,'minLocal':0.82,'sessions':[6,7,8,9,10,12,13,14,15,16],'stopMin':0.8,'stopMax':2.2,'trendMin':0.06,'momentumMin':0.02,'extensionMax':1.35}

# Reuse only definitions from V5; do not execute its driver.
tree=ast.parse(BASE.read_text())
keep=[n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef))]
G={}; exec(compile(ast.Module(body=keep,type_ignores=[]),str(BASE),'exec'),G)
G.update({'BASE':Path(__file__).with_name('forex_twelvedata_walkforward_v4.py'),'OUT':OUT,'KEY':KEY,'SYMS':SYMS,'SEED':SEED,'RNG':RNG,
          'WINDOWS':BLOCKS,'DAYS':BLOCK_DAYS,'MIN_TRADES':MIN_TRADES,'TARGET':TARGET,'SOURCE_SHA':SOURCE_SHA,'MODE':MODE,
          'START':START,'END':END,'HOURS':DEFAULT_CELL['sessions'],'STOPS':STOPS,'RRS':RRS,'ALLOWED':ALLOWED,'DEFAULT_CELL':DEFAULT_CELL,
          'MIN_PROB':{1:.72,2:.72},'MIN_LOCAL':{1:.82,2:.82}})
N=G['load_v4_primitives'](); G['N']=N
for k in ('fetch','enrich','day_groups','features','outcome','samples_for_day','predict','metrics'): G[k]=N[k]
raw=os.environ.get('FOREX_STRATEGY_PROFILE_JSON','').strip()
PROFILE=json.loads(raw) if raw else {'defaults':{'1':dict(DEFAULT_CELL),'2':dict(DEFAULT_CELL)},'symbols':{}}
G['PROFILE']=PROFILE
fetch,enrich,day_groups,samples_for_day,metrics=N['fetch'],N['enrich'],N['day_groups'],N['samples_for_day'],N['metrics']
choose,force_daily_entry,cell=G['choose'],G['force_daily_entry'],G['cell']

def random_blocks():
    span=(END-START).days-BLOCK_DAYS; chosen=[]
    for _ in range(50000):
        if len(chosen)>=BLOCKS: break
        a=START+timedelta(days=RNG.randint(0,max(1,span))); b=a+timedelta(days=BLOCK_DAYS)
        if any(not (b<=x or a>=y) for x,y in chosen): continue
        chosen.append((a,b))
    if len(chosen)<BLOCKS: raise RuntimeError('cannot sample random non-overlapping blocks')
    return sorted(chosen)

blocks=random_blocks()
report={'version':'FOREX-TWELVEDATA-WALKFORWARD-6-100-RANDOM-DAYS','mode':MODE,'sourceSha':SOURCE_SHA,'seed':SEED,
 'generatedAt':datetime.now(timezone.utc).isoformat(),'strategyProfile':PROFILE,
 'rules':{'source':'Twelve Data 5min','noLookahead':True,'randomOOSDaysPerSymbol':TARGET_DAYS,'randomBlocks':BLOCKS,
          'testDaysPerBlock':TEST_DAYS_PER_BLOCK,'trainPrefixDaysPerBlock':TRAIN_DAYS_PER_BLOCK,
          'minimumEntriesPerSymbolPerOOSDay':1,'dailyFallbackPreOutcome':True,'rrEvaluatedIndependently':[1,2],
          'sameBarSLTP':'SL_FIRST_PESSIMISTIC','timeouts':'LOSS','targetWinrateStrictlyGreaterThan':TARGET,
          'minimumTradesPerSymbolRR':MIN_TRADES,
          'antiCherryPick':'all 100 selected OOS days, all trades, forcedDaily flags, failed symbols and failed rounds must be retained; selection occurs before outcome'},
 'blocks':[{'start':a.isoformat(),'end':b.isoformat()} for a,b in blocks],'symbols':{},'pass':False}

allpass=True
for sym in SYMS:
    trades=[]; src=[]; err=None; total_test_days=0; days_with_entry=0; forced_days=0; selected_days=[]
    try:
        for bi,(a,b) in enumerate(blocks):
            rows=enrich(fetch(sym,a,b)); groups=day_groups(rows); days=sorted(groups)
            need=TRAIN_DAYS_PER_BLOCK+TEST_DAYS_PER_BLOCK
            if len(days)<need: raise RuntimeError(f'{sym} block {bi}: only {len(days)} valid days, need {need}')
            train_days=days[:TRAIN_DAYS_PER_BLOCK]
            pool=days[TRAIN_DAYS_PER_BLOCK:]
            if len(pool)<TEST_DAYS_PER_BLOCK: raise RuntimeError(f'{sym} block {bi}: insufficient OOS pool')
            # Precommit random OOS dates for this block before any outcome is evaluated.
            test_days=sorted(RNG.sample(pool,TEST_DAYS_PER_BLOCK)); selected_days.extend(test_days)
            train=[]
            for d in train_days: train.extend(samples_for_day(groups[d]))
            block_trades=[]; block_forced=0
            for d in test_days:
                total_test_days+=1; day_trades=[]
                for rr in RRS:
                    t,_=choose(groups[d],train,sym,rr)
                    if t: trades.append(t); block_trades.append(t); day_trades.append(t)
                if not day_trades:
                    ft=force_daily_entry(groups[d],train,sym)
                    if ft is None: raise RuntimeError(f'{sym} {d}: DAILY_ENTRY_UNAVAILABLE')
                    trades.append(ft); block_trades.append(ft); day_trades.append(ft); forced_days+=1; block_forced+=1
                days_with_entry+=1
            src.append({'block':bi,'trainDays':train_days,'selectedOOSDays':test_days,'testDays':len(test_days),
                        'daysWithEntry':len(test_days),'forcedDailyDays':block_forced,
                        'testMetrics':{'RR1':metrics([x for x in block_trades if x['rr']==1]),'RR2':metrics([x for x in block_trades if x['rr']==2])}})
            time.sleep(float(os.environ.get('TWELVEDATA_INTER_REQUEST_SLEEP','8.2')))
    except Exception as e: err=str(e)
    by={str(rr):metrics([x for x in trades if x['rr']==rr]) for rr in RRS}
    exact_days=(err is None and total_test_days==TARGET_DAYS and len(set(selected_days))==TARGET_DAYS)
    daily_pass=(exact_days and days_with_entry==TARGET_DAYS)
    rr_pass={str(rr):(err is None and by[str(rr)]['trades']>=MIN_TRADES and by[str(rr)]['winrate']>TARGET and by[str(rr)]['avgR']>0) for rr in RRS}
    passed=daily_pass and all(rr_pass.values()); allpass &= passed
    report['symbols'][sym.replace('/','')]={'pass':passed,'rrPass':rr_pass,'dailyEntryPass':daily_pass,
      'requiredOOSDays':TARGET_DAYS,'actualOOSDays':total_test_days,'daysWithEntry':days_with_entry,
      'dailyEntryCoveragePct':round(100*days_with_entry/TARGET_DAYS,2) if TARGET_DAYS else 0,'forcedDailyDays':forced_days,
      'selectedOOSDays':selected_days,'holdout':{'all':metrics(trades),'byRR':by},
      'activeProfiles':{'1':cell(sym,1),'2':cell(sym,2)},'source':src,'dataError':err,'trades':trades}
    print(sym,by,'OOSdays',total_test_days,'dailyEntries',days_with_entry,'forced',forced_days,'PASS' if passed else 'FAIL',err or '',flush=True)
    os.makedirs('data',exist_ok=True); json.dump(report,open(OUT,'w'),indent=2)
report['pass']=allpass
json.dump(report,open(OUT,'w'),indent=2)
print('FINAL_PASS',allpass,'seed',SEED,'requiredDays',TARGET_DAYS)
