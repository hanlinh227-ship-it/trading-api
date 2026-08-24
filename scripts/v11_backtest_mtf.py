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
_m.FEATURE_SCHEMA=str(_m.FEATURE_SCHEMA)+'-warmup14'
_m.VERSION=str(_m.VERSION)+'-W14'
for _k in dir(_m):
    if not _k.startswith('__'):globals()[_k]=getattr(_m,_k)
