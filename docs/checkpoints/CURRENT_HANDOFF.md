# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-17 UTC+7

Read `MASTER_TRADING_STATE.md` first, then `NO_CUT_INTRADAY_ALLPASS_V73.md`, then `LIVE_SYMBOL_ANALYSIS_V74.md`, then `TWELVEDATA_GROW55_DATA_POLICY.md`.

# CURRENT STRUCTURE
Two layers are now canonical and must not be conflated:

1. **V73 = frozen forced-daily statistical/backtest prior.**
2. **V74 = current live-analysis / execution playbook layered on V73.**

Do NOT execute V73 clock/geometry blindly in live trading. Use V74 for every live symbol analysis.

# USER-REQUIRED HARD RULES
- no CUT;
- no discretionary NO TRADE day;
- 1–3 trades per Forex pair / Crypto symbol per eligible day;
- V73 frozen development maps currently use exactly 1/day;
- RR only 1:1 or 1:2; V73 passing development methods use RR1:1;
- per-symbol development WR target >=80%;
- TIMEOUT is non-win;
- same-bar TP+SL = SL conservatively in backtest;
- every symbol must have its own entry prior and its own live news/context.

# V73 COMPLETED DEVELOPMENT TARGET
## Forex
- **28/28 PASS**.
- Minimum individual WR: **80.00%**.
- H1 methods.
- V64 base + V66 targeted refinement.

## Crypto
- **61/61 PASS**.
- Minimum individual WR: **80.22%**.
- 59 symbols use H1.
- HBAR and TAO use V71 special H1 routers.
- TON and IP use V72 dedicated 4H routers.
- HBAR 95.60%; TAO 96.70%; TON 91.21%; IP 86.81%.

V73 canonical state:
- `data/nocut_intraday_allpass_v73.json`
- `scripts/nocut_intraday_method_v73.py`
- `scripts/validate_nocut_v73.py`
- `.github/workflows/validate-nocut-v73.yml`
- `.github/workflows/build-nocut-allpass-v73.yml`
- canonical build run `32032071403`.

# V74 CURRENT LIVE ANALYSIS METHOD
Canonical implementation:
- `scripts/live_symbol_analysis_v74.py`
- `docs/checkpoints/LIVE_SYMBOL_ANALYSIS_V74.md`
- `.github/workflows/validate-live-v74.yml`
- validation run `32037184726` PASS.

Validation result:
- 28 Forex + 61 Crypto = **89/89 live playbooks**;
- 61 Crypto identities explicitly mapped;
- 35/35 Crypto profile-driver groups covered;
- no live `OTHER` driver fallback;
- smoke-tested EURUSD, BTC, LIT, HBAR, WLD, S and XPL.

## Critical V74 changes versus raw V73 execution
- V73 `signalHourUTC` = preferred observation anchor only, NOT automatic entry time.
- V73 family = setup-archetype prior, NOT a standalone signal.
- V73 `entryMode` = geometry prior. `DUAL_FADE` never means blindly place both sides.
- Direction/setup must be confirmed D1 -> H4 -> H1, then M15 location + M5 close-confirmed MSS/displacement/retest.
- structural SL first; ATR is only a volatility floor.
- RR default 1:1; promote to 1:2 only with >=2.2R clean structural/liquidity room after costs, HTF alignment and no opposing level before 2R.
- trade #2/#3 require independent later liquidity/session setups; never revenge or averaging.
- if no A-grade setup by the final liquid window, V74 uses a mandatory fallback: V73 prior + H1 close confirmation + M5 pullback/retest at 0.5x normal risk.

# LIVE DATA INTEGRITY
Before any signal:
- exact symbol/instrument/venue verified;
- fresh bid/ask/price and timestamp;
- Forex target quote age <=30s; Crypto <=10s;
- market-open status verified where applicable;
- spread/slippage estimated; target round-trip cost <=0.10R;
- stale data is forbidden.

If exact symbol, fresh price, market-open state or executable spread cannot be verified, return `DATA_BLOCK`. This is a technical integrity failure, not discretionary NO TRADE; never fabricate a live price/order to satisfy the daily-trade rule.

