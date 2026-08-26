# Continuous Crypto 50-Day Research Loop

## Objective
Build symbol-specific crypto profiles for the full Breakout prop-firm crypto universe using reproducible historical exchange data.

A symbol may be promoted only when its locked profile demonstrates >=80% win rate under RR 1:1 or RR 1:2 on unseen validation windows.

## Non-negotiable anti-overfit rules
- Never discard failed windows.
- Never keep sampling until a lucky PASS and then report only that PASS.
- Every trial, seed, window, profile version, trade and result is persisted.
- DEV/tuning windows and FINAL validation windows are disjoint.
- FINAL validation is immutable after first evaluation of a profile version.
- Fees, spread/slippage assumptions and funding where relevant must be included.
- No synthetic market evidence.

## Data
Primary research source: Binance historical market data for symbols that map to the Breakout universe.
Persist raw downloaded bars locally on VPS so repeated trials do not depend on chat sessions or repeated network requests.
Default research bars: 1m base bars, resampled deterministically for higher timeframes as required by each symbol profile.

## Universe
The runner MUST load the authoritative Breakout crypto symbol allow-list from project configuration. It MUST NOT silently substitute a Binance-wide universe. Any Breakout symbol without an exact Binance mapping is marked DATA_UNAVAILABLE and must be resolved explicitly.

## Symbol-specific methods
Each symbol owns an independent profile and parameter history. A profile may use its own regime filters, structure logic, volatility filter, entry trigger, session/time filter and exit behavior. Do not force one strategy across all coins.

## RR search
Allowed target RR values are exactly:
- 1:1
- 1:2

Stop loss is structure/volatility-derived first. Target is then derived from the locked RR. A trial may not move SL/TP after seeing the future path.

## Trial unit
One research trial uses a randomly selected contiguous 50-day window. Random selection MUST be seeded and logged.

For each symbol/profile version:
1. Select a 50-day DEV window from the DEV pool.
2. Run deterministic backtest.
3. Persist PASS/FAIL and complete metrics.
4. Research/tune only from DEV evidence.
5. When DEV qualification is met, freeze the profile version.
6. Evaluate it on previously unseen 50-day validation windows.
7. A failed validation returns the symbol to research with a NEW profile version; validation evidence is never erased.

## Promotion gate
Minimum gate for a symbol:
- validation win rate >= 0.80
- RR exactly 1 or 2
- positive expectancy after costs
- minimum trade-count gate configured globally (must not be bypassed to obtain 80% from tiny samples)
- no look-ahead
- no unresolved data gaps
- reproducible from saved seed + profile hash + data hash

Passing one lucky 50-day window is NOT sufficient. The production runner should require multiple unseen validation windows and report aggregate + worst-window metrics.

## Persistent VPS operation
Run as a system service/container with restart policy always/on-failure.
State directory must contain:
- universe.json
- raw-data manifest/hashes
- profiles/<symbol>/<version>.json
- trials.jsonl (append-only)
- trades/<trial-id>.jsonl
- checkpoints/state.json
- reports/current.json
- reports/final.json

Checkpoint after every trial. On restart, resume from checkpoint rather than restarting research.

## Scheduler
Loop continuously over unresolved symbols, prioritizing the symbols furthest from qualification while retaining exploration across all unresolved symbols.
Pseudo-flow:

while unresolved_symbols_exist:
    symbol = scheduler.next()
    profile = researcher.current_or_new_profile(symbol)
    window = sampler.next_random_50d(symbol, profile.version)
    result = backtest(symbol, profile, window, rr in [1, 2])
    ledger.append(result)
    checkpoint.save()
    if dev_gate_met(symbol, profile):
        freeze(profile)
        validate_on_unseen_windows(profile)
        if validation_gate_met(profile):
            promote(profile)
        else:
            create_new_profile_version(symbol)

If all symbols qualify, stop research mutations, write final report and remain in verification mode. Do not mutate a qualified profile merely to inflate its statistics.

## Reporting
Never publish cherry-picked results. Report per symbol:
- profile version/hash
- method summary
- RR
- total DEV windows/trades
- DEV WR/expectancy/max drawdown
- total unseen validation windows/trades
- aggregate validation WR
- worst 50-day validation WR
- expectancy after costs
- PASS/FAIL
- failure reason

Project target is all Breakout symbols PASS. If a symbol cannot honestly reach the target, keep it FAIL/researching rather than fabricating or hiding evidence.
