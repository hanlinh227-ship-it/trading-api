#!/usr/bin/env python3
from __future__ import annotations
# Research compatibility loader. Production Signal V11 does not import this file.
# V11 FUSION controller: V77/V78 per-symbol priors + V11 deterministic multi-round research.
import importlib.util,inspect,os,sys
from pathlib import Path
_HERE=Path(__file__).resolve().parent
_ENGINE=_HERE/'v11_backtest_geometry_r4.py'
if not _ENGINE.exists():raise RuntimeError('V11_GEOMETRY_R4_MISSING')
spec=importlib.util.spec_from_file_location('v11_geometry_r4_body',_ENGINE)
_m=importlib.util.module_from_spec(spec);spec.loader.exec_module(_m)

FUSION_VERSION='V11-FUSION-V77-V78-5AI-R3'

# Keep the direct-wrapper warm-up integrity fix.
_src=inspect.getsource(_m._candidate_days).replace("if i<75 or not is_market_day", "if i<14 or not is_market_day")
exec(_src,_m.__dict__)

# R17 bounded refinement: keep the R14 inverse families and add a small set of
# deterministic ensemble-side hypotheses built only from already-available H1/H4/D1
# trend and momentum features. These are searched independently per symbol on
# DEV/VALIDATION only. No FINAL values, labels, future bars, contract relaxation,
# symbol pooling, or fabricated executions are introduced.
_base_side=_m._side
_inverse_families=('INV_FAST','INV_MED','INV_SLOW','INV_H1','INV_H4','INV_D1','INV_MOM','INV_SESSION','INV_HYBRID')
_ensemble_families=('VOTE_TREND','VOTE_MOM','VOTE_ALL','REGIME_SWITCH')
_m.FAMILIES=tuple(dict.fromkeys(list(_m.FAMILIES)+list(_inverse_families)+list(_ensemble_families)))
def _sgn(x):
    return 1 if float(x or 0)>=0 else -1
def _fusion_side(f,m):
    f=str(f or '')
    if f.startswith('INV_'):
        return -_base_side(f[4:],m)
    if f=='VOTE_TREND':
        vote=_sgn(m.get('h1'))+_sgn(m.get('h4'))+_sgn(m.get('d1'))
        return 1 if vote>=1 else -1
    if f=='VOTE_MOM':
        vote=_sgn(m.get('g3'))+_sgn(m.get('g6'))+_sgn(m.get('g12'))+_sgn(m.get('g24'))
        if vote==0:return _base_side('MOM',m)
        return 1 if vote>0 else -1
    if f=='VOTE_ALL':
        vote=2*_sgn(m.get('h4'))+2*_sgn(m.get('d1'))+_sgn(m.get('h1'))+_sgn(m.get('g6'))+_sgn(m.get('g24'))+_sgn(m.get('mom'))
        return 1 if vote>=0 else -1
    if f=='REGIME_SWITCH':
        h1=_sgn(m.get('h1'));h4=_sgn(m.get('h4'));d1=_sgn(m.get('d1'))
        # Follow aligned higher-timeframe trend; when H4/D1 disagree, use a
        # bounded mean-reversion hypothesis from distance to H1 EMA20.
        if h4==d1:return h4
        dev=float(m.get('dev') or 0)
        if abs(dev)>=0.35:return -_sgn(dev)
        return h1
    return _base_side(f,m)
_m._side=_fusion_side

# R18 integrity refinement: style search must rank the same execution-day contract
# that the direct wrapper later seals. Earlier rounds ranked only trade WR/meanR and
# could prefer a style with a missing eligible execution day; forex also derived the
# tuning boundaries from H1 while executing on M5. This remains DEV/VALIDATION-only.
def _contract_style_stats(cands,base,rr,market,a,b):
    hold=max(6,int(12*3600/base.seconds));slots=set()
    for k,row in enumerate(base.rows):
        ts=int(row['ts'])
        if not (a<=ts<b) or not _m.is_market_day(ts,market) or k<61:continue
        last=k+hold-1
        if last>=len(base.rows):continue
        if int(base.rows[last]['ts'])+int(base.seconds)<=b:slots.add(k)
    eligible={_m.daykey(base.rows[k]['ts']) for k in slots};by={}
    for c in cands:
        k=int(c.get('i',-1))+1
        if k not in slots:continue
        day=_m.daykey(base.rows[k]['ts']);by.setdefault(day,[]).append(c)
    trades=[];traded=set()
    for day in sorted(eligible):
        arr=sorted(by.get(day,[]),key=lambda x:x.get('score',0),reverse=True)
        if not arr:continue
        z=_m.simulate_trade(base,arr[0],rr,market)
        if z:trades.append(z);traded.add(day)
    n=len(trades);tp=sum(x.get('outcome')=='TP' for x in trades);zero=len(eligible-traded)
    return {'trades':n,'eligibleDays':len(eligible),'coveragePct':100.0*len(traded)/len(eligible) if eligible else 0.0,'zeroExecutionDays':zero,'winRate':100.0*tp/n if n else 0.0,'meanR':_m.statistics.mean([float(x.get('r',0.0)) for x in trades]) if n else -9.0}
