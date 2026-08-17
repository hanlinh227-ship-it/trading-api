# MASTER TRADING STATE

Updated: 2026-08-17 UTC+7
Purpose: canonical handoff/checkpoint for the Trading project.

## Read order — CURRENT MODE
1. `CURRENT_HANDOFF.md`
2. `NO_CUT_INTRADAY_ALLPASS_V73.md`
3. `LIVE_SYMBOL_ANALYSIS_V74.md`
4. `data/nocut_intraday_allpass_v73.json`
5. `scripts/nocut_intraday_method_v73.py`
6. `scripts/live_symbol_analysis_v74.py`

# Canonical architecture
The project now has two separate current layers:

## V73 — frozen forced-daily statistical prior
V73 supersedes V18/V40 for the user's current no-CUT forced-daily research objective.

Hard rules:
- no CUT;
- no discretionary NO TRADE day;
- each symbol must trade minimum 1 and maximum 3 times per eligible day;
- current frozen V73 development maps use exactly 1 trade/day;
- RR only 1:1 or 1:2; current V73 passing maps use RR1:1;
- every Forex pair and Crypto symbol has development WR >=80%;
- TIMEOUT is a non-win;
- same-bar TP+SL is scored as SL conservatively.

V73 development result:
- Forex: **28/28 PASS**, minimum per-pair WR **80.00%**.
- Crypto: **61/61 PASS**, minimum per-coin WR **80.22%**.
- Forex = H1.
- 59 Crypto symbols = H1.
- TON/IP = dedicated 4H methods.
- exact prior state: `data/nocut_intraday_allpass_v73.json`.
- canonical build run: `32032071403`.

Final V73 architecture:
- Forex V64 base + V66 targeted H1 refinement.
- Crypto V69 static passes + V70 observable regime routers + V71 HBAR/TAO + V72 TON/IP.

Last difficult crypto confirmations:
- HBAR 95.60%.
- TAO 96.70%.
- TON 91.21%.
- IP 86.81%.

## V74 — CURRENT LIVE ANALYSIS / EXECUTION PLAYBOOK
V74 is the required layer for any real-time analysis. It reads V73 but does not optimize it.

Canonical files:
- `scripts/live_symbol_analysis_v74.py`
- `docs/checkpoints/LIVE_SYMBOL_ANALYSIS_V74.md`
- `.github/workflows/validate-live-v74.yml`
- validation run `32037184726` = PASS.

Coverage validation:
- 28 Forex + 61 Crypto = **89/89 live playbooks**;
- all 61 Crypto identities explicitly mapped;
- 35/35 Crypto driver profiles covered;
- no Crypto live-context fallback to generic `OTHER`;
- representative smoke tests passed for EURUSD, BTC, LIT, HBAR, WLD, S, XPL.

# V74 live workflow — mandatory order
1. Verify exact instrument/venue and fresh bid/ask/price timestamp.
2. Refresh point-in-time symbol-specific news/context.
3. Establish D1/H4 draw-on-liquidity, trend/regime and premium/discount.
4. Inspect H1 structure and compute only features observable at that timestamp.
5. Load the frozen V73 action/router result without re-optimizing.
6. Treat V73 `signalHourUTC` as an observation anchor, not an automatic market order.
7. Require M15 tradable location: liquidity sweep, breakout-retest, FVG/imbalance retest or clean reclaim.
8. Require M5 close-confirmed MSS/displacement + retest for execution.
9. Put structural SL first; ATR is only a minimum volatility buffer.
10. RR defaults to 1:1. Promote to 1:2 only with >=2.2R clean room after costs, HTF alignment and no opposing HTF liquidity before 2R.
11. Record context, timestamp, spread/slippage, entry and outcome for forward validation.

`DUAL_FADE` is geometry only. Never place both sides blindly. Activate only the side confirmed by live bias + price trigger.

# Symbol-specific context requirement
## Forex
Analyze both currency legs separately.
- USD: Fed/FOMC, CPI/PCE/labor, Treasury yields/DXY, global liquidity/risk.
- EUR: ECB, CPI/PMI, Germany growth/industry, EU fiscal/political risk.
- GBP: BoE, CPI/wages/jobs, GDP/retail, gilt/fiscal risk.
- JPY: BoJ, MoF intervention, CPI/wages, JGB yields/global risk.
- CHF: SNB, CPI, safe-haven/European risk.
- CAD: BoC, CPI/jobs/GDP, WTI, US-Canada differential.
- AUD: RBA, CPI/jobs, China, iron ore/risk.
- NZD: RBNZ, CPI/jobs, China, dairy/commodity/risk.

