#!/usr/bin/env python3
"""100-random-day controller for the PAPER_ONLY 3AI Forex research lab."""
import json,os,signal,time,urllib.request
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import forex_research_loop as lab

lab.BACKTEST=lab.REPO/'scripts/forex_twelvedata_walkforward_v6.py'
REQUIRED_DAYS=int(os.environ.get('BACKTEST_REQUIRED_RANDOM_DAYS','100'))
STOP=False

def handler(*_):
    global STOP; STOP=True

def strict100(rep):
    if not rep.get('pass'): return False
    syms=rep.get('symbols') or {}
    if set(syms)!=set(lab.SYMS): return False
    for sym,x in syms.items():
        if int(x.get('requiredOOSDays') or 0)!=REQUIRED_DAYS:return False
        if int(x.get('actualOOSDays') or 0)!=REQUIRED_DAYS:return False
        if int(x.get('daysWithEntry') or 0)!=REQUIRED_DAYS:return False
        if float(x.get('dailyEntryCoveragePct') or 0)!=100.0:return False
        if x.get('dailyEntryPass') is not True:return False
        for rr in ('1','2'):
            m=(((x.get('holdout') or {}).get('byRR') or {}).get(rr) or {})
            if int(m.get('trades') or 0)<lab.MIN_TRADES:return False
            if float(m.get('winrate') or 0)<=lab.TARGET:return False
            if float(m.get('avgR') or 0)<=0:return False
    return True
lab.strict=strict100

def ai_research(s,failed_rep,dev_feedback=None):
    instruction=(
      'PAPER_ONLY FOREX STRATEGY RESEARCH. Improve the trading method from the failed evidence; never hunt lucky seeds. '
      f'Acceptance is exactly {REQUIRED_DAYS} random OOS trading days per symbol and every symbol must produce at least one entry on EVERY tested day. '
      'Each symbol must independently pass the immutable target; RR1 and RR2 must each have >80% WR, positive avgR and minimum samples. '
      'Allowed strategy families per symbol/RR: TREND_CONTINUATION, MOMENTUM_BREAKOUT, PULLBACK_TREND, MEAN_REVERSION, HYBRID_REGIME. '
      'You may change method, sessions, ATR stop range, minProb/minLocal, trendMin, momentumMin and extensionMax. '
      'Do not remove symbols, lower the target, hide forcedDaily losses, use lookahead, cherry-pick dates or propose live trading. '
      'Return ONE complete profile between FOREX_RESEARCH_BEGIN and FOREX_RESEARCH_END using the project schema. '
      'Use failure clusters, forcedDaily rate, RR asymmetry, session/regime behavior and sample distribution to make a generalizable method change. '
      'If a previous DEV candidate failed, fix that weakness rather than repeat it.' )
    ctx={'currentProfile':s['profile'],'failedOOS':lab.summary(failed_rep),'target':'>80% each symbol each RR',
         'requiredRandomOOSDaysPerSymbol':REQUIRED_DAYS,'minimumEntriesEachSymbolEachDay':1,
         'minimumTradesEachRR':lab.MIN_TRADES,'previousDevRejection':dev_feedback}
    body={'evidence':{'mode':'MULTI_AI_ENGINEERING_TASK','task_id':f'forex-100day-research-{s["round"]}-{int(time.time())}',
                     'instruction':instruction,'context':ctx,'requestedProviders':['claude','codex','deepseek']}}
    req=urllib.request.Request(lab.BRIDGE,data=json.dumps(body).encode(),method='POST',headers={'Authorization':'Bearer '+lab.secret(),'Content-Type':'application/json'})
    last=None
    for a in range(lab.AI_RETRIES):
        try:
            with urllib.request.urlopen(req,timeout=160) as r:result=json.loads(r.read().decode())
            props=[]
            for text in lab.strings(result):
                for m in lab.BLOCK_RE.finditer(text):
                    try:props.append(json.loads(m.group(1)))
                    except:pass
            if props:
                lab.atomic(lab.REVIEWS/f'review-100day-{s["round"]:05d}-{int(time.time())}.json',result)
                return props
            last='no valid FOREX_RESEARCH block'
        except Exception as e:last=f'{type(e).__name__}: {e}'
        time.sleep(min(30,2**a))
    raise RuntimeError('3AI research unavailable: '+str(last))

