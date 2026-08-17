# MASTER TRADING STATE

Updated: 2026-08-17 15:32 UTC+7
Purpose: canonical handoff/checkpoint for continuing the Trading project across new ChatGPT conversations.

## Cross-chat protocol
Read this file first, then `CURRENT_HANDOFF.md`, then `CROSSMARKET_80WR_OFFLINE_AUDIT.md`, then `TRADE_MANAGEMENT_HOURLY_V1.md`, then the market-specific checkpoint. Do not reconstruct strategy state from memory when checkpoints exist. Never promote a method from one lucky sample; never present stale prices as executable live prices.

## Universal rules
- Regime/bias -> macro/news/calendar -> structure -> setup -> execution -> structural SL -> realistic TP -> managed review.
- Indicators must have distinct roles; avoid stacking.
- News/macro/event risk matters before entry and while a trade is active.
- Structure determines invalidation first; ATR is a buffer/normalizer.
- Forced BUY/SELL on every symbol is a research stress test, not automatically a live rule.
- Score direction separately from TP/SL.
- Do not optimize win rate alone; expectancy and RR matter.
- Separate `bias wrong` from `bias right but entry/barrier failed`.
- Never shrink TP just to manufacture a high WR.
- In-sample fitted results must never be presented as held-out validation.
- CUT is excluded from displayed TP/SL win rate by user convention, but CUT count/rate, average CUT R and total managed expectancy MUST always be reported so WR cannot be inflated cosmetically.

## Latest managed-entry research — mandatory context
Canonical protocol: `docs/checkpoints/TRADE_MANAGEMENT_HOURLY_V1.md`.
This is a RESEARCH protocol only. No recurring schedule/automation is active for this test.

Every filled MARKET or LIMIT position is conceptually reviewed at H+1, H+2, H+3... using only information observable at that review: current price, news, economic/event calendar, H1/M15/M5 structure/path, current indicator/factor/regime state, distance to invalidation/target, and original thesis quality. Decision is HOLD or CUT.

Historical limitation: old committed blind JSONs usually store entry-time features and final TP/SL but not complete hour-by-hour price + indicator + point-in-time news/calendar snapshots. Therefore a true historical H+1/H+2 CUT/HOLD validation cannot honestly be reconstructed across all old blocks without missing data. Do not use future/outcome fields to fake an observable CUT decision.

Zero-credit feasibility audit run `32010580143`:
- Forex F8: 248 TP /241 SL baseline = 50.72% WR. To display 80% WR under an impossible oracle that cuts losers only, 179/241 losses (74.27%) must be CUT before SL, leaving 248 TP /62 SL. F8 RR evidence around 1.42–1.45 already fits requested 1.0–1.5 band.
- Crypto recovered 12-date set: 229 TP /411 SL = 35.78% WR. Oracle would need CUT 354/411 losses (86.13%), leaving 229 TP /57 SL = 80.07%. Historical avg RR 1.639 is above the new 1.0–1.5 target and cannot be retroactively re-scored honestly without preserved price paths.
- These are DIAGNOSTIC UPPER BOUNDS, NOT validation.

Promotion target for the new managed-entry track:
- genuinely blind/held-out TP/SL WR >=80%;
- average planned/effective RR 1.0–1.5;
- positive managed expectancy INCLUDING CUT;
- non-trivial sample;
- hourly decisions must use genuinely observable snapshots.

## Previous cross-market 80WR audit
The 2026-08-17 zero-provider-credit audit targeted >=80% WR with average RR >=1.0 using only already committed Forex/Crypto results. Target was NOT validated. Canonical file: `docs/checkpoints/CROSSMARKET_80WR_OFFLINE_AUDIT.md`.
Pre-audit recovery: `docs/checkpoints/archive/2026-08-17_1507_PRE_80WR_OPTIMIZATION.md`, commit `de58e0a0ea2a6054b9c5839736be0efa80d01dce`.

## Forex — current state
Universe: all 28 liquid pairs from USD/EUR/GBP/JPY/CHF/CAD/AUD/NZD.
Frozen research comparator remains F8: EMA20/50, RSI14, ATR14, ADX14 plus 3/6/12/24/72h cross-currency factor coherence, dispersion/rank separation, 8h session state, pair archetype, horizon-matched SL/TP/expiry and bias-vs-barrier diagnostics.

Four consecutive chronological 5-day frozen validation blocks:
- May18–22 MARKET +0.111R;
- May25–29 +0.338R;
- Jun01–05 +0.247R;
- Jun08–12 +0.251R.
Combined 20 days /560 signals: MARKET 489 resolved, 248 TP /241 SL, WR 50.72%, weighted expectancy ~+0.233R. F8 remains the strongest comparator.

Live/research macro profiles by currency remain mandatory: USD Fed/rates/inflation/labour/yields; EUR ECB/inflation/wages/growth; GBP BoE/services CPI/wages/activity; JPY BoJ/JGB/carry/intervention; CHF SNB/risk-off; CAD BoC/oil; AUD RBA/China/commodities; NZD RBNZ/dairy/global rates.

## Crypto / Breakout — current state
No validated forced all-coin engine. Recovered 640 trades/12 dates: 229 wins /411 losses, 35.78% WR, -0.057R, avg RR 1.639. Static/regime selectors did not generalize. Current selection priority remains BTC + market breadth/regime + D1/H4/H1 + 6h/24h/72h momentum + M15/M5 path + genuine fresh order flow/news.

## Practical live analysis design
### Before Forex entry
Fresh exact price; current currency-specific news/macro and economic calendar; F8 factor/archetype; H4/H1 structure; M15 setup; M5 trigger; structural SL; liquidity target; MARKET/LIMIT/NO TRADE.

### Before Crypto entry
Fresh exact price/coverage; BTC + breadth/regime; current macro/risk news and material symbol news; D1/H4/H1; 6/24/72h momentum; M15/M5 anti-chase; structural SL; liquidity target; MARKET/LIMIT/NO TRADE.

### After fill — both markets
Research/live architecture requires H+1/H+2/... review snapshots and HOLD/CUT logic from `TRADE_MANAGEMENT_HOURLY_V1.md`.

## Provider efficiency
Reuse committed data first. Do not open new provider history merely to make historical hourly snapshots look available. Forex provider use, when explicitly allowed later: one M15 series per 28 pairs ≈28 symbol credits/block, derive H1/H4 locally.

## Handoff phrase
`Tiếp tục toàn bộ dự án Trading từ checkpoint GitHub mới nhất. Đọc MASTER_TRADING_STATE.md, CURRENT_HANDOFF.md, CROSSMARKET_80WR_OFFLINE_AUDIT.md và TRADE_MANAGEMENT_HOURLY_V1.md trước. Hourly HOLD/CUT hiện là protocol nghiên cứu; không được nói 80% đã đạt.`
