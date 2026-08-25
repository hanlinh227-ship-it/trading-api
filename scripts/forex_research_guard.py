#!/usr/bin/env python3
"""Integrity guard for the Forex research controller.

Keeps LOOP V5 logic unchanged while hardening every DEV/ACCEPTANCE backtest handoff:
- delete stale latest evidence before a run
- require subprocess exit code 0
- require evidence seed/mode/profile/symbol set to match the requested run

PAPER_ONLY. No execution/trading behavior is changed.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import forex_research_loop as lab

_original_run = lab.run


def guarded_run(profile, mode, seed, start, end, windows, days):
    # The base runner historically accepted any existing latest.json. Remove it first
    # so a failed/timeout subprocess can never reuse evidence from a prior run.
    try:
        lab.LATEST.unlink()
    except FileNotFoundError:
        pass

    rep, proc = _original_run(profile, mode, seed, start, end, windows, days)
    tail = (((proc.stderr or '') + '\n' + (proc.stdout or ''))[-2400:])
    if proc.returncode != 0:
        raise RuntimeError(f'backtest exit={proc.returncode}: {tail}')

    if int(rep.get('seed') or -1) != int(seed):
        raise RuntimeError(f'evidence seed mismatch expected={seed} got={rep.get("seed")}')
    if str(rep.get('mode') or '').upper() != str(mode).upper():
        raise RuntimeError(f'evidence mode mismatch expected={mode} got={rep.get("mode")}')

    if json.dumps(rep.get('strategyProfile') or {}, sort_keys=True, separators=(',', ':')) != json.dumps(profile, sort_keys=True, separators=(',', ':')):
        raise RuntimeError('evidence strategyProfile mismatch')

    symbols = set(rep.get('symbols') or {})
    expected = set(lab.SYMS)
    if symbols != expected:
        raise RuntimeError(
            f'evidence symbol set mismatch missing={sorted(expected-symbols)} extra={sorted(symbols-expected)}'
        )
    return rep, proc


lab.run = guarded_run

import forex_research_loop_v5 as controller

if __name__ == '__main__':
    raise SystemExit(controller.main())
