#!/usr/bin/env python3
"""PAPER_ONLY Forex research controller V5.

Research model:
- completed failed 100-day OOS evidence is immutable feedback
- Claude/Codex/DeepSeek may keep legacy families OR invent CUSTOM_RULESET DSL logic
- all valid distinct proposals are DEV-tested; best robust improvement wins
- fresh blind 100-day OOS is allowed only after DEV approval
- restart resumes the same failed evidence; no seed spinning
"""
import ast,json,os,signal,time,urllib.request
from pathlib import Path
from collections import Counter
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import forex_research_loop as lab

lab.BACKTEST=lab.REPO/'scripts/forex_twelvedata_walkforward_v7.py'
REQUIRED_DAYS=int(os.environ.get('BACKTEST_REQUIRED_RANDOM_DAYS','100'))
STOP=False
RESEARCH_BACKOFF_MAX=int(os.environ.get('FOREX_RESEARCH_BACKOFF_MAX_SECONDS','120'))
LEGACY={'TREND_CONTINUATION','MOMENTUM_BREAKOUT','PULLBACK_TREND','MEAN_REVERSION','HYBRID_REGIME'}
METHODS=LEGACY|{'CUSTOM_RULESET'}
FEATURES=['t1','t2','m3','m12','m36','rsi','ext','pos','vol','body','bar','hourSin','hourCos','stopNorm','rrNorm',
          'ema8Slope','ema20Slope','atrRegime','compression','wickPressure','rangePosition','impulseRatio','pr','local','edge','rr']
SAFE_FUNCS={'abs','min','max'}
ALLOWED_AST=(ast.Expression,ast.BoolOp,ast.And,ast.Or,ast.UnaryOp,ast.Not,ast.USub,ast.UAdd,ast.BinOp,ast.Add,ast.Sub,ast.Mult,ast.Div,
             ast.Compare,ast.Gt,ast.GtE,ast.Lt,ast.LtE,ast.Eq,ast.NotEq,ast.Name,ast.Load,ast.Constant,ast.Call)

def handler(*_):
    global STOP;STOP=True

def validate_expr(expr):
    if not isinstance(expr,str) or not expr.strip() or len(expr)>700:return False
    try:t=ast.parse(expr,mode='eval')
    except:return False
    for n in ast.walk(t):
        if not isinstance(n,ALLOWED_AST):return False
        if isinstance(n,ast.Name) and n.id not in FEATURES and n.id not in SAFE_FUNCS:return False
        if isinstance(n,ast.Call):
            if not isinstance(n.func,ast.Name) or n.func.id not in SAFE_FUNCS or n.keywords:return False
    return True

def valid_cell(c):
    if not isinstance(c,dict):return None
    method=str(c.get('method','')).upper()
    if method not in METHODS:return None
    try:
        q={'method':method,'minProb':float(c['minProb']),'minLocal':float(c['minLocal']),
           'sessions':sorted(set(int(x) for x in c['sessions'])),'stopMin':float(c['stopMin']),'stopMax':float(c['stopMax']),
           'trendMin':float(c.get('trendMin',.06)),'momentumMin':float(c.get('momentumMin',.02)),'extensionMax':float(c.get('extensionMax',1.35))}
    except:return None
    if not (.50<=q['minProb']<=.96 and .50<=q['minLocal']<=1 and q['sessions'] and all(0<=x<=23 for x in q['sessions']) and
            .6<=q['stopMin']<=q['stopMax']<=3 and -.2<=q['trendMin']<=.6 and -.5<=q['momentumMin']<=.8 and .3<=q['extensionMax']<=3):return None
    if method=='CUSTOM_RULESET':
        entry=c.get('entryExpr');quality=c.get('qualityExpr')
        if not validate_expr(entry) or not validate_expr(quality):return None
        q['entryExpr']=entry.strip();q['qualityExpr']=quality.strip()
    return q

