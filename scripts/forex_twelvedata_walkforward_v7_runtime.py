#!/usr/bin/env python3
"""Fail-closed runtime bootstrap for the PAPER_ONLY Forex V7 engine.

The canonical V7 file currently extracts V5 functions into a separate namespace. Those
functions resolve globals from that extracted namespace, so V4 primitives used by V5
(`outcome`, `metrics`, `idx_for_hour`) must be rebound there before `choose`/`make_trade`
can run. This bootstrap applies that narrow repair and guarantees enough calendar span
for 6 train + 10 OOS trading days around weekends/holidays.

This is deliberately fail-closed: if the canonical source changes so the expected repair
sites are no longer present, deployment stops instead of silently executing stale or
partially repaired research code.
"""
from pathlib import Path

SOURCE = Path(__file__).with_name('forex_twelvedata_walkforward_v7.py')
src = SOURCE.read_text()

OLD_BIND = "ns.update(features=features,predict=predict,samples_for_day=samples_for_day,cell=cell,method_ok=method_ok,quality=quality,PROFILE=PROFILE)"
FIXED_BIND = "ns.update(features=features,predict=predict,samples_for_day=samples_for_day,cell=cell,method_ok=method_ok,quality=quality,outcome=outcome,metrics=metrics,idx_for_hour=idx_for_hour,PROFILE=PROFILE)"
OLD_BLOCK_CALL = "blocks=random_blocks();report="
FIXED_BLOCK_CALL = "BLOCK_DAYS=max(BLOCK_DAYS,28);blocks=random_blocks();report="

# Namespace repair. Accept an already-fixed canonical source, otherwise require exactly
# one known unfixed binding site and repair it.
if FIXED_BIND not in src:
    count = src.count(OLD_BIND)
    if count != 1:
        raise SystemExit(f'VERSION_DRIFT: expected one V7 namespace binding site, found {count}')
    src = src.replace(OLD_BIND, FIXED_BIND, 1)

# Calendar-span repair. Accept an already-fixed source; otherwise repair exactly one call.
if FIXED_BLOCK_CALL not in src:
    count = src.count(OLD_BLOCK_CALL)
    if count != 1:
        raise SystemExit(f'VERSION_DRIFT: expected one V7 random-block call site, found {count}')
    src = src.replace(OLD_BLOCK_CALL, FIXED_BLOCK_CALL, 1)

# Preflight the transformed program before touching Twelve Data. This catches syntax drift
# immediately during deployment rather than after a long backtest has started.
compile(src, str(SOURCE), 'exec')
if FIXED_BIND not in src or FIXED_BLOCK_CALL not in src:
    raise SystemExit('V7_RUNTIME_PREFLIGHT_FAILED')

print(
    'FOREX_V7_RUNTIME_FIX=ACTIVE namespace_primitives=PASS '
    'min_calendar_block_days=28 preflight=PASS',
    flush=True,
)

g = {'__name__': '__main__', '__file__': str(SOURCE), '__package__': None}
exec(compile(src, str(SOURCE), 'exec'), g, g)
