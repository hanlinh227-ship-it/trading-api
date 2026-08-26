#!/usr/bin/env python3
"""Bounded accelerator for the canonical Forex open-DSL research controller.

This module intentionally does NOT weaken acceptance:
- 11 symbols remain mandatory;
- 100 blind random OOS days/symbol remain mandatory;
- RR1/RR2 >80% WR and positive expectancy remain mandatory;
- no seed spinning, symbol deletion, cherry-picking or infrastructure-as-strategy learning.

It accelerates only the DEV/research side:
1. DEV baseline is evaluated once per tournament instead of once per candidate.
2. Every candidate is replayed on the exact same DEV seed/date contract.
3. Candidate ranking includes minimum/mean expectancy, not only win-rate.
4. 3AI receives compact multi-round memory so research is cumulative rather than stateless.
"""
import json
import os
import time
import urllib.request
from collections import Counter, defaultdict

import forex_research_loop as lab
import forex_research_loop_v5 as base


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


def _robust(rep):
    rows=_cell_rows(rep)
    wr=[r['wr'] for r in rows]; ar=[r['avgR'] for r in rows]; tr=[r['trades'] for r in rows]
    return {
        'passedCells':sum(r['wr']>lab.TARGET and r['avgR']>0 and r['trades']>=lab.MIN_TRADES for r in rows),
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
    weak=[]
    for r in sorted(_cell_rows(failed_rep), key=lambda z:(z['wr'],z['avgR'],z['trades']))[:10]:
        weak.append(r)
    method_counts=Counter()
    for h in hist:
        p=h.get('profile') or {}
        for rr,c in (p.get('defaults') or {}).items():
            method_counts[str((c or {}).get('method') or 'UNKNOWN')]+=1
        for sym,v in (p.get('symbols') or {}).items():
            for rr,c in (v or {}).items():
                method_counts[str((c or {}).get('method') or 'UNKNOWN')]+=1
    return {
        'trajectory':trajectory,
        'currentWeakestCells':weak,
        'methodExposure':dict(method_counts),
        'lastDevTournament':s.get('lastDevTournament'),
        'lastResearchFeedback':s.get('lastResearchFeedback'),
        'quarantinedInfrastructureCount':len(s.get('quarantinedEvidence') or []),
        'principle':'Improve repeated failure clusters; do not react to one lucky/unlucky seed.',
    }


def ai_research(s,failed_rep,dev_feedback=None):
    instruction=(
      'PAPER_ONLY FOREX STRATEGY R&D WITH CUMULATIVE MEMORY. Treat failed OOS evidence and prior-round trajectory as research data. '
      'Do NOT tune to one seed and do NOT merely lower thresholds. You may retain a built-in family when justified, OR invent a new CUSTOM_RULESET independently per symbol/RR. '
      'CUSTOM_RULESET entryExpr is a safe boolean expression and qualityExpr is a safe numeric ranking expression. '
      'Available variables: '+','.join(base.FEATURES)+'. Safe functions: abs,min,max. '
      'Focus on recurring failure clusters across rounds: regime mismatch, session weakness, false breakout, poor pullback location, volatility compression/expansion, wick pressure, '
      'trend acceleration/deceleration, stop geometry, forced-daily quality and RR-specific expectancy. Prefer changes supported by repeated evidence. '
      f'Acceptance is immutable: EXACTLY {base.REQUIRED_DAYS} blind random OOS days/symbol, >=1 entry every day, RR1 and RR2 each >80% WR, positive avgR and minimum samples. '
      'Never remove symbols, lower target, hide forcedDaily losses, cherry-pick dates, use future outcomes, learn from infrastructure errors, or generate arbitrary Python. '
      'Return ONE complete profile between FOREX_RESEARCH_BEGIN and FOREX_RESEARCH_END. CELL fields: '
      '{method,minProb,minLocal,sessions,stopMin,stopMax,trendMin,momentumMin,extensionMax}. '
      'For CUSTOM_RULESET also require entryExpr and qualityExpr. Built-ins remain TREND_CONTINUATION,MOMENTUM_BREAKOUT,PULLBACK_TREND,MEAN_REVERSION,HYBRID_REGIME. '
      'Make a materially different, falsifiable proposal aimed at the weakest repeated cells while preserving cells that already generalize.'
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
        'researchMode':'OPEN_STRATEGY_DSL_SANDBOX_CUMULATIVE_MEMORY',
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


def dev_rank_candidates(candidates,baseline):
    """Run the immutable DEV baseline once, then replay every candidate on the same data contract."""
    common={
        'mode':'DEV','seed':314159265,
        'start':os.environ.get('FOREX_DEV_START','2025-01-06'),
        'end':os.environ.get('FOREX_DEV_END','2025-12-31'),
        'windows':int(os.environ.get('FOREX_DEV_WINDOWS','4')),
        'days':int(os.environ.get('FOREX_DEV_WINDOW_DAYS','20')),
    }
    base_rep,_=lab.run(baseline,common['mode'],common['seed'],common['start'],common['end'],common['windows'],common['days'])
    sb=_robust(base_rep)
    ranked=[]
    for idx,c in enumerate(candidates):
        if base.STOP: raise InterruptedError('shutdown during DEV ranking')
        rep,_=lab.run(c,common['mode'],common['seed'],common['start'],common['end'],common['windows'],common['days'])
        sc=_robust(rep)
        coverage_ok=sc['minTrades']>=max(4,min(lab.MIN_TRADES,sb['minTrades']))
        broad_improvement=(
            sc['passedCells']>sb['passedCells'] or
            (sc['passedCells']==sb['passedCells'] and sc['minWR']>sb['minWR']+0.25) or
            (sc['passedCells']==sb['passedCells'] and sc['meanWR']>sb['meanWR']+0.50 and sc['meanAvgR']>=sb['meanAvgR'])
        )
        expectancy_guard=sc['meanAvgR']>=sb['meanAvgR']-0.03 and sc['minAvgR']>=sb['minAvgR']-0.10
        ok=bool(coverage_ok and broad_improvement and expectancy_guard)
        objective=(sc['passedCells'],sc['minWR'],sc['minAvgR'],sc['meanWR'],sc['meanAvgR'],sc['minTrades'])
        rec={'index':idx,'ok':ok,'objective':objective,'baseline':sb,'candidate':sc,'candidateProfile':c}
        ranked.append(rec)
        lab.atomic(lab.DEV/f'dev-fast-r{int(time.time())}-{idx}.json',rec)
    accepted=[x for x in ranked if x['ok']]
    best=max(accepted,key=lambda x:x['objective']) if accepted else None
    summary={'baselineEvaluations':1,'candidateEvaluations':len(candidates),'savedBaselineReplays':max(0,len(candidates)-1),
             'ranked':[{k:v for k,v in x.items() if k!='candidateProfile'} for x in ranked],
             'selectedIndex':best['index'] if best else None}
    return (best['candidateProfile'] if best else None),summary


# Monkey-patch only bounded research/DEV functions. Acceptance and strict gates stay canonical V5/V7.
base.ai_research=ai_research
base.dev_rank_candidates=dev_rank_candidates


def main():
    return base.main()


if __name__=='__main__':
    raise SystemExit(main())