def validate_profile(p,old):
    if not isinstance(p,dict) or not isinstance(p.get('defaults'),dict):return None
    try:version=int(p.get('version',int(old.get('version',1))+1))
    except:return None
    q={'version':version,'defaults':{},'symbols':{}}
    for rr in ('1','2'):
        c=valid_cell(p['defaults'].get(rr))
        if not c:return None
        q['defaults'][rr]=c
    for sym,v in (p.get('symbols') or {}).items():
        if sym not in lab.SYMS or not isinstance(v,dict):continue
        z={}
        for rr in ('1','2'):
            if rr in v:
                c=valid_cell(v[rr])
                if c:z[rr]=c
        if z:q['symbols'][sym]=z
    # material change ignores version-only bumps
    a=json.loads(json.dumps(q));b=json.loads(json.dumps(old));a.pop('version',None);b.pop('version',None)
    if json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True):return None
    return q

def dedupe_profiles(props,old):
    out=[];seen=set()
    for p in props:
        q=validate_profile(p,old)
        if not q:continue
        key=json.dumps({k:v for k,v in q.items() if k!='version'},sort_keys=True,separators=(',',':'))
        if key not in seen:seen.add(key);out.append(q)
    return out

def strict100(rep):
    if not rep.get('pass'):return False
    syms=rep.get('symbols') or {}
    if set(syms)!=set(lab.SYMS):return False
    for x in syms.values():
        if int(x.get('requiredOOSDays') or 0)!=REQUIRED_DAYS:return False
        if int(x.get('actualOOSDays') or 0)!=REQUIRED_DAYS:return False
        if int(x.get('daysWithEntry') or 0)!=REQUIRED_DAYS:return False
        if float(x.get('dailyEntryCoveragePct') or 0)!=100.0 or x.get('dailyEntryPass') is not True:return False
        for rr in ('1','2'):
            m=(((x.get('holdout') or {}).get('byRR') or {}).get(rr) or {})
            if int(m.get('trades') or 0)<lab.MIN_TRADES:return False
            if float(m.get('winrate') or 0)<=lab.TARGET or float(m.get('avgR') or 0)<=0:return False
    return True
lab.strict=strict100

def ai_research(s,failed_rep,dev_feedback=None):
    instruction=(
      'PAPER_ONLY FOREX STRATEGY R&D. Treat the failed OOS evidence as a research dataset. Do NOT merely tune thresholds. '
      'You may retain a built-in family when justified, OR invent a new CUSTOM_RULESET independently for each symbol/RR. '
      'CUSTOM_RULESET entryExpr is a safe boolean expression and qualityExpr is a safe numeric ranking expression. '
      'Available variables: '+','.join(FEATURES)+'. Safe functions: abs,min,max. '
      'Feature meanings: t1=e8-e20 trend side-normalized; t2=e20-e50; m3/m12/m36=side momentum; rsi=side RSI; ext=side distance from EMA20; '
      'pos/rangePosition=side-normalized location in day range; vol=ATR scale; body/bar=bar geometry; ema8Slope/ema20Slope=12-bar side slopes; '
      'atrRegime=current ATR vs recent ATR; compression=recent 12-bar range vs 36-bar range; wickPressure=side wick imbalance; impulseRatio=12-bar impulse/range; '
      'pr=KNN estimated win probability; local=local consensus; edge=pr*(rr+1)-1. '
      'Research hypotheses may include trend acceleration, pullback continuation, volatility compression/expansion, false-break rejection, wick-pressure reversal, '
      'session-specific momentum, regime switching, or hybrids. Use evidence to decide; do not force a predefined family. '
      f'Acceptance remains EXACTLY {REQUIRED_DAYS} random blind OOS days/symbol, >=1 entry every day, RR1 and RR2 each >80% WR, positive avgR and minimum samples. '
      'Never remove symbols, lower target, hide forcedDaily losses, cherry-pick dates, use future outcomes, or generate arbitrary Python. '
      'Return ONE complete profile between FOREX_RESEARCH_BEGIN and FOREX_RESEARCH_END. CELL common fields: '
      '{method,minProb,minLocal,sessions,stopMin,stopMax,trendMin,momentumMin,extensionMax}. '
      'For method CUSTOM_RULESET also require entryExpr and qualityExpr. Built-ins remain TREND_CONTINUATION,MOMENTUM_BREAKOUT,PULLBACK_TREND,MEAN_REVERSION,HYBRID_REGIME. '
      'Make materially different, falsifiable changes targeted at observed failure clusters. If prior DEV failed, explicitly correct that weakness.' )
    ctx={'currentProfile':s['profile'],'failedOOS':lab.summary(failed_rep),'target':'>80% each symbol each RR',
         'requiredRandomOOSDaysPerSymbol':REQUIRED_DAYS,'minimumEntriesEachSymbolEachDay':1,'minimumTradesEachRR':lab.MIN_TRADES,
         'previousDevRejection':dev_feedback,'researchMode':'OPEN_STRATEGY_DSL_SANDBOX'}
    body={'evidence':{'mode':'MULTI_AI_ENGINEERING_TASK','task_id':f'forex-open-rd-{s["round"]}-{int(time.time())}',
                     'instruction':instruction,'context':ctx,'requestedProviders':['claude','codex','deepseek']}}
    req=urllib.request.Request(lab.BRIDGE,data=json.dumps(body).encode(),method='POST',headers={'Authorization':'Bearer '+lab.secret(),'Content-Type':'application/json'})
    last=None
    for a in range(lab.AI_RETRIES):
        if STOP:raise InterruptedError('shutdown requested during 3AI research')
        try:
            with urllib.request.urlopen(req,timeout=160) as r:result=json.loads(r.read().decode())
            props=[]
            for text in lab.strings(result):
                for m in lab.BLOCK_RE.finditer(text):
                    try:props.append(json.loads(m.group(1)))
                    except:pass
            if props:
                lab.atomic(lab.REVIEWS/f'review-open-rd-{s["round"]:05d}-{int(time.time())}.json',result)
                return props
            last='no valid FOREX_RESEARCH block'
        except InterruptedError:raise
        except Exception as e:last=f'{type(e).__name__}: {e}'
        time.sleep(min(30,2**a))
    raise RuntimeError('3AI research unavailable: '+str(last))

