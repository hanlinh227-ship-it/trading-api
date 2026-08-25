#!/usr/bin/env python3
"""Continuous PAPER_ONLY 3AI Forex strategy research loop.

Cycle:
  ACCEPTANCE OOS -> failure analysis -> 3AI strategy proposal -> DEV validation -> fresh ACCEPTANCE OOS

The three AI may change method family, session, stop range and selection/regime parameters,
including symbol/RR-specific overrides. They may not weaken acceptance, hide failures, use
future outcomes, touch production trading code, or simply spin another seed with an unchanged profile.
"""
from __future__ import annotations
import json,os,random,re,signal,subprocess,time,urllib.request
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

REPO=Path(os.environ.get('FOREX_RESEARCH_REPO','/opt/trading/trading-api-main'))
STATE_DIR=Path(os.environ.get('FOREX_RESEARCH_STATE_DIR','/var/lib/trading/forex-research'))
STATE=STATE_DIR/'state.json'; ROUNDS=STATE_DIR/'rounds'; REVIEWS=STATE_DIR/'reviews'; DEV=STATE_DIR/'dev'; LOCK=STATE_DIR/'running.lock'
BACKTEST=REPO/'scripts/forex_twelvedata_walkforward_v5.py'; LATEST=REPO/'data/forex-twelvedata-walkforward-latest.json'
BRIDGE=os.environ.get('FOREX_AI_BRIDGE_URL','http://127.0.0.1:8789/review')
TARGET=float(os.environ.get('BACKTEST_TARGET_WR','80')); MIN_TRADES=int(os.environ.get('BACKTEST_MIN_TEST_DAYS','18'))
AI_RETRIES=int(os.environ.get('FOREX_RESEARCH_AI_RETRIES','5')); PAUSE=int(os.environ.get('FOREX_RESEARCH_ROUND_PAUSE_SECONDS','3'))
SYMS=['EURUSD','GBPUSD','USDJPY','USDCHF','AUDUSD','NZDUSD','USDCAD','EURJPY','GBPJPY','EURGBP','XAUUSD']
METHODS={'TREND_CONTINUATION','MOMENTUM_BREAKOUT','PULLBACK_TREND','MEAN_REVERSION','HYBRID_REGIME'}
DEFAULT_CELL={'method':'TREND_CONTINUATION','minProb':.72,'minLocal':.82,'sessions':[6,7,8,9,10,12,13,14,15,16],'stopMin':.8,'stopMax':2.2,'trendMin':.06,'momentumMin':.02,'extensionMax':1.35}
DEFAULT_PROFILE={'version':1,'defaults':{'1':dict(DEFAULT_CELL),'2':dict(DEFAULT_CELL)},'symbols':{}}
BLOCK_RE=re.compile(r'FOREX_RESEARCH_BEGIN\s*(\{.*?\})\s*FOREX_RESEARCH_END',re.S)
STOP=False

def now():return datetime.now(timezone.utc).isoformat()
def atomic(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True); t=path.with_suffix(path.suffix+'.tmp'); t.write_text(json.dumps(obj,indent=2,ensure_ascii=False)); os.replace(t,path)
def load():
    try:return json.loads(STATE.read_text())
    except:return {'version':'FOREX-RESEARCH-LOOP-2','mode':'PAPER_ONLY','round':0,'status':'INIT','profile':DEFAULT_PROFILE,'history':[],'updatedAt':now()}
def save(s):s['updatedAt']=now();atomic(STATE,s)
def sh(cmd,env=None,timeout=None):return subprocess.run(cmd,cwd=str(REPO),env=env,capture_output=True,text=True,timeout=timeout,check=False)
def strings(x):
    if isinstance(x,str):yield x
    elif isinstance(x,dict):
        for v in x.values():yield from strings(v)
    elif isinstance(x,list):
        for v in x:yield from strings(v)
