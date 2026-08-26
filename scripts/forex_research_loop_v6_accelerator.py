#!/usr/bin/env python3
"""Bounded accelerator for the canonical Forex open-DSL research controller.

Acceptance is intentionally untouched:
- all 11 symbols remain mandatory;
- exactly 100 blind random OOS days/symbol remain mandatory;
- RR1/RR2 must each exceed 80% WR with positive expectancy;
- no seed spinning, symbol deletion, cherry-picking or infrastructure-as-strategy learning.

Acceleration applies only before acceptance:
1. 3AI research receives compact multi-round memory instead of acting statelessly.
2. DEV Stage-1 uses one shared baseline and one fixed seed for every proposal.
3. Only the strongest proposals reach a wider Stage-2 on an independent fixed seed.
4. A proposal must improve robustness/expectancy on both DEV seeds before a fresh 100-day OOS round is spent.
"""
import json
import os
import time
import urllib.request
from collections import Counter
from contextlib import contextmanager

import forex_research_loop as lab
import forex_research_loop_v5 as base

STAGE1_SEED = int(os.environ.get('FOREX_DEV_STAGE1_SEED', '314159265'))
STAGE2_SEED = int(os.environ.get('FOREX_DEV_STAGE2_SEED', '271828182'))
STAGE1_BLOCKS = max(3, int(os.environ.get('FOREX_DEV_STAGE1_BLOCKS', '4')))
STAGE1_TEST_DAYS = max(4, int(os.environ.get('FOREX_DEV_STAGE1_TEST_DAYS', '6')))
STAGE2_BLOCKS = max(STAGE1_BLOCKS + 1, int(os.environ.get('FOREX_DEV_STAGE2_BLOCKS', '7')))
STAGE2_TEST_DAYS = max(STAGE1_TEST_DAYS, int(os.environ.get('FOREX_DEV_STAGE2_TEST_DAYS', '8')))
DEV_TRAIN_DAYS = max(4, int(os.environ.get('FOREX_DEV_TRAIN_DAYS', '6')))
DEV_BLOCK_DAYS = max(42, int(os.environ.get('FOREX_DEV_BLOCK_DAYS', '42')))
STAGE2_FINALISTS = max(1, min(2, int(os.environ.get('FOREX_DEV_STAGE2_FINALISTS', '2'))))


def _cell_rows(rep):
    rows=[]
    for sym,x in sorted((rep.get('symbols') or {}).items()):
        for rr in ('1','2'):
            m=(((x.get('holdout') or {}).get('byRR') or {}).get(rr) or {})
            rows.append({
                'symbol':sym,'rr':rr,'trades':int(m.get('trades') or 0),
                'wr':float(m.get('winrate') or 0),'avgR':float(m.get('avgR') or 0),
                'forcedDailyDays':int(x.get('forcedDailyDays') or 0),
                'days':int(x.get('actualOOSDays') or x.get('validOOSTestDays') or 0),
            })
    return rows


def _robust(rep, min_samples=4):
    rows=_cell_rows(rep)
    wr=[r['wr'] for r in rows]; ar=[r['avgR'] for r in rows]; tr=[r['trades'] for r in rows]
    return {
        'passedCells':sum(r['wr']>lab.TARGET and r['avgR']>0 and r['trades']>=min_samples for r in rows),
        'positiveExpectancyCells':sum(r['avgR']>0 and r['trades']>=min_samples for r in rows),
        'cells':len(rows),
        'minWR':min(wr) if wr else 0.0,
        'meanWR':sum(wr)/len(wr) if wr else 0.0,
        'minAvgR':min(ar) if ar else -999.0,
        'meanAvgR':sum(ar)/len(ar) if ar else -999.0,
        'minTrades':min(tr) if tr else 0,
    }


