#!/usr/bin/env python3
"""Integrity guard for the PAPER_ONLY Forex research controller.

Hard guarantees around every DEV/ACCEPTANCE handoff:
- stale latest evidence can never be reused
- subprocess must exit cleanly
- evidence seed/mode/profile/symbol set must match the requested run
- market-data/infrastructure failures are retried, never learned as strategy failures
- legacy pending evidence containing data errors is quarantined before research resumes
- intentional systemd shutdown is translated to InterruptedError for clean STOPPED state
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import forex_research_loop as lab

_original_run = lab.run
MAX_INFRA_RETRIES = 3


def shutting_down():
    m = sys.modules.get('forex_research_loop_v5')
    return bool(getattr(m, 'STOP', False)) if m else False


def evidence_data_errors(rep):
    return {
        sym: str(x.get('dataError'))
        for sym, x in (rep.get('symbols') or {}).items()
        if x.get('dataError')
    }


def validate_evidence(rep, proc, profile, mode, seed):
    tail = (((proc.stderr or '') + '\n' + (proc.stdout or ''))[-2400:])
    if proc.returncode != 0:
        if shutting_down():
            raise InterruptedError('shutdown requested during backtest')
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
        raise RuntimeError(f'evidence symbol set mismatch missing={sorted(expected-symbols)} extra={sorted(symbols-expected)}')
    errors = evidence_data_errors(rep)
    if errors:
        raise RuntimeError('market-data evidence errors: ' + json.dumps(errors, sort_keys=True, separators=(',', ':')))


def guarded_run(profile, mode, seed, start, end, windows, days):
    last = None
    for attempt in range(1, MAX_INFRA_RETRIES + 1):
        if shutting_down():
            raise InterruptedError('shutdown requested before backtest')
        try:
            # A prior partial or successful run must never satisfy this run's evidence check.
            try:
                lab.LATEST.unlink()
            except FileNotFoundError:
                pass
            rep, proc = _original_run(profile, mode, seed, start, end, windows, days)
            validate_evidence(rep, proc, profile, mode, seed)
            if attempt > 1:
                print(f'FOREX_INFRA_RECOVERED attempt={attempt} mode={mode} seed={seed}', flush=True)
            return rep, proc
        except InterruptedError:
            raise
        except Exception as exc:
            last = f'{type(exc).__name__}: {exc}'
            print(f'FOREX_INFRA_RETRY attempt={attempt}/{MAX_INFRA_RETRIES} mode={mode} seed={seed} error={last}', flush=True)
            if attempt < MAX_INFRA_RETRIES:
                time.sleep(min(30, 5 * attempt))
    raise RuntimeError('Forex backtest infrastructure failed after retries: ' + str(last))


lab.run = guarded_run

import forex_research_loop_v5 as controller


def compact_round_report(state):
    """Emit compact immutable evidence diagnostics for the latest rounds into journal."""
    for h in (state.get('history') or [])[-3:]:
        path = Path(str(h.get('evidence') or ''))
        if not path.is_file():
            print(f'FOREX_ROUND_EVIDENCE round={h.get("round")} missing={path}', flush=True)
            continue
        try:
            rep = json.loads(path.read_text())
        except Exception as exc:
            print(f'FOREX_ROUND_EVIDENCE round={h.get("round")} unreadable={type(exc).__name__}:{exc}', flush=True)
            continue
        errs = evidence_data_errors(rep)
        print(f'FOREX_ROUND_EVIDENCE round={h.get("round")} seed={rep.get("seed")} pass={h.get("pass")} dataErrors={len(errs)}', flush=True)
        for sym, x in (rep.get('symbols') or {}).items():
            by = ((x.get('holdout') or {}).get('byRR') or {})
            r1, r2 = by.get('1') or {}, by.get('2') or {}
            print(
                'FOREX_ROUND_SYMBOL '
                f'round={h.get("round")} symbol={sym} days={x.get("actualOOSDays")}/{x.get("requiredOOSDays")} '
                f'RR1_trades={r1.get("trades")} RR1_wr={r1.get("winrate")} RR1_avgR={r1.get("avgR")} '
                f'RR2_trades={r2.get("trades")} RR2_wr={r2.get("winrate")} RR2_avgR={r2.get("avgR")} '
                f'dataError={json.dumps(x.get("dataError"), ensure_ascii=False)}',
                flush=True,
            )


def quarantine_invalid_pending():
    state = lab.load()
    compact_round_report(state)
    pending = state.get('pendingFailedEvidence')
    if not pending:
        return
    path = Path(str(pending))
    if not path.is_file():
        return
    try:
        rep = json.loads(path.read_text())
    except Exception:
        return
    errors = evidence_data_errors(rep)
    if not errors:
        return

    record = {
        'at': lab.now(),
        'evidence': str(path),
        'round': state.get('round'),
        'reason': 'INFRASTRUCTURE_DATA_ERROR_NOT_STRATEGY_FAILURE',
        'dataErrors': errors,
    }
    state.setdefault('quarantinedEvidence', []).append(record)
    state['quarantinedEvidence'] = state['quarantinedEvidence'][-50:]
    for h in state.get('history') or []:
        if str(h.get('evidence')) == str(path):
            h['validForResearch'] = False
            h['invalidReason'] = record['reason']
    state.pop('pendingFailedEvidence', None)
    state.pop('lastResearchFeedback', None)
    state.pop('candidateCount', None)
    state.pop('lastError', None)
    state['researchCycle'] = 0
    state['status'] = 'NEXT_FRESH_100_DAY_OOS'
    lab.save(state)
    print('FOREX_INVALID_EVIDENCE_QUARANTINED ' + json.dumps(record, sort_keys=True, separators=(',', ':')), flush=True)


if __name__ == '__main__':
    quarantine_invalid_pending()
    raise SystemExit(controller.main())