# TWELVE DATA GROW 55 — ACTIVE DATA POLICY
The user upgraded the connected Twelve Data account to **Grow 55** on 2026-08-17.

Canonical policy:
- `docs/checkpoints/TWELVEDATA_GROW55_DATA_POLICY.md`

Operational rules:
- 55 API credits/minute, reset each minute, paid plan has no daily API limit;
- Grow has only 8 trial WebSocket credits, so REST remains the main integration path;
- maximize information per credit, not raw request count;
- compute indicators locally from OHLC whenever possible;
- Forex scanner now uses staged Grow 55 allocation instead of Basic-plan fixed waits;
- normal Forex budget: ~28 broad scan + ~15 Top-3 D1/H4/H1/M15/M5 + ~3 Top-3 refresh = ~46 credits, with ~9-credit reserve;
- `.github/workflows/scan-forex.yml` is upgraded accordingly;
- routine `sleep 65` after every 7 Forex pairs is deprecated;
- Crypto live execution remains exchange-native first (Binance/OKX/Bybit), with Twelve Data as enrichment/cross-check where useful;
- futures/commodities may use Twelve Data only after exact contract/instrument verification;
- cash indices must use actual cash-index instruments and must never silently proxy NQ/ES futures;
- metals remain a separate structure-first module and spot/futures identity must not be conflated.

More available quota does NOT relax freshness, symbol identity, venue identity, V74 M15/M5 confirmation or `DATA_BLOCK` rules.

# NEWS / CONTEXT — USE V74, NOT V73 NEWS PROFILE
The original V73 builder had profile-name mismatch that caused **28/61 Crypto symbols to fall back to generic `OTHER` drivers**. V73 results remain frozen, but its newsProfile is deprecated for live analysis.

V74 explicitly maps all 61 current Crypto identities and 35 live driver profiles.
Important fixes:
- LIT = Lighter / Lighter Infrastructure Token, profile PERP_DEX; not legacy Litentry identity.
- S = Sonic native token after FTM -> S migration.
- ASTER = Aster perp-DEX ecosystem.
- XPL = Plasma stablecoin-focused Layer 1.
- HBAR = Hedera enterprise/public-network context.
- NEAR = NEAR chain-abstraction/AI ecosystem context.
- WLD = World/World ID/World Chain + token-distribution/regulatory context.

Forex continues to score both currency legs independently using central banks, inflation/jobs/growth, rates/yields/DXY/commodity/risk context as relevant.

# INTEGRITY CLASSIFICATION
**V73 = EXPOSED DEVELOPMENT ALL-PASS, NOT UNTOUCHED OOS.**
**V74 = LIVE OPERATIONAL PLAYBOOK LAYER, VALIDATED FOR STRUCTURAL COVERAGE BUT NOT YET STATISTICALLY FORWARD-PROVEN.**

May–Jul 2026 was used to develop/refine V73. V74's M15/M5 confirmation, transaction-cost gates, event-delay behavior, mandatory fallback and trade #2/#3 logic are new live rules and must be forward/OOS tested unchanged before claiming the historical >=80% WR transfers to live execution.

# LEGACY
V18/V40 are old CUT-based forced-daily research and are not active. V15/V36b are separate selective scanner research with untouched August evidence; only use them if the user explicitly switches back to a selective/NO-TRADE-capable mode.

## New-chat instruction
`Current Trading structure = V73 frozen no-CUT forced-daily prior + V74 live-analysis layer + Twelve Data Grow55 data policy. Read MASTER_TRADING_STATE.md, NO_CUT_INTRADAY_ALLPASS_V73.md, LIVE_SYMBOL_ANALYSIS_V74.md and TWELVEDATA_GROW55_DATA_POLICY.md. V73: Forex28/28 PASS min80.00%, Crypto61/61 PASS min80.22%, exposed development only. For LIVE always use V74: exact fresh price, symbol-specific news/context, D1-H4-H1 bias, M15 location, M5 confirmed trigger, structural SL, RR1 default / RR2 only with clean room, 1–3 independent trades/day. Grow55: use staged market-data allocation, no routine Basic-plan sleep, exchange-native crypto execution quotes, verified exact futures/cash instruments, never stale/proxy data.`