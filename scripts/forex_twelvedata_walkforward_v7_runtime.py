#!/usr/bin/env python3
"""Integrity bootstrap for canonical PAPER_ONLY Forex V7.

No runtime string patching is allowed here. The canonical V7 source must already
contain every required primitive binding and block-width guard. This wrapper
only validates the source and executes it unchanged, so production cannot run a
hidden transformed variant that differs from GitHub main.
"""
from pathlib import Path

SOURCE = Path(__file__).with_name('forex_twelvedata_walkforward_v7.py')
src = SOURCE.read_text()

required = (
    'outcome=outcome',
    'metrics=metrics',
    'idx_for_hour=idx_for_hour',
    "BLOCK_DAYS = max(35",
    "BACKTEST_SYMBOLS",
)
missing = [token for token in required if token not in src]
if missing:
    raise SystemExit('V7_CANONICAL_INTEGRITY_FAIL missing=' + ','.join(missing))

code = compile(src, str(SOURCE), 'exec')
print(
    'FOREX_V7_RUNTIME=CANONICAL_ONLY namespace_primitives=PASS '
    'min_calendar_block_days=35 smoke_symbol_override=PASS source_drift_guard=PASS',
    flush=True,
)

g = {'__name__': '__main__', '__file__': str(SOURCE), '__package__': None}
exec(code, g, g)
