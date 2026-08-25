# MEME AUTO — THEORETICAL DESIGN CHECKPOINT

Updated: 2026-08-25 UTC+7

## STATUS
- Version: `MEME-AUTO-0.2.0-DESIGN`.
- Chain: Solana.
- State: `DESIGN_ONLY`.
- Wallet: NOT CONNECTED.
- Signing: DISABLED.
- Execution: DISABLED.
- Telegram: read-only MEME branch inside Unified Trading Hub.

## PHILOSOPHY
`CONFIRMED_MOMENTUM_NOT_BLIND_SNIPING`.
Safety and sellability are hard gates before quality scoring. No blind launch sniping, leverage, DCA, averaging down or martingale.

## BALANCE-AWARE CONTINUOUS CAPITAL ALLOCATOR
Starting capital is $30, but $30 is only the initial balance, not a fixed sizing profile. Capital sizing automatically recalculates from current confirmed equity on every future decision.

Canonical rules:
- allocator mode: `BALANCE_AWARE_CONTINUOUS_ALLOCATOR`;
- auto scale with current balance = ON;
- auto de-risk with drawdown = ON;
- minimum operating equity = $20;
- reserve = max($5, 15% of equity);
- hard reserve policy is never consumed to force an entry;
- position size scales up when equity rises and scales down immediately when equity falls;
- safety/security/slippage limits never loosen because balance is larger;
- liquidity capacity can cap position size below the balance-derived target;
- maximum liquidity participation reference = 0.05% of pool liquidity;
- no forced use of full allocation.

### Equity tiers
- <= $50: target 20%, hard allocation cap 23.5%, max 1 position.
- <= $100: target 18%, hard cap 21%, max 1 position.
- <= $250: target 14%, hard cap 18%, max 2 positions.
- <= $500: target 11%, hard cap 15%, max 2 positions.
- <= $1,000: target 8%, hard cap 12%, max 3 positions.
- > $1,000: target 6%, hard cap 10%, max 3 positions.

The percentage intentionally decreases as capital grows so dollar size may grow without linearly increasing portfolio fragility.

### Drawdown de-risking
Measured from peak confirmed equity:
- drawdown <=5%: normal size.
- >5% to 10%: size x0.80.
- >10% to 15%: size x0.60 and reduce position capacity.
- >15%: size x0.40 and effectively return to one-position defensive mode.

The bot may not keep an old larger size after balance falls.

### Setup/quality sizing
- `MOMENTUM_RETEST`: x1.00.
- `FRESH_BREAKOUT`: x0.85.
- `EARLY_ROTATION`: x0.70.
- entry-quality but non-premium candidate: x0.85.
- premium candidate: x1.00.

Final theoretical position size is the minimum of balance-derived target, hard equity cap, available capital after reserve, drawdown-adjusted capacity and liquidity participation cap.

## HARD SAFETY GATE
Before any momentum score:
- executable SELL route must exist before BUY;
- critical mint/freeze/security risk -> reject;
- liquidity >= $30k; fast-breakout preference >= $50k;
- wallet-level top-10 concentration <=35%;
- dev+insider <=8%; bundler <=12%; sniper <=18%;
- wallet-level distribution and holder profile required;
- fresh SELL quote required.

Safety cannot be relaxed by AI, learning or larger account balance.

## QUALITY SCORE
Weights: Safety 30, Holders 20, Liquidity 15, Real Flow 20, Momentum 15.
- <78 reject
- 78–84 watch
- >=85 entry-quality
- >=92 premium
Learning may only move effective entry threshold within 82–92 after sufficient closed samples.

## REGIME / ENTRY
Regimes: EARLY_DISCOVERY, MOMENTUM_BUILD, BREAKOUT_EXPANSION, HEALTHY_PULLBACK, EUPHORIA, DISTRIBUTION, LIQUIDITY_DECAY.
Allowed entry regimes: MOMENTUM_BUILD, BREAKOUT_EXPANSION, HEALTHY_PULLBACK.
Setups: `MOMENTUM_RETEST` > `FRESH_BREAKOUT` > `EARLY_ROTATION`.
No forced trade quota.

## FUTURE EXECUTION DESIGN
Future router: Jupiter. Phantom is only the user wallet/link/view layer.
Before BUY: fresh BUY quote + fresh SELL quote, quote age target <=2.5s, target impact <=1.5%, hard impact cap 3%, target slippage ~1%, hard cap 4%, no chase beyond 2.5% drift, transaction confirmation required before OPEN.
No signing or submission is allowed in DESIGN_ONLY.

## EXIT ENGINE
- Smart CUT design around -8% to -12% depending on flow/volatility.
- hard loss reference 16%.
- TP1 +18% sell 25%.
- TP2 +35% sell another 25%.
- then principal recovery + volatility-managed runner.
Emergency exit for lost/deteriorating sell route, liquidity shock, security deterioration, dev dump or extreme exit impact.

## LEARNING
Memory now also records equity bucket and drawdown bucket in addition to token/source/age/regime/setup/liquidity.
Metrics include net PnL/R, MFE/MAE, hold time, impact, fees, exit reason, equity at entry and position percentage.
Learning may tune only bounded entry score, setup priority, bounded size multiplier and exit profile. It may never modify hard safety, wallet authority, max allocation caps, emergency exit, drawdown de-risking or no-martingale policy. Auto-promote remains OFF.

## TELEGRAM HUB
Top level remains `BYBIT` and `MEME`. BYBIT is current LIVE execution authority. MEME remains DESIGN_ONLY and must visibly state NO WALLET / NO SIGNING / NO EXECUTION.

## NEXT PHASE — NOT ACTIVE
Build data adapters + Paper/Shadow engine first, then Solana RPC simulation, dedicated trading wallet/Phantom link, Jupiter execution, failed-sell fallback and an explicit independent MEME production-enable gate.

Do not connect wallet or enable execution merely because this design checkpoint exists.
