#!/usr/bin/env python3
from __future__ import annotations
# Research compatibility loader. Production Signal V11 does not import this file.
import importlib.util,sys
from pathlib import Path
_HERE=Path(__file__).resolve().parent
_ENGINE=_HERE/'v11_backtest_geometry_r4.py'
if not _ENGINE.exists():
    raise RuntimeError('V11_GEOMETRY_R4_MISSING')
spec=importlib.util.spec_from_file_location('v11_geometry_r4_body',_ENGINE)
_m=importlib.util.module_from_spec(spec);spec.loader.exec_module(_m)
for _k in dir(_m):
    if not _k.startswith('__'):globals()[_k]=getattr(_m,_k)