def _research_memory(s, failed_rep):
    hist=(s.get('history') or [])[-16:]
    trajectory=[]
    for h in hist:
        sc=h.get('score') or {}
        trajectory.append({
            'round':h.get('round'),'pass':bool(h.get('pass')),
            'minWR':sc.get('minWR'),'meanWR':sc.get('meanWR'),
            'passedCells':sc.get('passedCells'),'minTrades':sc.get('minTrades'),
        })
    weak=sorted(_cell_rows(failed_rep), key=lambda z:(z['wr'],z['avgR'],z['trades']))[:10]
    method_counts=Counter()
    for h in hist:
        p=h.get('profile') or {}
        for _,c in (p.get('defaults') or {}).items():
            method_counts[str((c or {}).get('method') or 'UNKNOWN')]+=1
        for _,v in (p.get('symbols') or {}).items():
            for _,c in (v or {}).items():
                method_counts[str((c or {}).get('method') or 'UNKNOWN')]+=1
    return {
        'trajectory':trajectory,
        'currentWeakestCells':weak,
        'methodExposure':dict(method_counts),
        'lastDevTournament':s.get('lastDevTournament'),
        'lastResearchFeedback':s.get('lastResearchFeedback'),
        'quarantinedInfrastructureCount':len(s.get('quarantinedEvidence') or []),
        'principle':'Improve repeated failure clusters across rounds; never react to one lucky/unlucky seed.',
    }


def ai_research(s,failed_rep,dev_feedback=None):
    instruction=(
      'PAPER_ONLY FOREX STRATEGY R&D WITH CUMULATIVE MEMORY. Treat failed OOS evidence and prior-round trajectory as research data. '
      'Do NOT tune to one seed and do NOT merely lower thresholds. You may retain a built-in family when justified, OR invent a new CUSTOM_RULESET independently per symbol/RR. '
      'CUSTOM_RULESET entryExpr is a safe boolean expression and qualityExpr is a safe numeric ranking expression. '
      'Available variables: '+','.join(base.FEATURES)+'. Safe functions: abs,min,max. '
      'Focus on recurring failure clusters across rounds: regime mismatch, session weakness, false breakout, poor pullback location, volatility compression/expansion, wick pressure, '
      'trend acceleration/deceleration, stop geometry, forced-daily quality and RR-specific expectancy. Preserve cells that already generalize. '
      f'Acceptance is immutable: EXACTLY {base.REQUIRED_DAYS} blind random OOS days/symbol, >=1 entry every day, RR1 and RR2 each >80% WR, positive avgR and minimum samples. '
      'Never remove symbols, lower target, hide forcedDaily losses, cherry-pick dates, use future outcomes, learn from infrastructure errors, or generate arbitrary Python. '
      'Return ONE complete profile between FOREX_RESEARCH_BEGIN and FOREX_RESEARCH_END. CELL fields: '
      '{method,minProb,minLocal,sessions,stopMin,stopMax,trendMin,momentumMin,extensionMax}. '
      'For CUSTOM_RULESET also require entryExpr and qualityExpr. Built-ins remain TREND_CONTINUATION,MOMENTUM_BREAKOUT,PULLBACK_TREND,MEAN_REVERSION,HYBRID_REGIME. '
      'Make a materially different, falsifiable proposal aimed at the weakest repeated cells.'
    )
    ctx={
        'currentProfile':s['profile'],
        'failedOOS':lab.summary(failed_rep),
        'researchMemory':_research_memory(s,failed_rep),
        'target':'>80% each symbol each RR',
        'requiredRandomOOSDaysPerSymbol':base.REQUIRED_DAYS,
        'minimumEntriesEachSymbolEachDay':1,
        'minimumTradesEachRR':lab.MIN_TRADES,
        'previousDevRejection':dev_feedback,
        'researchMode':'OPEN_STRATEGY_DSL_SANDBOX_CUMULATIVE_MEMORY_TWO_SEED_DEV',
    }
    body={'evidence':{'mode':'MULTI_AI_ENGINEERING_TASK','task_id':f'forex-open-rd-memory-{s["round"]}-{int(time.time())}',
                     'instruction':instruction,'context':ctx,'requestedProviders':['claude','codex','deepseek']}}
    req=urllib.request.Request(lab.BRIDGE,data=json.dumps(body).encode(),method='POST',headers={'Authorization':'Bearer '+lab.secret(),'Content-Type':'application/json'})
    last=None
    for a in range(lab.AI_RETRIES):
        if base.STOP: raise InterruptedError('shutdown requested during 3AI research')
        try:
            with urllib.request.urlopen(req,timeout=160) as r: result=json.loads(r.read().decode())
            props=[]
            for text in lab.strings(result):
                for m in lab.BLOCK_RE.finditer(text):
                    try: props.append(json.loads(m.group(1)))
                    except Exception: pass
            if props:
                lab.atomic(lab.REVIEWS/f'review-memory-rd-{s["round"]:05d}-{int(time.time())}.json',result)
                return props
            last='no valid FOREX_RESEARCH block'
        except InterruptedError: raise
        except Exception as e: last=f'{type(e).__name__}: {e}'
        time.sleep(min(30,2**a))
    raise RuntimeError('3AI research unavailable: '+str(last))