def _contract_rank_pair(dev,val):
    return (min(dev.get('coveragePct',0),val.get('coveragePct',0)),-int(dev.get('zeroExecutionDays',10**9))-int(val.get('zeroExecutionDays',10**9)),min(dev.get('winRate',0),val.get('winRate',0)),min(dev.get('meanR',-9),val.get('meanR',-9)),val.get('winRate',0),dev.get('winRate',0))
_m._style_stats=_contract_style_stats
_m._rank_pair=_contract_rank_pair

# Direct research defaults to the widest predeclared bounded DEV/VALIDATION search (round 4).
# The multi-round controller still sets V11_RESEARCH_ROUND explicitly per round.
# FINAL remains sealed and is never inspected or tuned here.
_round=max(0,min(4,int(os.environ.get('V11_RESEARCH_ROUND','4') or 4)))
_search_src=inspect.getsource(_m._search_style)

# Preserve R7 execution-base alignment: search and execution must use the same base.
# R18 also aligns the DEV/VALIDATION day boundaries to that same execution base.
_search_src=_search_src.replace(
    "h1=frames['h1'];bounds=_research_bounds(h1,market);prior=load_registry_prior(symbol)",
    "h1=frames['h1'];target=frames[BASE_TF[market]];bounds=_research_bounds(target,market);prior=load_registry_prior(symbol)"
)
_search_src=_search_src.replace("c=_candidate_days(frames,market,st,h1)","c=_candidate_days(frames,market,st,target)")
_search_src=_search_src.replace(
    "d=_style_stats(c,h1,rr,market,bounds['devStart'],bounds['devEnd']);v=_style_stats(c,h1,rr,market,bounds['validationStart'],bounds['validationEnd'])",
    "d=_style_stats(c,target,rr,market,bounds['devStart'],bounds['devEnd']);v=_style_stats(c,target,rr,market,bounds['validationStart'],bounds['validationEnd'])"
)

# V77/V78 fusion seeding: family/hour/riskATR were already legacy-prior aware in R4.
# Also prioritize the stored per-symbol entryMode and RR before generic alternatives.
_search_src=_search_src.replace(
    "for rr in ALLOWED_RR:",
    "for rr in tuple(dict.fromkeys(([float(prior.get('priorRR'))] if prior.get('priorRR') in (1,1.0,2,2.0) else [])+list(ALLOWED_RR))):"
)
_search_src=_search_src.replace(
    "for mode in ('MKT','PB','BRK','DUAL_FADE','DUAL_BRK'):test({**style,'mode':mode,'expiry':0 if mode=='MKT' else 2,'hold':12 if mode=='MKT' else 10})",
    "legacy_mode=str(prior.get('entryMode') or '').upper();modes=list(dict.fromkeys(([legacy_mode] if legacy_mode in ('MKT','PB','BRK','DUAL_FADE','DUAL_BRK') else [])+['MKT','PB','BRK','DUAL_FADE','DUAL_BRK']));\n    for mode in modes:test({**style,'mode':mode,'expiry':0 if mode=='MKT' else 2,'hold':12 if mode=='MKT' else 10})"
)

if _round>=1:
    _search_src=_search_src.replace("[0,4,8,12,16,20]","list(range(0,24,2))")
    _search_src=_search_src.replace("(.30,.50,.75,1.00,1.25,1.50)","(.20,.30,.40,.50,.60,.75,.90,1.00,1.15,1.30,1.50,1.70)")
    _search_src=_search_src.replace("(.35,.50,.75,1.00,1.25,1.50)","(.25,.35,.45,.50,.60,.75,.90,1.00,1.15,1.30,1.50,1.70)")
