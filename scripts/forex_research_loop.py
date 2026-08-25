#!/usr/bin/env python3
"""Continuous PAPER_ONLY Forex research loop for the trading VPS.

State machine:
  BACKTEST -> STRICT_GATE -> 3AI_REVIEW -> VALIDATE_PROFILE -> NEXT_FRESH_OOS

The loop NEVER executes trades and NEVER changes production Bybit code/configuration.
A failed acceptance round cannot be repeated with the same research profile merely to
sample another lucky seed: a materially changed profile is required before the next OOS.
"""
from __future__ import annotations
import json, os, random, re, shutil, signal, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO=Path(os.environ.get('FOREX_RESEARCH_REPO','/opt/trading/trading-api-main'))
STATE_DIR=Path(os.environ.get('FOREX_RESEARCH_STATE_DIR','/var/lib/trading/forex-research'))
STATE_FILE=STATE_DIR/'state.json'
ROUNDS_DIR=STATE_DIR/'rounds'
REVIEWS_DIR=STATE_DIR/'reviews'
LOCK_FILE=STATE_DIR/'running.lock'
BACKTEST=REPO/'scripts/forex_twelvedata_walkforward_v4.py'
LATEST=REPO/'data/forex-twelvedata-walkforward-latest.json'
BRIDGE=os.environ.get('FOREX_AI_BRIDGE_URL','http://127.0.0.1:8789/review')
TARGET=float(os.environ.get('BACKTEST_TARGET_WR','80'))
MIN_TRADES=int(os.environ.get('BACKTEST_MIN_TEST_DAYS','18'))
SLEEP_BETWEEN_ROUNDS=int(os.environ.get('FOREX_RESEARCH_ROUND_PAUSE_SECONDS','3'))
AI_RETRIES=int(os.environ.get('FOREX_RESEARCH_AI_RETRIES','5'))

DEFAULT_PROFILE={'rr1MinProb':0.74,'rr2MinProb':0.72,'rr1MinLocal':0.86,'rr2MinLocal':0.86,'method':'SELECTIVE_TREND_KNN'}
BOUNDS={'rr1MinProb':(0.58,0.94),'rr2MinProb':(0.58,0.94),'rr1MinLocal':(0.57,1.0),'rr2MinLocal':(0.57,1.0)}
ALLOWED_METHODS={'SELECTIVE_TREND_KNN'}
PROFILE_RE=re.compile(r'FOREX_PROFILE_BEGIN\s*(\{.*?\})\s*FOREX_PROFILE_END',re.S)
STOP=False

def now(): return datetime.now(timezone.utc).isoformat()
def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)); os.replace(tmp,path)
def load_state():
    try:return json.loads(STATE_FILE.read_text())
    except:return {'version':'FOREX-RESEARCH-LOOP-1','mode':'PAPER_ONLY','round':0,'status':'INIT','profile':DEFAULT_PROFILE.copy(),'history':[],'updatedAt':now()}
def save(st): st['updatedAt']=now(); atomic_json(STATE_FILE,st)
def sh(cmd,env=None,timeout=None):
    return subprocess.run(cmd,cwd=str(REPO),env=env,capture_output=True,text=True,timeout=timeout,check=False)
def flatten_strings(x):
    if isinstance(x,str): yield x
    elif isinstance(x,dict):
        for v in x.values(): yield from flatten_strings(v)
    elif isinstance(x,list):
        for v in x: yield from flatten_strings(v)
def bridge_secret():
    direct=os.environ.get('V11_AI_BRIDGE_SECRET','').strip()
    if direct:return direct
    p=Path('/etc/trading-v11-ai.env')
    if p.exists():
        for line in p.read_text(errors='ignore').splitlines():
            if line.startswith('V11_AI_BRIDGE_SECRET='):return line.split('=',1)[1].strip()
    raise RuntimeError('V11_AI_BRIDGE_SECRET unavailable')