@contextmanager
def _dev_contract(blocks, test_days):
    """Temporarily map the intended DEV geometry to the variables V7 actually consumes."""
    keys={
        'BACKTEST_RANDOM_BLOCKS':str(blocks),
        'BACKTEST_TEST_DAYS_PER_BLOCK':str(test_days),
        'BACKTEST_TRAIN_DAYS_PER_BLOCK':str(DEV_TRAIN_DAYS),
        'BACKTEST_BLOCK_DAYS':str(DEV_BLOCK_DAYS),
        'TWELVEDATA_INTER_REQUEST_SLEEP':os.environ.get('FOREX_DEV_INTER_REQUEST_SLEEP','8.2'),
    }
    old={k:os.environ.get(k) for k in keys}
    os.environ.update(keys)
    try:
        yield
    finally:
        for k,v in old.items():
            if v is None: os.environ.pop(k,None)
            else: os.environ[k]=v


def _run_dev(profile, seed, blocks, test_days):
    start=os.environ.get('FOREX_DEV_START','2025-01-06')
    end=os.environ.get('FOREX_DEV_END','2025-12-31')
    with _dev_contract(blocks,test_days):
        rep,_=lab.run(profile,'DEV',seed,start,end,blocks,DEV_BLOCK_DAYS)
    expected=blocks*test_days
    for sym,x in (rep.get('symbols') or {}).items():
        if x.get('dataError'):
            raise RuntimeError(f'DEV dataError {sym}: {x.get("dataError")}')
        if int(x.get('actualOOSDays') or 0)!=expected:
            raise RuntimeError(f'DEV day contract mismatch {sym}: got={x.get("actualOOSDays")} expected={expected}')
    return rep


def _improves(sc,sb,min_samples):
    coverage_ok=sc['minTrades']>=max(min_samples,min(sb['minTrades'],lab.MIN_TRADES))
    broad=(
        sc['passedCells']>sb['passedCells'] or
        sc['positiveExpectancyCells']>sb['positiveExpectancyCells'] or
        (sc['passedCells']==sb['passedCells'] and sc['minWR']>sb['minWR']+0.25) or
        (sc['passedCells']==sb['passedCells'] and sc['meanWR']>sb['meanWR']+0.50 and sc['meanAvgR']>=sb['meanAvgR'])
    )
    expectancy=sc['meanAvgR']>=sb['meanAvgR']-0.03 and sc['minAvgR']>=sb['minAvgR']-0.12
    return bool(coverage_ok and broad and expectancy)


def _objective(sc):
    return (sc['passedCells'],sc['positiveExpectancyCells'],sc['minWR'],sc['minAvgR'],sc['meanWR'],sc['meanAvgR'],sc['minTrades'])


