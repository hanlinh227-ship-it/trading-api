# V6 Telegram-confirmed scalp execution rules

## Principle

The system researches and ranks setups continuously, but a real-money order is reachable only after a Telegram confirmation for one specific, still-valid signal fingerprint. Confirmation is one-time and expires.

## AI decision matrix

Claude = context/regime reviewer. DeepSeek = adversarial failure reviewer. Codex = quantitative/execution verifier.

- LONG / LONG / LONG: eligible if scanner, risk and execution guard agree.
- SHORT / SHORT / SHORT: eligible if scanner, risk and execution guard agree.
- LONG / LONG / WAIT: eligible only when the WAIT reviewer is not expressing an opposite-direction thesis and confidence/quality gates pass.
- SHORT / SHORT / WAIT: same rule.
- LONG / LONG / SHORT: reject.
- SHORT / SHORT / LONG: reject.
- LONG / WAIT / WAIT: reject.
- SHORT / WAIT / WAIT: reject.
- Any reviewer unavailable: reject.
- Any current hard blocker: reject regardless of historical learning score.

## Telegram signal TTL

Scalp signals expire automatically if the user does not inspect them:

- BREAKOUT: 60 seconds.
- MOMENTUM: 75 seconds.
- TREND_PULLBACK: 120 seconds.
- MEAN_REVERSION: 120 seconds.
- Unknown strategy: 90 seconds.

Expired signals never execute. If the market later creates a new valid setup, a new fingerprint and a new Telegram message are generated.

## What happens when CONFIRM is pressed

The click is not an unconditional order command. It initiates a fresh revalidation:

1. Re-run MTF scanner.
2. Re-run Claude, DeepSeek and Codex.
3. Re-run adaptive risk engine.
4. Re-run execution guard.
5. Require the same symbol, direction and strategy as the Telegram message.
6. Require current price not to have moved more than 0.35R from the displayed entry.
7. Require a fresh guard fingerprint.
8. Issue a one-time 30-second execution confirmation.
9. Live executor may consume that confirmation once only.

If any condition fails, no order is sent and a fresh setup must be generated.

## Stale or unattended scenarios

- User never checks Telegram: signal expires, no trade.
- User checks after TTL: EXPIRED, no trade.
- Price already ran toward TP: PRICE_MOVED, no chase.
- Price moved sharply against old entry: PRICE_MOVED, no stale catch-up entry.
- Strategy changed during revalidation: SETUP_CHANGED, no trade.
- Direction changed: reject.
- 3-AI consensus disappeared: NO_LONGER_VALID, no trade.
- Spread/noise/MTF blocker appears: guard rejects.
- Same symbol already has a position: risk engine rejects duplicate exposure.
- Duplicate Telegram button press: one-time state prevents a second execution.

## Real execution protection

After a valid confirmation and only when local LIVE_TRADING and LIVE_ARMED are both enabled:

1. Verify Binance Futures is One-way mode. Hedge mode is blocked by this executor.
2. Set leverage from the approved decision.
3. Submit MARKET entry.
4. Immediately submit server-side STOP_MARKET close-all using MARK_PRICE.
5. Submit server-side TAKE_PROFIT_MARKET TP3 close-all.
6. Submit reduce-only TP1 and TP2 partial orders when their rounded quantities are valid.
7. If protective-order placement fails, issue an emergency reduce-only MARKET close.
8. Mark the Telegram confirmation CONSUMED so it cannot execute again.

Binance USD-M currently routes conditional TP/SL orders through POST /fapi/v1/algoOrder with algoType=CONDITIONAL. STOP_MARKET and TAKE_PROFIT_MARKET support closePosition=true for close-all protection.

## Continuous learning boundary

Learning may adjust ranking within bounded limits after adequate PAPER samples. It cannot bypass current hard blockers, cannot manufacture a Telegram confirmation, and cannot silently authorize a real-money order.
