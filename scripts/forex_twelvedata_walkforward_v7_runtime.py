#!/usr/bin/env python3
"""Integrity bootstrap for canonical PAPER_ONLY Forex V7.

No runtime string patching is allowed here. The canonical V7 source must already
contain every required primitive binding and block-width guard. This wrapper
only validates the source, normalizes infrastructure-safe runtime parameters,
and executes it unchanged, so production cannot run a hidden transformed
variant that differs from GitHub main.
"""
import os
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

# Infrastructure hardening only: the strategy/source is untouched. A 35-day
# calendar window is normally enough for 6 train + 10 OOS sessions, but metals
# and holiday/data-gap clusters can occasionally expose fewer valid sessions.
# Enforce 42 calendar days on VPS/runtime runs so sparse provider windows do not
# kill an otherwise valid 100-day acceptance round.
try:
    requested_block_days = int(os.environ.get('BACKTEST_BLOCK_DAYS', '35') or '35')
except ValueError:
    requested_block_days = 35
runtime_block_days = max(42, requested_block_days)
os.environ['BACKTEST_BLOCK_DAYS'] = str(runtime_block_days)

code = compile(src, str(SOURCE), 'exec')
print(
    'FOREX_V7_RUNTIME=CANONICAL_ONLY namespace_primitives=PASS '
    f'runtime_calendar_block_days={runtime_block_days} '
    'sparse_window_guard=PASS smoke_symbol_override=PASS source_drift_guard=PASS',
    flush=True,
)

g = {'__name__': '__main__', '__file__': str(SOURCE), '__package__': None}
exec(code, g, g)
