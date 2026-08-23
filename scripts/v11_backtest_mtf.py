#!/usr/bin/env python3
from __future__ import annotations
# Compatibility loader: the canonical engine body is preserved below by importing its frozen implementation.
# This file intentionally keeps the same public API while aligning base timeframes with the restored legacy feeds.
import importlib.util,sys
from pathlib import Path
_HERE=Path(__file__).resolve().parent
_LEGACY=_HERE/'v11_backtest_mtf_engine_r1.py'
if not _LEGACY.exists():
    raise RuntimeError('V11_ENGINE_BODY_MISSING: expected scripts/v11_backtest_mtf_engine_r1.py')
spec=importlib.util.spec_from_file_location('v11_mtf_engine_r1_body',_LEGACY);_m=importlib.util.module_from_spec(spec);spec.loader.exec_module(_m)
for _k in dir(_m):
    if not _k.startswith('__'):globals()[_k]=getattr(_m,_k)
BASE_TF={'forex':'m5','crypto':'h4','metal':'h1','index':'h1'}
MIN_BARS={'m5':4320,'h4':900,'h1':1440}
VERSION=str(getattr(_m,'VERSION','V11-MTF-ENGINE-R1'))+'-LEGACYDATA'