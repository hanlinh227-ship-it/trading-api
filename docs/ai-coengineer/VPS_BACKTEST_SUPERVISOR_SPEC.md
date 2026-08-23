# V11 VPS Backtest Supervisor — Spec

Status: DESIGN / FAIL-CLOSED

## Objective
Run an autonomous VPS supervisor that continuously evaluates and improves Signal V11 methods per symbol until each symbol has independently proven >=80.00% win rate over the latest ~122 days, using only RR 1:1 or 1:2 and at most 3 valid entries per eligible trading day. The supervisor must never fabricate, pool, or round results upward and must never unlock Telegram by itself.

## Service
- systemd service: `v11-backtest-supervisor.service`
- optional health endpoint bound to localhost only: `127.0.0.1:8791`
- state root: `/var/lib/trading-v11/backtest-supervisor/`
- repo root: `/opt/trading-api`
- logs: journald (`journalctl -u v11-backtest-supervisor`)

## Per-symbol state machine
`PENDING -> DATA_READY -> SEARCHING -> CANDIDATE_FROZEN -> OOS_TEST -> PASS`

Failure/research branches:
`DATA_* -> BLOCKED_DATA`
`SEARCHING -> NEEDS_RESEARCH -> SEARCHING`
`OOS_TEST -> OOS_FAIL -> NEEDS_RESEARCH`

`PASS` is sticky only for the exact evidence window/profile SHA. When the rolling 122-day window materially changes, the symbol must revalidate and can leave PASS.

## Integrity rules
1. Every catalog symbol is tracked independently. No pooled market WR can make a symbol pass.
2. Latest ~122 days of deduplicated M5 OHLC with provider/source/timestamp evidence.
3. Crypto: canonical exchange history; Forex/Metal/Index: canonical mapped provider history. Missing coverage => fail closed.
4. Entry executes on the next M5 bar with adverse cost padding.
5. Same-bar TP+SL => SL.
6. Timeout => non-win.
7. RR exactly 1:1 or 1:2.
8. At most 3 valid entries per eligible day. Do not force trades just to fill 3 slots.
9. Crypto may trade every calendar day. Forex/Metal/Index exclude Saturday and Sunday.
10. Record trades, TP, SL, timeout, days traded, average trades/day, method family, RR, source and evidence SHA for each symbol.
11. Global success only if passCount == totalSymbols and every symbol independently passes all gates.

## Anti-overfit rule
The supervisor may search repeatedly, but it must not repeatedly tune against the same final OOS outcomes.

- Local parameter/method search uses TRAIN/DEV + VALIDATION or nested chronological walk-forward folds.
- A candidate is frozen before final OOS evaluation.
- OOS data is not used to rank parameters within the same generation.
- If a frozen candidate fails OOS, the result is recorded as failure. Subsequent research must use earlier folds / rotated holdout / newly available data rather than directly optimizing to the failed OOS path.
- Therefore the service can keep researching until >=80% is genuinely proven, but cannot guarantee that every symbol will eventually pass.

## Search / research loop
1. Run deterministic local search first using current V11 method families and prior V62/V63/V73/V77/V78 ideas only as priors.
2. If a symbol remains below threshold after the configured local search budget, send a bounded `MULTI_AI_ENGINEERING_TASK` to the local 5-provider bridge at `127.0.0.1:8789/review`.
3. Send only factual per-symbol TRAIN/VALIDATION evidence, current method family, parameter boundaries, failures and integrity constraints.
4. The five providers return proposals only; they do not execute trades or bypass gates.
5. Supervisor accepts only schema-valid proposals inside an allow-listed strategy/config search space. Invalid or conflicting proposals are discarded.
6. Re-run backtest with the new candidate generation.
7. Continue until PASS or remain NEEDS_RESEARCH/BLOCKED. Never mark PASS by removing the symbol or lowering the threshold.

## Resource controls
- configurable worker concurrency, default 4 symbols
- one active supervisor lock via flock/systemd
- cached immutable market-history chunks to avoid redownloading on every iteration
- local search before any paid AI call
- AI research cooldown per symbol to prevent runaway spend
- atomic state/result writes
- graceful restart resumes from state rather than starting over

## Required outputs
- `/var/lib/trading-v11/backtest-supervisor/state.json`
- `/var/lib/trading-v11/backtest-supervisor/results/<SYMBOL>.json`
- repository evidence files when a validated publishing path is available:
  - `data/v11_symbol_backtest_4m.json`
  - `data/v11_backtest_gate.json`
  - `cloudflare-worker/v11/generated-backtest-profiles.js`

## Health status
`GET /health` should expose only operational state, not secrets:
- service ok/state
- current main SHA
- current symbol / queue counts
- passCount / totalSymbols
- blocked count
- research count
- last completed symbol
- last result timestamp
- globalGate (OPEN only when every symbol genuinely passes; this endpoint itself never unlocks Telegram)