def secret():
    v=os.environ.get('V11_AI_BRIDGE_SECRET','').strip()
    if v:return v
    p=Path('/etc/trading-v11-ai.env')
    if p.exists():
        for line in p.read_text(errors='ignore').splitlines():
            if line.startswith('V11_AI_BRIDGE_SECRET='):return line.split('=',1)[1].strip()
    raise RuntimeError('V11_AI_BRIDGE_SECRET unavailable')
def strict(rep):
    if not rep.get('pass'):return False
    for x in (rep.get('symbols') or {}).values():
        for rr in ('1','2'):
            m=(((x.get('holdout') or {}).get('byRR') or {}).get(rr) or {})
            if int(m.get('trades') or 0)<MIN_TRADES or float(m.get('winrate') or 0)<=TARGET or float(m.get('avgR') or 0)<=0:return False
    return True
def score(rep):
    vals=[]; samples=[]
    for x in (rep.get('symbols') or {}).values():
        for rr in ('1','2'):
            m=(((x.get('holdout') or {}).get('byRR') or {}).get(rr) or {}); vals.append(float(m.get('winrate') or 0)); samples.append(int(m.get('trades') or 0))
    return {'minWR':min(vals) if vals else 0,'meanWR':sum(vals)/len(vals) if vals else 0,'minTrades':min(samples) if samples else 0,'passedCells':sum(v>TARGET for v in vals),'cells':len(vals)}
def summary(rep):
    o={}
    for s,x in (rep.get('symbols') or {}).items():o[s]={'pass':x.get('pass'),'byRR':((x.get('holdout') or {}).get('byRR') or {}),'profiles':x.get('activeProfiles'),'dataError':x.get('dataError')}
    return {'seed':rep.get('seed'),'score':score(rep),'symbols':o}
def run(profile,mode,seed,start,end,windows,days):
    env=os.environ.copy();env.update({'BACKTEST_SEED':str(seed),'BACKTEST_WINDOWS':str(windows),'BACKTEST_WINDOW_DAYS':str(days),'BACKTEST_MIN_TEST_DAYS':str(MIN_TRADES),
      'BACKTEST_TARGET_WR':str(TARGET),'FOREX_STRATEGY_PROFILE_JSON':json.dumps(profile,separators=(',',':')),'FOREX_RESEARCH_MODE':mode,
      'BACKTEST_START':start,'BACKTEST_END':end,'GITHUB_SHA':sh(['git','rev-parse','HEAD']).stdout.strip()})
    p=sh(['python3',str(BACKTEST)],env=env,timeout=int(os.environ.get('FOREX_BACKTEST_TIMEOUT_SECONDS','5400')))
    if not LATEST.exists():raise RuntimeError('evidence missing '+(p.stderr or p.stdout)[-1200:])
    return json.loads(LATEST.read_text()),p
def acceptance(s):
    seed=random.SystemRandom().randrange(1,2**31-1);s['status']='ACCEPTANCE_RUNNING';s['activeSeed']=seed;save(s)
    rep,p=run(s['profile'],'ACCEPTANCE',seed,os.environ.get('FOREX_ACCEPT_START','2025-01-06'),os.environ.get('FOREX_ACCEPT_END','2026-07-31'),int(os.environ.get('BACKTEST_WINDOWS','6')),int(os.environ.get('BACKTEST_WINDOW_DAYS','24')))
    rid=s['round']+1;path=ROUNDS/f'round-{rid:05d}-seed-{seed}.json';atomic(path,rep);return rep,path,p