def dev_rank_candidates(candidates,baseline):
    """DEV-test every distinct AI proposal and choose the strongest robust improvement."""
    ranked=[]
    for idx,c in enumerate(candidates):
        if STOP:raise InterruptedError('shutdown during DEV ranking')
        ok,dev=lab.dev_validate(c,baseline)
        sc=(dev.get('candidate') or {});sb=(dev.get('baseline') or {})
        # Robust objective: cells passing dominates, then weakest cell proxy/minWR, then meanWR, then sample floor.
        objective=(int(sc.get('passedCells') or 0),float(sc.get('minWR') or 0),float(sc.get('meanWR') or 0),int(sc.get('minTrades') or 0))
        ranked.append({'index':idx,'ok':bool(ok),'objective':objective,'dev':dev,'candidate':c})
    accepted=[x for x in ranked if x['ok']]
    best=max(accepted,key=lambda x:x['objective']) if accepted else None
    return (best['candidate'] if best else None),{'ranked':[{'index':x['index'],'ok':x['ok'],'objective':x['objective'],'dev':x['dev']} for x in ranked],
                                                  'selectedIndex':best['index'] if best else None}

def final_summary(rep):
    out={'version':'FOREX-100-RANDOM-DAY-FINAL-V7','target':'>80% RR1 and RR2 per symbol','requiredDays':REQUIRED_DAYS,'symbols':{}}
    for sym,x in (rep.get('symbols') or {}).items():
        out['symbols'][sym]={'pass':x.get('pass'),'days':x.get('actualOOSDays'),'daysWithEntry':x.get('daysWithEntry'),'forcedDailyDays':x.get('forcedDailyDays'),
          'RR1':((x.get('holdout') or {}).get('byRR') or {}).get('1'),'RR2':((x.get('holdout') or {}).get('byRR') or {}).get('2'),'profiles':x.get('activeProfiles')}
    return out

def load_pending(s):
    p=s.get('pendingFailedEvidence')
    if not p:return None
    path=Path(p)
    if not path.is_file():raise RuntimeError('pending failed evidence missing: '+str(path))
    return json.loads(path.read_text())

