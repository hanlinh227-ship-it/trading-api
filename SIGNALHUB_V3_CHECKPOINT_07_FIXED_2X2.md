# SignalHub V3 Checkpoint 07 — Fixed 2x2 Crypto Book

- Backend version: SIGNALHUB-V3-GATEWAY-3.15.0
- Crypto only; Forex remains disabled.
- Portfolio target: exactly 2 active SCALP ideas + 2 active SWING ideas whenever live provider data is available.
- Strict confirmed setups are always ranked first.
- If a style is underfilled, best-available conditional coverage is allowed only as LIMIT/STOP, never forced MARKET.
- Conditional coverage still requires hard checks: valid Entry/SL/TP geometry, structural invalidation, live source price, correct pending side, reachable trigger, liquidity, spread and target path.
- One active idea per symbol across styles remains enforced.
- Meme concentration remains capped at one active idea.
- Active API synchronously attempts refill when a style has fewer than 2 ideas.
- Cron/status/monitor maintenance also refill underfilled styles.
- Historical win rate remains closed TP/SL only and is not a predicted probability.

The 2x2 occupancy target is a portfolio availability rule, not a claim that all four ideas have identical conviction. Conditional coverage is explicitly labeled BEST_AVAILABLE_CONDITIONAL.

## V3.15.1 hot-spare refinement
- Durable Object keeps up to 3 prepared pending candidates per style.
- A TP, SL or pending cancellation triggers atomic hot-spare promotion for the depleted style.
- Standbys are not shown as active orders until promoted.
- Cron maintenance refreshes standby pools even while the 2x2 book is full.
- Active reads also perform bounded refill attempts if a race leaves a style temporarily underfilled.

## V3.15.2 reserve-pool hardening
- Standby pools merge and preserve still-valid reserves instead of being erased by an empty scan.
- Any current analyzed setup can be converted into a conditional confirmation STOP reserve when it is not already a pending order.
- Derived reserves are rechecked by V315_FIXED_2X2_HARD_SAFETY before storage or promotion.
- Scanner immediately promotes a reserve after analysis if its style remains under the 2-active target.
- Active signals remain capped at exactly 2 SCALP + 2 SWING; reserve signals are hidden until promotion.