Session preference is pair-specific: Asia for JPY/AUD/NZD exposure, London for EUR/GBP/CHF, New York for USD/CAD, with London-New York overlap emphasized for USD crosses.

## Crypto
For every symbol use current project identity plus:
- official project/protocol announcements;
- unlock/supply/staking/buyback changes where relevant;
- fresh spot/perp volume, OI/funding, exchange/on-chain/whale flow;
- symbol/BTC relative strength;
- BTC dominance/breadth;
- sector-specific context.

Important current identity mappings:
- LIT = Lighter / Lighter Infrastructure Token, PERP_DEX.
- S = Sonic native token after FTM -> S migration.
- ASTER = Aster perp-DEX.
- XPL = Plasma stablecoin-focused Layer 1.
- HBAR = Hedera enterprise/public-network context.
- NEAR = NEAR chain-abstraction/AI ecosystem context.
- WLD = World/World ID/World Chain + distribution/regulatory context.

The original V73 builder's live-news mapping is deprecated because 28/61 Crypto profiles could fall back to generic `OTHER`. Keep V73 results frozen, but use V74 for live context.

# Live freshness and execution integrity
Before any real signal:
- exact symbol and venue/source verified;
- fresh bid/ask/price and explicit timestamp;
- Forex quote target age <=30 seconds;
- Crypto quote target age <=10 seconds;
- market-open state verified where applicable;
- estimated round-trip spread/slippage target <=0.10R;
- stale data is forbidden.

If exact symbol, fresh price, market-open state or executable spread cannot be verified, return `DATA_BLOCK` rather than fabricate a trade. This is a technical integrity block, not a discretionary NO TRADE call.

# 1–3 trades/day behavior
- Trade #1 = best confirmed setup in the symbol's preferred active window.
- Trade #2 only after #1 is closed or risk neutralized AND a genuinely new liquidity/structure event occurs.
- Trade #3 only in a later independent session/regime with A-grade confirmation; never revenge/averaging.
- After two losses, do not force a third recovery trade; the daily minimum is already satisfied.
- If no A-grade setup appears by the final liquid window, V74 uses a mandatory fallback: frozen V73 prior + H1 close confirmation + M5 pullback/retest at 0.5x normal risk.

The mandatory fallback and trade #2/#3 rules are NEW V74 operational rules and are not included in V73's development WR.

# Integrity classification
**V73 IS EXPOSED DEVELOPMENT ALL-PASS, NOT UNTOUCHED OOS.**
May–Jul 2026 was used to search/refine V73. Do not call its development WR a live/future guarantee.

**V74 IS STRUCTURALLY VALIDATED FOR 89/89 LIVE PLAYBOOK COVERAGE, BUT IS NOT YET STATISTICALLY FORWARD-PROVEN.**
The next quality step is unchanged forward/OOS validation of V73+V74 including real transaction costs, event delays, M15/M5 trigger behavior, mandatory fallback and second/third trades. Do not retune the holdout after seeing it.

# Legacy / comparison modes
The following are research history and must not be mistaken for the current V73+V74 architecture:
- V18 Forex forced-daily CUT-based mode.
- V40 Crypto forced-daily CUT-based mode.
- V15 Forex selective scanner with untouched August evidence.
- V36b Crypto selective scanner with untouched August evidence.

Selective V15/V36b can still be used only if the user explicitly switches back to a selective/NO-TRADE-capable research objective.

## Handoff phrase
`Tiếp tục Trading từ MASTER_TRADING_STATE.md. Current architecture = V73 frozen no-CUT forced-daily prior + V74 live-analysis layer. V73 development: Forex28/28 PASS min80.00%, Crypto61/61 PASS min80.22%, exposed May-Jul only. For LIVE always use live_symbol_analysis_v74.py: exact fresh price, current symbol identity/news, D1-H4-H1 bias, V73 prior/router, M15 location, M5 confirmed trigger, structural SL, RR1 default / RR2 only with clean >=2.2R room, 1-3 independent trades/eligible day. V73 signalHour/DUAL_FADE must never be executed blindly. V74 coverage validator run32037184726 PASS 89/89.`
