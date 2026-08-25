#!/usr/bin/env python3
"""Runtime bootstrap for the PAPER_ONLY Forex V7 engine.

Applies two narrowly-scoped integrity fixes before executing canonical V7:
1) inject V4 outcome/metrics/index primitives into the extracted V5 function namespace;
2) guarantee enough calendar span per random block to obtain 6 train + 10 OOS trading days,
   including XAU/USD around holidays/weekends.

The exact substitutions are asserted so a future V7 source change fails closed rather than
silently running an unintended transformation.
"""
from pathlib import Path

SOURCE = Path(__file__).with_name('forex_twelvedata_walkforward_v7.py')
src = SOURCE.read_text()

old_bind = "ns.update(features=features,predict=predict,samples_for_day=samples_for_day,cell=cell,method_ok=method_ok,quality=quality,PROFILE=PROFILE)"
new_bind = "ns.update(features=features,predict=predict,samples_for_day=samples_for_day,cell=cell,method_ok=method_ok,quality=quality,outcome=outcome,metrics=metrics,idx_for_hour=idx_for_hour,PROFILE=PROFILE)"
old_blocks = "blocks=random_blocks();report="
new_blocks = "BLOCK_DAYS=max(BLOCK_DAYS,28);blocks=random_blocks();report="

if src.count(old_bind) != 1:
    raise SystemExit(f'VERSION_DRIFT: expected one V7 namespace binding site, found {src.count(old_bind)}')
if src.count(old_blocks) != 1:
    raise SystemExit(f'VERSION_DRIFT: expected one V7 random-block call site, found {src.count(old_blocks)}')

src = src.replace(old_bind, new_bind, 1).replace(old_blocks, new_blocks, 1)
print('FOREX_V7_RUNTIME_FIX=ACTIVE namespace_primitives=PASS min_calendar_block_days=28', flush=True)

g = {'__name__': '__main__', '__file__': str(SOURCE), '__package__': None}
exec(compile(src, str(SOURCE), 'exec'), g, g)
