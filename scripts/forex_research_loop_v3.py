#!/usr/bin/env python3
"""Strict controller for forex_research_loop.py.
A failed DEV candidate sends its DEV evidence back to the 3-AI council; the old profile is never
re-tested on another acceptance seed merely because a candidate was rejected.
"""
import json,os,signal,sys,time,urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import forex_research_loop as lab

STOP=False

def handler(*_):
    global STOP; STOP=True

def ai_with_feedback(s,failed_rep,dev_feedback=None):
    instruction=(
      'PAPER_ONLY FOREX STRATEGY RESEARCH. Improve the actual trading method from evidence. Do not optimize by seed hunting. '
      'Allowed strategy families per symbol/RR: TREND_CONTINUATION, MOMENTUM_BREAKOUT, PULLBACK_TREND, MEAN_REVERSION, HYBRID_REGIME. '
      'You may alter method, sessions, ATR stop range, minProb/minLocal, trendMin, momentumMin and extensionMax. '
      'Target is immutable: every one of 22 symbol/RR cells must have >80% WR, positive avgR and required sample count on fresh OOS. '
      'Never remove symbols, lower target, use lookahead, hide failures or propose live execution. '
      'Return one complete profile in FOREX_RESEARCH_BEGIN ... FOREX_RESEARCH_END using the schema already defined by the project. '
      'Base changes on failure clusters and generalization. If previous DEV rejected a candidate, explicitly fix the DEV weakness rather than repeating it.' )
    ctx={'currentProfile':s['profile'],'failedOOS':lab.summary(failed_rep),'target':'>80% each symbol each RR','minimumTrades':lab.MIN_TRADES,'previousDevRejection':dev_feedback}
    body={'evidence':{'mode':'MULTI_AI_ENGINEERING_TASK','task_id':f'forex-strategy-research-{s["round"]}-dev-{int(time.time())}','instruction':instruction,'context':ctx,'requestedProviders':['claude','codex','deepseek']}}
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
                lab.atomic(lab.REVIEWS/f'review-{s["round"]:05d}-dev-{int(time.time())}.json',result)
                return props
            last='no valid FOREX_RESEARCH block'
        except Exception as e:last=f'{type(e).__name__}: {e}'
        time.sleep(min(30,2**a))
    raise RuntimeError('3AI research unavailable: '+str(last))

def main():
    signal.signal(signal.SIGTERM,handler);signal.signal(signal.SIGINT,handler)
    for p in (lab.STATE_DIR,lab.ROUNDS,lab.REVIEWS,lab.DEV):p.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(lab.LOCK,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.write(fd,str(os.getpid()).encode());os.close(fd)
    except FileExistsError:raise SystemExit('FOREX_RESEARCH_SINGLE_FLIGHT_LOCKED')
    s=lab.load();s['version']='FOREX-RESEARCH-LOOP-3';s['mode']='PAPER_ONLY';lab.save(s)
    try:
        while not STOP:
            rep,path,p=lab.acceptance(s);s['round']+=1
            rec={'round':s['round'],'seed':rep.get('seed'),'evidence':str(path),'profile':s['profile'],'pass':lab.strict(rep),'score':lab.score(rep),'at':lab.now(),'stdoutTail':(p.stdout or '')[-1000:]}
            s.setdefault('history',[]).append(rec);s['history']=s['history'][-200:];lab.save(s)
            if rec['pass']:
                s['status']='TARGET_ACHIEVED';s['finalEvidence']=str(path);lab.save(s);print('FOREX_TARGET_ACHIEVED',path,flush=True);return 0
            # Research on the SAME failed OOS until a candidate survives DEV. No fresh acceptance seed here.
            dev_feedback=None; approved=None
            for research_attempt in range(int(os.environ.get('FOREX_MAX_DEV_RESEARCH_ATTEMPTS','8'))):
                s['status']='3AI_RESEARCH';s['researchAttempt']=research_attempt+1;lab.save(s)
                props=ai_with_feedback(s,rep,dev_feedback);candidate=lab.choose_proposal(props,s['profile'])
                if not candidate:
                    dev_feedback={'reason':'NO_VALID_MATERIAL_PROFILE'};continue
                s['status']='DEV_VALIDATION';lab.save(s);ok,dev=lab.dev_validate(candidate,s['profile']);s['lastDev']=dev;lab.save(s)
                if ok:
                    approved=candidate;break
                dev_feedback={'reason':'DEV_REJECTED','metrics':dev,'candidateProfile':candidate}
                s['status']='DEV_REJECTED_RESEARCH_AGAIN';lab.save(s)
            if approved is None:
                raise RuntimeError('3AI failed to produce a DEV-improving strategy within bounded research attempts; refusing acceptance seed spin')
            s['previousProfile']=s['profile'];s['profile']=approved;s['status']='NEXT_FRESH_ACCEPTANCE_OOS';lab.save(s);time.sleep(lab.PAUSE)
        s['status']='STOPPED';lab.save(s);return 0
    except Exception as e:
        s['status']='BLOCKED';s['lastError']=f'{type(e).__name__}: {e}';lab.save(s);raise
    finally:
        try:lab.LOCK.unlink()
        except:pass
if __name__=='__main__':raise SystemExit(main())