if _round>=2:
    _search_src=_search_src.replace("list(range(0,24,2))","list(range(24))")
    _search_src=_search_src.replace("((1,10),(2,10),(2,8),(4,8),(4,6))","((1,10),(1,8),(2,10),(2,8),(2,6),(3,9),(3,6),(4,8),(4,6),(5,6))")
if _round>=3:
    _search_src=_search_src.replace(
        "bo=float(style['offset']);br=float(style['risk']);offs=sorted({round(min(1.7,max(.2,bo+x)),2) for x in (-.15,-.08,0,.08,.15)});risks=sorted({round(min(1.7,max(.2,br+x)),2) for x in (-.15,-.08,0,.08,.15)})",
        "bo=float(style['offset']);br=float(style['risk']);offs=sorted({round(min(2.0,max(.15,bo+x)),2) for x in (-.30,-.20,-.10,-.05,0,.05,.10,.20,.30)});risks=sorted({round(min(2.0,max(.15,br+x)),2) for x in (-.30,-.20,-.10,-.05,0,.05,.10,.20,.30)})"
    )
if _round>=4:
    # Extra bounded family/hour sweep; RR remains exactly 1 or 2 in the base engine.
    _search_src=_search_src.replace("families=tuple(dict.fromkeys(pf+list(FAMILIES)))","families=tuple(dict.fromkeys(list(FAMILIES)+pf))")

# R13 bounded refinement: the base R4 timing loop accidentally pinned MKT to 12h
# regardless of the timing sweep. Explore 4/6/8/10/12h MKT holds on DEV/VALIDATION
# only, while preserving the existing bounded pending-entry timing grid.
_search_src=_search_src.replace(
    "for ex,hold in ((1,10),(1,8),(2,10),(2,8),(2,6),(3,9),(3,6),(4,8),(4,6),(5,6)):test({**style,'expiry':0 if style['mode']=='MKT' else ex,'hold':12 if style['mode']=='MKT' else hold})",
    "for ex,hold in (((0,4),(0,6),(0,8),(0,10),(0,12)) if style['mode']=='MKT' else ((1,10),(1,8),(2,10),(2,8),(2,6),(3,9),(3,6),(4,8),(4,6),(5,6))):test({**style,'expiry':ex,'hold':hold})"
)
_search_src=_search_src.replace(
    "for ex,hold in ((1,10),(2,10),(2,8),(4,8),(4,6)):test({**style,'expiry':0 if style['mode']=='MKT' else ex,'hold':12 if style['mode']=='MKT' else hold})",
    "for ex,hold in (((0,4),(0,6),(0,8),(0,10),(0,12)) if style['mode']=='MKT' else ((1,10),(2,10),(2,8),(4,8),(4,6))):test({**style,'expiry':ex,'hold':hold})"
)

# R16/R17/R18 bounded refinement: choose family/hour jointly with all five predeclared
# entry geometries so ensemble families are evaluated on equal footing. FINAL remains
# sealed; RR, exact-data, execution-count, WR and expectancy gates are unchanged.
_search_src=_search_src.replace(
    "for f in families:\n        for hr in hours:test({**style,'family':f,'hour':hr})",
    "for f in families:\n        for hr in hours:\n            for coarse_mode in ('MKT','PB','BRK','DUAL_FADE','DUAL_BRK'):\n                test({**style,'family':f,'hour':hr,'mode':coarse_mode,'expiry':0 if coarse_mode=='MKT' else 2,'hold':8 if coarse_mode=='MKT' else 10})"
)

exec(_search_src,_m.__dict__)
# Cache identity must change whenever bounded candidate-generation/search behavior changes.
_m.FEATURE_SCHEMA=str(_m.FEATURE_SCHEMA)+f'-fusion-v77v78-priors-warmup14-executionbase-r{_round}-mkt-hold-sweep-v2-inverse-family-r14-joint-all-modes-r16-ensemble-side-r17-contract-rank-r18'
_m.VERSION=str(_m.VERSION)+f'-FUSION-V77V78-R{_round}-MKT-HOLD-SWEEP-V2-INVERSE-FAMILY-R14-JOINT-ALL-MODES-R16-ENSEMBLE-SIDE-R17-CONTRACT-RANK-R18'
for _k in dir(_m):
    if not _k.startswith('__'):globals()[_k]=getattr(_m,_k)
