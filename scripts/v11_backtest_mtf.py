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

FUSION_VERSION='V11-FUSION-V77-V78-5AI-R1'

# Keep the direct-wrapper warm-up integrity fix.
_src=inspect.getsource(_m._candidate_days).replace("if i<75 or not is_market_day", "if i<14 or not is_market_day")
exec(_src,_m.__dict__)

# Round 0 starts from the proven legacy per-symbol priors. Later rounds only expand
# predeclared DEV/VALIDATION search space; FINAL is never inspected or tuned here.
_round=max(0,min(4,int(os.environ.get('V11_RESEARCH_ROUND','0') or 0)))
_search_src=inspect.getsource(_m._search_style)

# Preserve R7 execution-base alignment: search and execution must use the same base.
_search_src=_search_src.replace(
    "h1=frames['h1'];bounds=_research_bounds(h1,market);prior=load_registry_prior(symbol)",
    "h1=frames['h1'];target=frames[BASE_TF[market]];bounds=_research_bounds(h1,market);prior=load_registry_prior(symbol)"
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

exec(_search_src,_m.__dict__)
_m.FEATURE_SCHEMA=str(_m.FEATURE_SCHEMA)+f'-fusion-v77v78-priors-warmup14-executionbase-r{_round}'
_m.VERSION=str(_m.VERSION)+f'-FUSION-V77V78-R{_round}'
for _k in dir(_m):
    if not _k.startswith('__'):globals()[_k]=getattr(_m,_k)