def research_until_approved(s,rep):
    feedback=s.get('lastResearchFeedback');cycle=int(s.get('researchCycle') or 0)
    while not STOP:
        cycle+=1;s['researchCycle']=cycle;s['status']='3AI_OPEN_STRATEGY_RESEARCH';lab.save(s)
        try:
            props=ai_research(s,rep,feedback);candidates=dedupe_profiles(props,s['profile'])
            if not candidates:
                feedback={'reason':'NO_VALID_MATERIAL_STRATEGY'};s['lastResearchFeedback']=feedback;lab.save(s)
                time.sleep(min(RESEARCH_BACKOFF_MAX,max(3,cycle*3)));continue
            s['status']='DEV_MULTI_CANDIDATE_VALIDATION';s['candidateCount']=len(candidates);lab.save(s)
            approved,dev=dev_rank_candidates(candidates,s['profile']);s['lastDevTournament']=dev;lab.save(s)
            if approved:
                s.pop('lastResearchFeedback',None);s.pop('candidateCount',None);return approved
            feedback={'reason':'ALL_DEV_CANDIDATES_REJECTED','devTournament':dev}
            s['lastResearchFeedback']=feedback;s['status']='DEV_REJECTED_RESEARCH_AGAIN';lab.save(s)
        except InterruptedError:raise
        except Exception as e:
            feedback={'reason':'RESEARCH_TRANSIENT_ERROR','error':f'{type(e).__name__}: {e}'}
            s['lastResearchFeedback']=feedback;s['status']='3AI_OPEN_STRATEGY_RESEARCH';lab.save(s)
        time.sleep(min(RESEARCH_BACKOFF_MAX,max(3,cycle*3)))
    raise InterruptedError('shutdown requested during research')

def main():
    signal.signal(signal.SIGTERM,handler);signal.signal(signal.SIGINT,handler)
    for p in (lab.STATE_DIR,lab.ROUNDS,lab.REVIEWS,lab.DEV):p.mkdir(parents=True,exist_ok=True)
    try:
        fd=os.open(lab.LOCK,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.write(fd,str(os.getpid()).encode());os.close(fd)
    except FileExistsError:raise SystemExit('FOREX_RESEARCH_SINGLE_FLIGHT_LOCKED')
    s=lab.load();s['version']='FOREX-RESEARCH-LOOP-5-OPEN-DSL';s['engine']='V7_DSL_100_RANDOM_DAYS';s['mode']='PAPER_ONLY';s['requiredRandomDays']=REQUIRED_DAYS;lab.save(s)
    try:
        while not STOP:
            rep=load_pending(s)
            if rep is not None:
                approved=research_until_approved(s,rep);s['previousProfile']=s['profile'];s['profile']=approved
                s.pop('pendingFailedEvidence',None);s.pop('lastError',None);s['researchCycle']=0;s['status']='NEXT_FRESH_100_DAY_OOS';lab.save(s);time.sleep(lab.PAUSE);continue
            rep,path,p=lab.acceptance(s)
            if STOP:break
            s['round']+=1;passed=strict100(rep)
            rec={'round':s['round'],'seed':rep.get('seed'),'evidence':str(path),'profile':s['profile'],'pass':passed,'score':lab.score(rep),
                 'requiredDays':REQUIRED_DAYS,'engine':rep.get('version'),'at':lab.now(),'stdoutTail':(p.stdout or '')[-1200:]}
            s.setdefault('history',[]).append(rec);s['history']=s['history'][-200:];lab.save(s)
            if passed:
                final=final_summary(rep);final_path=lab.STATE_DIR/'FINAL_100_DAY_REPORT.json';lab.atomic(final_path,final)
                s['status']='TARGET_ACHIEVED_ALL_SYMBOLS';s['finalEvidence']=str(path);s['finalReport']=str(final_path);lab.save(s)
                print('FOREX_TARGET_ACHIEVED_ALL_SYMBOLS',final_path,flush=True);return 0
            s['pendingFailedEvidence']=str(path);s['status']='3AI_OPEN_STRATEGY_RESEARCH';s['researchCycle']=0;lab.save(s)
            approved=research_until_approved(s,rep);s['previousProfile']=s['profile'];s['profile']=approved
            s.pop('pendingFailedEvidence',None);s.pop('lastError',None);s['researchCycle']=0;s['status']='NEXT_FRESH_100_DAY_OOS';lab.save(s);time.sleep(lab.PAUSE)
        s['status']='STOPPED';lab.save(s);return 0
    except InterruptedError:
        s['status']='STOPPED';lab.save(s);return 0
    except Exception as e:
        s['status']='BLOCKED';s['lastError']=f'{type(e).__name__}: {e}';lab.save(s);raise
    finally:
        try:lab.LOCK.unlink()
        except:pass
if __name__=='__main__':raise SystemExit(main())