def call_ai(s,rep):
    instruction=(
      'PAPER_ONLY FOREX STRATEGY RESEARCH. Diagnose the failed OOS evidence and propose a genuinely improved strategy profile, not merely a lucky-seed retry. '
      'You may change strategy family per symbol and per RR among TREND_CONTINUATION, MOMENTUM_BREAKOUT, PULLBACK_TREND, MEAN_REVERSION, HYBRID_REGIME; '
      'you may change sessions, stopMin/stopMax, minProb/minLocal, trendMin, momentumMin, extensionMax. Different symbols/RRs may use different methods. '
      'Do not lower the immutable acceptance target (>80% WR each of 22 symbol/RR cells, positive avgR, >= minimum trades), remove symbols, cherry-pick periods, use lookahead, or propose LIVE execution. '
      'Prefer generalizable changes based on failure clusters, session/regime behavior, MFE/MAE and sample scarcity. '
      'Return ONE complete JSON research profile between FOREX_RESEARCH_BEGIN and FOREX_RESEARCH_END. Schema: '
      '{"version":integer,"defaults":{"1":CELL,"2":CELL},"symbols":{"EURUSD":{"1":CELL,"2":CELL},...}} where CELL fields are '
      '{"method":METHOD,"minProb":0.50..0.96,"minLocal":0.50..1.00,"sessions":[0..23],"stopMin":0.6..3.0,"stopMax":0.6..3.0,"trendMin":-0.2..0.6,"momentumMin":-0.5..0.8,"extensionMax":0.3..3.0}. '
      'Only include symbol overrides that are justified; defaults are required. Explain the hypothesis after the block.' )
    body={'evidence':{'mode':'MULTI_AI_ENGINEERING_TASK','task_id':f'forex-strategy-research-{s["round"]+1}','instruction':instruction,
      'context':{'currentProfile':s['profile'],'failedOOS':summary(rep),'target':'>80% each symbol each RR','minimumTrades':MIN_TRADES,
                 'researchPrinciple':'backtest is feedback for strategy improvement, not target-beautification'},'requestedProviders':['claude','codex','deepseek']}}
    req=urllib.request.Request(BRIDGE,data=json.dumps(body).encode(),method='POST',headers={'Authorization':'Bearer '+secret(),'Content-Type':'application/json'})
    last=None
    for a in range(AI_RETRIES):
        try:
            with urllib.request.urlopen(req,timeout=160) as r:result=json.loads(r.read().decode())
            props=[]
            for text in strings(result):
                for m in BLOCK_RE.finditer(text):
                    try:props.append(json.loads(m.group(1)))
                    except:pass
            if props:atomic(REVIEWS/f'review-{s["round"]+1:05d}.json',result);return props
            last='no FOREX_RESEARCH block'
        except Exception as e:last=f'{type(e).__name__}: {e}'
        time.sleep(min(30,2**a))
    raise RuntimeError('3AI unavailable '+str(last))
def valid_cell(c):
    if not isinstance(c,dict) or str(c.get('method','')).upper() not in METHODS:return None
    try:
        q={'method':str(c['method']).upper(),'minProb':float(c['minProb']),'minLocal':float(c['minLocal']),'sessions':sorted(set(int(x) for x in c['sessions'])),
           'stopMin':float(c['stopMin']),'stopMax':float(c['stopMax']),'trendMin':float(c['trendMin']),'momentumMin':float(c['momentumMin']),'extensionMax':float(c['extensionMax'])}
    except:return None
    if not (.50<=q['minProb']<=.96 and .50<=q['minLocal']<=1 and q['sessions'] and all(0<=x<=23 for x in q['sessions']) and .6<=q['stopMin']<=q['stopMax']<=3 and -.2<=q['trendMin']<=.6 and -.5<=q['momentumMin']<=.8 and .3<=q['extensionMax']<=3):return None
    return q
def validate(p,old):
    if not isinstance(p,dict) or not isinstance(p.get('defaults'),dict):return None
    q={'version':int(p.get('version',int(old.get('version',1))+1)),'defaults':{},'symbols':{}}
    for rr in ('1','2'):
        c=valid_cell(p['defaults'].get(rr));
        if not c:return None
        q['defaults'][rr]=c
    for sym,v in (p.get('symbols') or {}).items():
        if sym not in SYMS or not isinstance(v,dict):continue
        q['symbols'][sym]={}
        for rr in ('1','2'):
            if rr in v:
                c=valid_cell(v[rr]);
                if c:q['symbols'][sym][rr]=c
        if not q['symbols'][sym]:q['symbols'].pop(sym,None)
    if json.dumps(q,sort_keys=True)==json.dumps(old,sort_keys=True):return None
    return q