def final_summary(rep):
    out={'version':'FOREX-100-RANDOM-DAY-FINAL','target':'>80% RR1 and RR2 per symbol','requiredDays':REQUIRED_DAYS,'symbols':{}}
    for sym,x in (rep.get('symbols') or {}).items():
        out['symbols'][sym]={'pass':x.get('pass'),'days':x.get('actualOOSDays'),'daysWithEntry':x.get('daysWithEntry'),
          'forcedDailyDays':x.get('forcedDailyDays'),'RR1':((x.get('holdout') or {}).get('byRR') or {}).get('1'),
          'RR2':((x.get('holdout') or {}).get('byRR') or {}).get('2')}
    return out

def main():
    signal.signal(signal.SIGTERM,handler);signal.signal(signal.SIGINT,handler)
    for p in (lab.STATE_DIR,lab.ROUNDS,lab.REVIEWS,lab.DEV):p.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(lab.LOCK,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.write(fd,str(os.getpid()).encode());os.close(fd)
    except FileExistsError:raise SystemExit('FOREX_RESEARCH_SINGLE_FLIGHT_LOCKED')
    s=lab.load();s['version']='FOREX-RESEARCH-LOOP-4-100-DAYS';s['mode']='PAPER_ONLY';s['requiredRandomDays']=REQUIRED_DAYS;lab.save(s)
    try:
        while not STOP:
            rep,path,p=lab.acceptance(s);s['round']+=1
            passed=strict100(rep)
            rec={'round':s['round'],'seed':rep.get('seed'),'evidence':str(path),'profile':s['profile'],'pass':passed,
                 'score':lab.score(rep),'requiredDays':REQUIRED_DAYS,'at':lab.now(),'stdoutTail':(p.stdout or '')[-1200:]}
            s.setdefault('history',[]).append(rec);s['history']=s['history'][-200:];lab.save(s)
            if passed:
                final=final_summary(rep);final_path=lab.STATE_DIR/'FINAL_100_DAY_REPORT.json';lab.atomic(final_path,final)
                s['status']='TARGET_ACHIEVED_ALL_SYMBOLS';s['finalEvidence']=str(path);s['finalReport']=str(final_path);lab.save(s)
                print('FOREX_TARGET_ACHIEVED_ALL_SYMBOLS',final_path,flush=True);return 0
            feedback=None;approved=None
            for attempt in range(int(os.environ.get('FOREX_MAX_DEV_RESEARCH_ATTEMPTS','8'))):
                s['status']='3AI_RESEARCH';s['researchAttempt']=attempt+1;lab.save(s)
                props=ai_research(s,rep,feedback);candidate=lab.choose_proposal(props,s['profile'])
                if not candidate:
                    feedback={'reason':'NO_VALID_MATERIAL_PROFILE'};continue
                s['status']='DEV_VALIDATION';lab.save(s);ok,dev=lab.dev_validate(candidate,s['profile']);s['lastDev']=dev;lab.save(s)
                if ok:approved=candidate;break
                feedback={'reason':'DEV_REJECTED','metrics':dev,'candidateProfile':candidate};s['status']='DEV_REJECTED_RESEARCH_AGAIN';lab.save(s)
            if approved is None:raise RuntimeError('3AI could not produce a DEV-improving method; refusing seed spin')
            s['previousProfile']=s['profile'];s['profile']=approved;s['status']='NEXT_FRESH_100_DAY_OOS';lab.save(s);time.sleep(lab.PAUSE)
        s['status']='STOPPED';lab.save(s);return 0
    except Exception as e:
        s['status']='BLOCKED';s['lastError']=f'{type(e).__name__}: {e}';lab.save(s);raise
    finally:
        try:lab.LOCK.unlink()
        except:pass
if __name__=='__main__':raise SystemExit(main())
