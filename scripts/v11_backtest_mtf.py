#!/usr/bin/env python3
from __future__ import annotations
# Compatibility loader for the frozen deterministic engine body.
# R4 explicitly mutates the imported module globals before exporting them;
# merely assigning BASE_TF in this wrapper does not affect function.__globals__.
import importlib.util,sys
from pathlib import Path
_HERE=Path(__file__).resolve().parent
_LEGACY=_HERE/'v11_backtest_mtf_engine_r1.py'
if not _LEGACY.exists():
    raise RuntimeError('V11_ENGINE_BODY_MISSING: expected scripts/v11_backtest_mtf_engine_r1.py')
spec=importlib.util.spec_from_file_location('v11_mtf_engine_r1_body',_LEGACY)
_m=importlib.util.module_from_spec(spec);spec.loader.exec_module(_m)
# Earlier accurate crypto research used exact H1 history. Restore H1 as the
# finest practical crypto research base and derive H4/D1/W1 from completed H1.
_m.BASE_TF={'forex':'m5','crypto':'h1','metal':'h1','index':'h1'}
_m.MIN_BARS={'m5':4320,'h1':720,'h4':180}
_m.FEATURE_SCHEMA='v11-mtf-features-r4-h1crypto'
_m.VERSION=str(getattr(_m,'VERSION','V11-MTF-ENGINE-R1'))+'-R4-H1CRYPTO'
for _k in dir(_m):
    if not _k.startswith('__'):globals()[_k]=getattr(_m,_k)