def strict_pass(rep):
    if not rep.get('pass'): return False
    syms=rep.get('symbols') or {}
    if not syms:return False
    for s,x in syms.items():
        by=((x.get('holdout') or {}).get('byRR') or {})
        for rr in ('1','2'):
            m=by.get(rr) or {}
            if int(m.get('trades') or 0)<MIN_TRADES:return False
            if float(m.get('winrate') or 0)<=TARGET:return False
            if float(m.get('avgR') or 0)<=0:return False
    return True
def summarize(rep):
    out={}
    for s,x in (rep.get('symbols') or {}).items():
        out[s]={'pass':x.get('pass'),'byRR':((x.get('holdout') or {}).get('byRR') or {}),'dataError':x.get('dataError')}
    return {'version':rep.get('version'),'seed':rep.get('seed'),'pass':rep.get('pass'),'symbols':out}
def run_backtest(st):
    profile=st['profile']; seed=random.SystemRandom().randrange(1,2**31-1)
    env=os.environ.copy(); env.update({
      'BACKTEST_SEED':str(seed),'BACKTEST_WINDOWS':os.environ.get('BACKTEST_WINDOWS','6'),
      'BACKTEST_WINDOW_DAYS':os.environ.get('BACKTEST_WINDOW_DAYS','24'),
      'BACKTEST_MIN_TEST_DAYS':str(MIN_TRADES),'BACKTEST_TARGET_WR':str(TARGET),
      'RR1_MIN_PROB':str(profile['rr1MinProb']),'RR2_MIN_PROB':str(profile['rr2MinProb']),
      'RR1_MIN_LOCAL':str(profile['rr1MinLocal']),'RR2_MIN_LOCAL':str(profile['rr2MinLocal']),
      'GITHUB_SHA':sh(['git','rev-parse','HEAD']).stdout.strip(),
    })
    st['status']='BACKTEST_RUNNING'; st['activeSeed']=seed; save(st)
    p=sh(['python3',str(BACKTEST)],env=env,timeout=int(os.environ.get('FOREX_BACKTEST_TIMEOUT_SECONDS','5400')))
    if not LATEST.exists(): raise RuntimeError('backtest evidence missing: '+(p.stderr or p.stdout)[-1500:])
    rep=json.loads(LATEST.read_text()); rid=st['round']+1
    dest=ROUNDS_DIR/f'round-{rid:05d}-seed-{seed}.json'; atomic_json(dest,rep)
    return rep,dest,p
def ai_review(st,rep):
    summary=summarize(rep); old=st['profile']; secret=bridge_secret()
    instruction=(
      'PAPER_ONLY FOREX RESEARCH. Independently diagnose this failed strict OOS round. '
      'Acceptance is immutable: every symbol must exceed 80% WR independently at RR1 and RR2, positive avgR, minimum samples. '
      'Do not cherry-pick windows, do not lower acceptance, do not propose live trading. '
      'Propose ONE materially changed next research profile using only SELECTIVE_TREND_KNN and these numeric fields: '
      'rr1MinProb 0.58..0.94, rr2MinProb 0.58..0.94, rr1MinLocal 0.57..1.00, rr2MinLocal 0.57..1.00. '
      'Balance selectivity against the minimum sample requirement. Return exactly one block '
      'FOREX_PROFILE_BEGIN {"method":"SELECTIVE_TREND_KNN","rr1MinProb":0.xx,"rr2MinProb":0.xx,"rr1MinLocal":0.xx,"rr2MinLocal":0.xx} FOREX_PROFILE_END '
      'plus concise rationale. The next round will use fresh unseen random OOS windows.'
    )
    body={'evidence':{'mode':'MULTI_AI_ENGINEERING_TASK','task_id':f'forex-research-round-{st["round"]+1}',
      'instruction':instruction,'context':{'currentProfile':old,'failedOOS':summary,'target':'>80% each symbol each RR','minimumTradesPerSymbolRR':MIN_TRADES},
      'requestedProviders':['claude','codex','deepseek']}}
    raw=json.dumps(body).encode(); req=urllib.request.Request(BRIDGE,data=raw,method='POST',headers={'Authorization':'Bearer '+secret,'Content-Type':'application/json'})
    last=None
    for attempt in range(AI_RETRIES):
        try:
            with urllib.request.urlopen(req,timeout=150) as r: result=json.loads(r.read().decode())
            proposals=[]
            for text in flatten_strings(result):
                for m in PROFILE_RE.finditer(text):
                    try: proposals.append(json.loads(m.group(1)))
                    except: pass
            if proposals:
                REVIEWS_DIR.mkdir(parents=True,exist_ok=True)
                atomic_json(REVIEWS_DIR/f'review-{st["round"]+1:05d}.json',result)
                return proposals,result
            last='3AI response contained no valid FOREX_PROFILE block'
        except Exception as e:last=f'{type(e).__name__}: {e}'
        time.sleep(min(30,2**attempt))
    raise RuntimeError('3AI review unavailable: '+str(last))