def choose_proposal(props,old):
    good=[validate(p,old) for p in props];good=[p for p in good if p]
    if not good:return None
    # Prefer method consensus across providers; ties choose the least complex profile.
    def signature(p):return (p['defaults']['1']['method'],p['defaults']['2']['method'])
    counts=Counter(signature(p) for p in good);best=max(counts.values())
    pool=[p for p in good if counts[signature(p)]==best]
    return min(pool,key=lambda p:len(p.get('symbols') or {}))
def dev_validate(candidate,baseline):
    seed=314159265
    common={'mode':'DEV','seed':seed,'start':os.environ.get('FOREX_DEV_START','2025-01-06'),'end':os.environ.get('FOREX_DEV_END','2025-12-31'),'windows':int(os.environ.get('FOREX_DEV_WINDOWS','4')),'days':int(os.environ.get('FOREX_DEV_WINDOW_DAYS','20'))}
    b,_=run(baseline,common['mode'],seed,common['start'],common['end'],common['windows'],common['days']); c,_=run(candidate,common['mode'],seed,common['start'],common['end'],common['windows'],common['days'])
    sb,sc=score(b),score(c);path=DEV/f'dev-{int(time.time())}.json';atomic(path,{'seed':seed,'baseline':sb,'candidate':sc,'candidateProfile':candidate})
    # Candidate must improve broad discrimination without collapsing sample coverage.
    ok=(sc['meanWR']>sb['meanWR']+0.5 or sc['passedCells']>sb['passedCells']) and sc['minTrades']>=max(4,min(MIN_TRADES,sb['minTrades']))
    return ok,{'baseline':sb,'candidate':sc,'path':str(path)}
def handler(*_):
    global STOP;STOP=True

def main():
    signal.signal(signal.SIGTERM,handler);signal.signal(signal.SIGINT,handler)
    for p in (STATE_DIR,ROUNDS,REVIEWS,DEV):p.mkdir(parents=True,exist_ok=True)
    try:fd=os.open(LOCK,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.write(fd,str(os.getpid()).encode());os.close(fd)
    except FileExistsError:raise SystemExit('FOREX_RESEARCH_SINGLE_FLIGHT_LOCKED')
    s=load();s['version']='FOREX-RESEARCH-LOOP-2';s['mode']='PAPER_ONLY';save(s)
    try:
        while not STOP:
            rep,path,p=acceptance(s);s['round']+=1;rec={'round':s['round'],'seed':rep.get('seed'),'evidence':str(path),'profile':s['profile'],'pass':strict(rep),'score':score(rep),'at':now(),'stdoutTail':(p.stdout or '')[-1000:]};s.setdefault('history',[]).append(rec);s['history']=s['history'][-200:];save(s)
            if rec['pass']:
                s['status']='TARGET_ACHIEVED';s['finalEvidence']=str(path);save(s);print('FOREX_TARGET_ACHIEVED',path,flush=True);return 0
            s['status']='3AI_RESEARCH';save(s);props=call_ai(s,rep);candidate=choose_proposal(props,s['profile'])
            if not candidate:raise RuntimeError('3AI produced no valid materially changed strategy profile; refusing seed spin')
            s['status']='DEV_VALIDATION';save(s);ok,dev=dev_validate(candidate,s['profile']);s['lastDev']=dev;save(s)
            if not ok:
                # Do not consume a blind acceptance round for a candidate that failed development validation.
                s['status']='DEV_REJECTED_RESEARCH_AGAIN';save(s);time.sleep(PAUSE);continue
            s['previousProfile']=s['profile'];s['profile']=candidate;s['status']='NEXT_FRESH_ACCEPTANCE_OOS';save(s);time.sleep(PAUSE)
        s['status']='STOPPED';save(s);return 0
    except Exception as e:s['status']='BLOCKED';s['lastError']=f'{type(e).__name__}: {e}';save(s);raise
    finally:
        try:LOCK.unlink()
        except:pass
if __name__=='__main__':raise SystemExit(main())
