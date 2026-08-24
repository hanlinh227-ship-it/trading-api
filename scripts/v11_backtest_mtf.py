#!/usr/bin/env python3
from __future__ import annotations
# Research compatibility loader. Production Signal V11 does not import this file.
import importlib.util,inspect,sys
from pathlib import Path
_HERE=Path(__file__).resolve().parent
_ENGINE=_HERE/'v11_backtest_geometry_r4.py'
if not _ENGINE.exists():raise RuntimeError('V11_GEOMETRY_R4_MISSING')
spec=importlib.util.spec_from_file_location('v11_geometry_r4_body',_ENGINE)
_m=importlib.util.module_from_spec(spec);spec.loader.exec_module(_m)
# R4 needs only ATR warm-up for the first deterministic daily candidate. Keeping
# the original 75-H1-bar guard would create artificial zero-execution days at
# the beginning of DEV even though the direct wrapper already owns partition
# warm-up/integrity. Override that one research guard without changing FINAL.
_src=inspect.getsource(_m._candidate_days).replace("if i<75 or not is_market_day", "if i<14 or not is_market_day")
exec(_src,_m.__dict__)
# R7 integrity fix: style search must simulate on the same execution base that
# the selected profile is later evaluated on. R4 searched Forex styles on H1
# but evaluated the frozen candidates on M5, creating a search/evaluation
# geometry mismatch. Crypto/metals/indices remain H1 because their execution
# base is H1. This changes no contract threshold and uses no FINAL evidence.
_search_src=inspect.getsource(_m._search_style)
_search_src=_search_src.replace(
    "h1=frames['h1'];bounds=_research_bounds(h1,market);prior=load_registry_prior(symbol)",
    "h1=frames['h1'];target=frames[BASE_TF[market]];bounds=_research_bounds(h1,market);prior=load_registry_prior(symbol)"
)
_search_src=_search_src.replace("c=_candidate_days(frames,market,st,h1)","c=_candidate_days(frames,market,st,target)")
_search_src=_search_src.replace("d=_style_stats(c,h1,rr,market,bounds['devStart'],bounds['devEnd']);v=_style_stats(c,h1,rr,market,bounds['validationStart'],bounds['validationEnd'])","d=_style_stats(c,target,rr,market,bounds['devStart'],bounds['devEnd']);v=_style_stats(c,target,rr,market,bounds['validationStart'],bounds['validationEnd'])")
exec(_search_src,_m.__dict__)
_m.FEATURE_SCHEMA=str(_m.FEATURE_SCHEMA)+'-warmup14-executionbase-r7'
_m.VERSION=str(_m.VERSION)+'-W14-EXECBASE-R7'
for _k in dir(_m):
    if not _k.startswith('__'):globals()[_k]=getattr(_m,_k)