def validate_profile(p,old):
    if not isinstance(p,dict) or p.get('method') not in ALLOWED_METHODS:return None
    q={'method':p['method']}
    for k,(lo,hi) in BOUNDS.items():
        try:v=float(p[k])
        except:return None
        if not lo<=v<=hi:return None
        q[k]=round(v,4)
    # Material change is mandatory: never spin fresh seeds with an identical candidate.
    delta=max(abs(q[k]-float(old[k])) for k in BOUNDS)
    if delta<0.005:return None
    return q
def aggregate_proposals(props,old):
    valid=[validate_profile(p,old) for p in props]; valid=[p for p in valid if p]
    if not valid:return None
    # Robust consensus: coordinate median over every valid provider proposal.
    q={'method':'SELECTIVE_TREND_KNN'}
    for k in BOUNDS:
        xs=sorted(float(p[k]) for p in valid); q[k]=round(xs[len(xs)//2],4)
    return validate_profile(q,old)
def handler(*_):
    global STOP; STOP=True

def main():
    signal.signal(signal.SIGTERM,handler); signal.signal(signal.SIGINT,handler)
    STATE_DIR.mkdir(parents=True,exist_ok=True); ROUNDS_DIR.mkdir(parents=True,exist_ok=True); REVIEWS_DIR.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(LOCK_FILE,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.write(fd,str(os.getpid()).encode()); os.close(fd)
    except FileExistsError: raise SystemExit('FOREX_RESEARCH_SINGLE_FLIGHT_LOCKED')
    st=load_state(); st['status']='RUNNING'; save(st)
    try:
        while not STOP:
            rep,path,p=run_backtest(st); st['round']+=1
            rec={'round':st['round'],'seed':rep.get('seed'),'evidence':str(path),'profile':dict(st['profile']),
                 'pass':strict_pass(rep),'at':now(),'stdoutTail':(p.stdout or '')[-1200:]}
            st.setdefault('history',[]).append(rec); st['history']=st['history'][-200:]
            if rec['pass']:
                st['status']='TARGET_ACHIEVED'; st['finalEvidence']=str(path); save(st); print('FOREX_TARGET_ACHIEVED',path,flush=True); return 0
            st['status']='WAITING_3AI_REVIEW'; save(st)
            props,_=ai_review(st,rep); nxt=aggregate_proposals(props,st['profile'])
            if not nxt:
                st['status']='BLOCKED_NO_MATERIAL_3AI_PROFILE'; save(st)
                raise RuntimeError('3AI did not produce a valid materially changed profile; refusing seed-cherry-pick retry')
            st['previousProfile']=st['profile']; st['profile']=nxt; st['status']='NEXT_FRESH_OOS'; save(st)
            time.sleep(SLEEP_BETWEEN_ROUNDS)
        st['status']='STOPPED'; save(st); return 0
    except Exception as e:
        st['status']='BLOCKED'; st['lastError']=f'{type(e).__name__}: {e}'; save(st); raise
    finally:
        try:LOCK_FILE.unlink()
        except:pass
if __name__=='__main__': raise SystemExit(main())