def dev_rank_candidates(candidates,baseline):
    """Progressive deterministic two-seed DEV tournament; acceptance remains full 100-day V7."""
    # Stage 1: cheap common-seed discrimination. Baseline is evaluated once, not once/candidate.
    b1=_run_dev(baseline,STAGE1_SEED,STAGE1_BLOCKS,STAGE1_TEST_DAYS)
    min1=max(4,min(8,(STAGE1_BLOCKS*STAGE1_TEST_DAYS)//3))
    sb1=_robust(b1,min1)
    stage1=[]
    for idx,c in enumerate(candidates):
        if base.STOP: raise InterruptedError('shutdown during DEV stage 1')
        rep=_run_dev(c,STAGE1_SEED,STAGE1_BLOCKS,STAGE1_TEST_DAYS)
        sc=_robust(rep,min1)
        ok=_improves(sc,sb1,min1)
        stage1.append({'index':idx,'ok':ok,'objective':_objective(sc),'baseline':sb1,'candidate':sc,'candidateProfile':c})
    survivors=sorted((x for x in stage1 if x['ok']),key=lambda x:x['objective'],reverse=True)[:STAGE2_FINALISTS]
    if not survivors:
        summary={'mode':'PROGRESSIVE_TWO_SEED_DEV','stage1DaysPerSymbol':STAGE1_BLOCKS*STAGE1_TEST_DAYS,
                 'stage2DaysPerSymbol':STAGE2_BLOCKS*STAGE2_TEST_DAYS,'stage1':[{k:v for k,v in x.items() if k!='candidateProfile'} for x in stage1],
                 'stage2':[],'selectedIndex':None,'acceptanceDaysUnchanged':base.REQUIRED_DAYS}
        lab.atomic(lab.DEV/f'dev-progressive-{int(time.time())}.json',summary)
        return None,summary

    # Stage 2: independent fixed seed and wider sample. This is a generalization gate, not tuning data.
    b2=_run_dev(baseline,STAGE2_SEED,STAGE2_BLOCKS,STAGE2_TEST_DAYS)
    min2=max(6,min(lab.MIN_TRADES,(STAGE2_BLOCKS*STAGE2_TEST_DAYS)//3))
    sb2=_robust(b2,min2)
    stage2=[]
    for x in survivors:
        if base.STOP: raise InterruptedError('shutdown during DEV stage 2')
        rep=_run_dev(x['candidateProfile'],STAGE2_SEED,STAGE2_BLOCKS,STAGE2_TEST_DAYS)
        sc=_robust(rep,min2)
        ok=_improves(sc,sb2,min2)
        stage2.append({'index':x['index'],'ok':ok,'objective':_objective(sc),'baseline':sb2,'candidate':sc,'candidateProfile':x['candidateProfile']})
    accepted=[x for x in stage2 if x['ok']]
    best=max(accepted,key=lambda x:x['objective']) if accepted else None
    summary={
        'mode':'PROGRESSIVE_TWO_SEED_DEV',
        'stage1':[{k:v for k,v in x.items() if k!='candidateProfile'} for x in stage1],
        'stage2':[{k:v for k,v in x.items() if k!='candidateProfile'} for x in stage2],
        'stage1DaysPerSymbol':STAGE1_BLOCKS*STAGE1_TEST_DAYS,
        'stage2DaysPerSymbol':STAGE2_BLOCKS*STAGE2_TEST_DAYS,
        'baselineEvaluations':2,
        'candidateStage1Evaluations':len(candidates),
        'candidateStage2Evaluations':len(stage2),
        'selectedIndex':best['index'] if best else None,
        'acceptanceDaysUnchanged':base.REQUIRED_DAYS,
        'integrity':'FIXED_SEEDS_NO_SEED_SPIN_NO_ACCEPTANCE_WEAKENING',
    }
    lab.atomic(lab.DEV/f'dev-progressive-{int(time.time())}.json',summary)
    return (best['candidateProfile'] if best else None),summary


# Monkey-patch bounded research/DEV functions only. strict100(), acceptance() and V7 evidence stay canonical.
base.ai_research=ai_research
base.dev_rank_candidates=dev_rank_candidates


def main():
    return base.main()


if __name__=='__main__':
    raise SystemExit(main())
