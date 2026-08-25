# MASTER TRADING STATE

Updated: 2026-08-25 UTC+7
Purpose: single canonical state for the Trading project.

## CURRENT PRODUCTION AUTHORITY — BYBIT AUTO 1.4.1

GitHub `main` + deployed Cloudflare runtime are authoritative.

Current production contract:
- production execution authority = Bybit Auto LIVE only;
- production Bybit version = `BYBIT-AUTO-1.4.1`;
- Telegram surface = Unified Trading Hub with BYBIT + MEME branches;
- MEME version = `MEME-AUTO-0.1.0-DESIGN` and is DESIGN_ONLY / NO WALLET / NO SIGNING / NO EXECUTION;
- Signal V11 runtime/scheduler on this Worker = OFF;
- private authenticated Bybit transport = `VPS_BYBIT_PRIVATE_PROXY`;
- existing `TRADING_STATE` KV is preserved; never reset it;
- daily profit target = OFF;
- Bybit trading policy = continuous, constrained by safety/risk/capital/adaptive-edge gates.

## VERSIONING
Every Bybit production change increments `BYBIT_AUTO_VERSION`. Source is LIVE only after `/bybit/health` reports the deployed commit revision and readiness is valid.
MEME has an independent version namespace and must not gain wallet/signing/execution authority during DESIGN_ONLY phase.

## VERSION HISTORY
- `BYBIT-AUTO-1.4.1` — Unified Telegram Hub navigation: top-level BYBIT and MEME branches; no change to Bybit execution logic. MEME branch added design-only.
- `BYBIT-AUTO-1.4.0` — Adaptive Edge Engine: deterministic regime classification, bounded per-symbol/per-strategy/per-regime learning, net expectancy after costs, adaptive score threshold 68–85, live rolling correlation/beta-cluster portfolio gate, bounded exit-profile recommendation, no auto-promote.
- `BYBIT-AUTO-1.3.1` — portfolio initial-margin headroom protection for legacy oversized positions.
- `BYBIT-AUTO-1.3.0` — Continuous Capital Allocation with reserve/slot/risk ceilings.
- `BYBIT-AUTO-1.2.8` — Smart CUT multi-signal thesis-invalidation engine.
- `MEME-AUTO-0.1.0-DESIGN` — theoretical Solana meme system specification only; hard safety/holder/flow/regime/entry/exit/capital/learning design, no wallet or execution.

## BYBIT LIVE PIPELINE
`Scheduler -> liquid universe -> deterministic setup -> Regime Engine -> Per-Coin Edge Memory -> Adaptive Threshold -> correlation/beta portfolio gate -> fresh/re-anchor -> Continuous Capital Allocation -> risk + portfolio-margin preflight -> Claude/Codex/DeepSeek final review -> post-AI fresh quote -> LIVE order -> verified SL/TP -> HOLD/BE/LOCK/TRAIL/SMART_CUT -> Telegram -> bounded learning`

## BYBIT ADAPTIVE EDGE ENGINE — CANONICAL
Regimes: `TREND_UP`, `TREND_DOWN`, `RANGE`, `BREAKOUT_EXPANSION`, `HIGH_VOL_CHAOS`, `LOW_VOL_COMPRESSION`.
Rules:
- regime deterministic; AI does not override it;
- learning memory by symbol and symbol+strategy+regime;
- <10 closed samples has zero adaptive influence;
- adaptive score hard-bounded 68–85;
- correlation soft 0.80, hard 0.90 for same-direction exposure;
- exit-learning bounded to `DEFENSIVE`, `BALANCED`, `TREND_RUNNER`;
- auto-promote permanently OFF;
- learning never weakens freshness, SL, RR, capital, risk or protection gates.

## BYBIT CAPITAL / ENTRY / MANAGEMENT
- risk is a ceiling, never a quantity target;
- planned baseline near $50 equity ≈ $1.50 risk / $3 reward;
- max risk/trade 4% equity; total managed open risk 10%;
- max initial-margin budget/new position 20% before buffer;
- reserve target 30%; fee buffer 5%; portfolio IM target 65%;
- leverage cap 5x; max positions 3; max same direction 2;
- `PORTFOLIO_MARGIN_HEADROOM` may block new entries while open/legacy management continues;
- scan every 60s; global new-entry spacing 300s;
- no daily target or trade quota;
- normal management `HOLD -> BREAKEVEN -> PROFIT_LOCK -> TRAIL -> TP/STOP`;
- Smart CUT is exceptional thesis invalidation and always `reduceOnly`;
- 3 consecutive realized losses -> 30-minute new-entry pause, management remains active.

## MEME-AUTO DESIGN — CANONICAL
Checkpoint: `docs/checkpoints/MEME_AUTO_DESIGN_CHECKPOINT.md`.
Current design target:
- Solana spot meme trading, theoretical starting capital $30;
- reserve $5; tradable ≈$25; one position; target $6, range $4–$7;
- no leverage, DCA, averaging down or martingale;
- confirmed momentum, not blind launch sniping;
- hard safety before score: sellability, mint/freeze/security, liquidity, wallet-level concentration and labeled bundler/sniper/insider/dev cohorts;
- theoretical liquidity floor $30k, stronger fast-breakout preference $50k;
- quality score: safety 30 / holder 20 / liquidity 15 / real flow 20 / momentum 15;
- watch 78+, entry 85+, premium 92+;
- regimes: EARLY_DISCOVERY, MOMENTUM_BUILD, BREAKOUT_EXPANSION, HEALTHY_PULLBACK, EUPHORIA, DISTRIBUTION, LIQUIDITY_DECAY;
- entry only in MOMENTUM_BUILD / BREAKOUT_EXPANSION / HEALTHY_PULLBACK;
- setup priority MOMENTUM_RETEST > FRESH_BREAKOUT > EARLY_ROTATION;
- future execution design uses fresh Jupiter BUY+SELL quotes but no signing/submission exists yet;
- Smart CUT, emergency exit, TP1/TP2, principal recovery and volatility runner are defined theoretically;
- bounded learning only; auto-promote OFF; AI cannot override safety or sign transactions.

## TELEGRAM UNIFIED HUB
Root menu has two systems:
- BYBIT — LIVE production controls/telemetry.
- MEME — DESIGN_ONLY telemetry/specification.
MEME must visibly display NO WALLET / NO SIGNING / NO EXECUTION until a dedicated later integration phase is completed.

## PERMANENT INVARIANTS
Never reset state, fabricate live data, bypass freshness/SL/RR/risk/capital/protection gates, exceed Bybit 5x leverage, size up to force a dollar-risk target, resurrect the old 80% single-position margin model, enable adaptive auto-promote, let retired V11 execution compete with Bybit Auto, or give MEME wallet/signing/execution capability during DESIGN_ONLY phase.

## DEPLOYMENT
Canonical workflow: `.github/workflows/deploy-cloudflare-worker.yml`. `npm run check`, Cloudflare deploy and `/bybit/health` revision verification must all pass before declaring a production update LIVE.
