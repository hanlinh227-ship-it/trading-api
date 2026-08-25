#!/usr/bin/env python3
"""Runtime bootstrap for the PAPER_ONLY Forex V7 engine.

Integrity guarantees:
1) V5 extracted choose/force_daily functions always receive V4 outcome/metrics/index primitives;
2) random calendar blocks are widened enough to contain 6 train + 10 OOS trading days;
3) patching is idempotent so a future canonical V7 fix does not break deployment;
4) unexpected source drift fails closed before any evidence can be produced.
"""
from pathlib import Path

SOURCE = Path(__file__).with_name('forex_twelvedata_walkforward_v7.py')
src = SOURCE.read_text()

old_bind = "ns.update(features=features,predict=predict,samples_for_day=samples_for_day,cell=cell,method_ok=method_ok,quality=quality,PROFILE=PROFILE)"
new_bind = "ns.update(features=features,predict=predict,samples_for_day=samples_for_day,cell=cell,method_ok=method_ok,quality=quality,outcome=outcome,metrics=metrics,idx_for_hour=idx_for_hour,PROFILE=PROFILE)"
old_blocks = "blocks=random_blocks();report="
new_blocks = "BLOCK_DAYS=max(BLOCK_DAYS,28);blocks=random_blocks();report="

bind_old_count = src.count(old_bind)
bind_new_count = src.count(new_bind)
if bind_old_count == 1 and bind_new_count == 0:
    src = src.replace(old_bind, new_bind, 1)
elif bind_old_count == 0 and bind_new_count == 1:
    pass
else:
    raise SystemExit(
        f'VERSION_DRIFT: V7 namespace binding unexpected old={bind_old_count} new={bind_new_count}'
    )

block_old_count = src.count(old_blocks)
block_new_count = src.count(new_blocks)
if block_old_count == 1 and block_new_count == 0:
    src = src.replace(old_blocks, new_blocks, 1)
elif block_old_count == 0 and block_new_count == 1:
    pass
else:
    raise SystemExit(
        f'VERSION_DRIFT: V7 random-block bootstrap unexpected old={block_old_count} new={block_new_count}'
    )

# Compile before execution so syntax/source-transform failures cannot leave partial evidence.
code = compile(src, str(SOURCE), 'exec')
assert new_bind in src, 'V7_RUNTIME_INTEGRITY: namespace primitives not bound'
assert new_blocks in src, 'V7_RUNTIME_INTEGRITY: calendar block guard not active'
print(
    'FOREX_V7_RUNTIME_FIX=ACTIVE namespace_primitives=PASS min_calendar_block_days=28 source_drift_guard=PASS',
    flush=True,
)

g = {'__name__': '__main__', '__file__': str(SOURCE), '__package__': None}
exec(code, g, g)
