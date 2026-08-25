# MEME AUTO — THEORETICAL DESIGN CHECKPOINT

Updated: 2026-08-25 UTC+7

## STATUS
- Version: `MEME-AUTO-0.1.0-DESIGN`.
- Chain: Solana.
- State: `DESIGN_ONLY`.
- Wallet: NOT CONNECTED.
- Signing: DISABLED.
- Execution: DISABLED.
- No BUY/SELL route is allowed to submit transactions yet.
- Telegram is integrated only as a read-only design branch inside the Unified Trading Hub.

## PURPOSE
Design the meme-coin decision/risk/exit/learning system as completely as practical before adding wallet credentials, Solana transaction signing, live data subscriptions or Jupiter transaction submission.

## PHILOSOPHY
`CONFIRMED_MOMENTUM_NOT_BLIND_SNIPING`.
The bot must not buy simply because a token is new or pumping. Safety and sellability are hard gates before quality scoring. The desired edge is early-but-confirmed momentum, not first-block sniping.

## TARGET CAPITAL MODEL — $30 START
- Starting capital: $30.
- Reserve: $5.
- Tradable pool: about $25.
- Max simultaneous positions initially: 1.
- Target position: $6.
- Allowed position range: $4–$7.
- Max allocation/token: about 23.5% of wallet equity.
- Spot only; leverage OFF.
- DCA OFF; averaging down OFF; martingale OFF.

## FUTURE DATA / EXECUTION ROLES
Discovery/intelligence design:
- Birdeye new listings / meme screen as primary discovery/intelligence candidate source.
- Birdeye token security, wallet-level holder distribution, holder profile and holder history for safety/ownership/flow intelligence.
- DexScreener may be used as a cross-check/discovery supplement, not execution authority.
- Jupiter is the future executable quote/router layer only after wallet integration.
- Phantom is a user-facing wallet link/view layer; the bot must not depend on UI clicking.

## HARD SAFETY GATE
Safety is evaluated before momentum score and cannot be overridden by AI or learning.
Canonical design thresholds:
- executable SELL route must exist before BUY;
- critical security/mint/freeze risk -> reject;
- liquidity >= $30k; fast-breakout preference >= $50k;
- wallet-level top-10 concentration <=35%;
- dev+insider supply <=8%;
- bundler supply <=12%;
- sniper supply <=18%;
- holder profile required;
- wallet-level distribution required;
- fresh sell quote required.
These thresholds are initial theoretical guards and must later be validated against live/paper samples before execution activation.

## QUALITY SCORE 0–100
Hard safety gates run first. Only safe candidates are scored.
Weights:
- Safety quality 30
- Holder quality 20
- Liquidity quality 15
- Real flow 20
- Momentum/setup quality 15

Thresholds:
- <78: reject
- 78–84: watch
- >=85: entry-quality candidate
- >=92: premium candidate

Future learning may only move the effective entry threshold within 82–92, with no influence before 20 closed samples and full weight only after 100+ samples.

## HOLDER / FLOW INTELLIGENCE
Use wallet-level ownership rather than token-account-only views where possible.
Track labeled cohorts: bundler, sniper, insider, dev, smart_trader.
Penalize concentration, coordinated early buying, insider/dev selling, wash-like concentration and narrow buyer breadth.
Reward healthy holder growth, broad unique buyer participation and smart-trader participation only when not concentrated.

## MEME REGIME ENGINE
Regimes:
- EARLY_DISCOVERY
- MOMENTUM_BUILD
- BREAKOUT_EXPANSION
- HEALTHY_PULLBACK
- EUPHORIA
- DISTRIBUTION
- LIQUIDITY_DECAY

Allowed entry regimes:
- MOMENTUM_BUILD
- BREAKOUT_EXPANSION
- HEALTHY_PULLBACK

Blocked entry regimes:
- EUPHORIA
- DISTRIBUTION
- LIQUIDITY_DECAY

## ENTRY SETUPS
Priority order:
1. `MOMENTUM_RETEST` — preferred full design size.
2. `FRESH_BREAKOUT` — reduced size, requires premium real-flow confirmation.
3. `EARLY_ROTATION` — smaller size, requires especially high safety quality.

No forced trade quota. Continuous scanning does not mean forced ownership.

## FUTURE EXECUTION DESIGN
Future router: Jupiter.
Before BUY:
- fresh executable BUY quote;
- fresh executable SELL quote;
- quote age target <=2.5s;
- target price impact <=1.5%; hard cap 3%;
- target slippage about 1%; hard cap 4%;
- reject if price drifts/chases >2.5% after quote preparation;
- transaction must confirm before state is considered OPEN.
No implementation of signing/submission is allowed in DESIGN_ONLY phase.

## EXIT ENGINE
Normal loss control:
- adaptive Smart CUT design around -8% to -12% depending on flow/volatility;
- hard loss reference 16% for theoretical sizing/validation, recognizing live slippage can exceed it.

Profit path:
- TP1 around +18% -> sell 25%;
- TP2 around +35% -> sell another 25%;
- principal recovery logic then prioritizes recovering original capital when feasible;
- remaining quantity can become volatility-managed runner.

Smart CUT evidence can include momentum collapse, buyer/seller flip, holder-growth stall, dev/insider selling, failed breakout and distribution flow.
Emergency exit bypasses normal confirmation when sell route is lost/deteriorating, liquidity shocks, token security deteriorates, dev dump occurs or exit price impact becomes extreme.

## LEARNING
Memory dimensions:
- token
- launch/source
- token age bucket
- regime
- setup
- liquidity bucket

Metrics:
- net PnL / net R after costs
- MFE / MAE
- hold duration
- entry/exit impact
- fees
- exit reason

Learning may only tune bounded entry score, setup priority, bounded size multiplier and bounded exit profile. It may never change hard safety, wallet authority, max allocation, emergency exit rules or no-martingale policy. Auto-promote remains OFF.

## AI ROLE
AI is not required for execution and may never override deterministic safety or sign transactions. Future optional use is narrative/social-context review only after deterministic gates.

## TELEGRAM HUB
Unified root menu has two top-level buttons:
- `BYBIT` — current LIVE production execution branch.
- `MEME` — DESIGN_ONLY branch.
MEME submenu exposes DESIGN, SAFETY, ENTRY/EXIT, CAPITAL and LEARNING. It must clearly display NO WALLET / NO SIGNING / NO EXECUTION until the dedicated integration phase is explicitly approved and designed.

## NEXT PHASE — NOT YET ACTIVE
Before activating real trading, separately design and validate:
1. Birdeye/DexScreener data adapters and freshness/rate-limit handling.
2. Solana RPC and transaction simulation.
3. Dedicated trading wallet / Phantom linking model without exposing seed phrase to GitHub or chat.
4. Jupiter quote + swap construction, slippage/impact limits and sell-route verification.
5. Paper/shadow mode with historical/live replay and outcome telemetry.
6. Emergency transaction/rpc fallback and failed-sell handling.
7. Explicit production enable gate and independent MEME state namespace.

Do not connect wallet or enable execution merely because this design checkpoint exists.
