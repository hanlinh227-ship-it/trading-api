# Forex Analysis Skill Upgrade Review

Updated: 2026-10-04  
Status: isolated research-only candidate; not a production skill release

## Scope and authority

The reviewed source is `hanlinh227-ship-it/trading-api`, main at `ce2c7211583d38e2117525dbacfe57caeea4c4cd` (2026-10-02). Current Trading execution authority remains the current Bybit project authority; Forex execution authority is retired. The Exness multi-timeframe/news method in `docs/exness/SCALP_SIGNAL_RESEARCH_DESIGN_2026-10-01.md` remains a **design candidate** with no order route, live signal authority, paid API call, or production deployment.

This proposal strengthens existing canonical skills. It does not add a second router, primary skill, model, provider, order route, credential, or runtime dependency. The changed source and catalog contracts have no effect until a separately validated capability release is promoted and runtime health is confirmed at its exact SHA.

## Skill inventory

| Existing route or skill | Role in FX work | Change in this candidate |
|---|---|---|
| `trading_router` | Entry route and authority boundary | Route FX breadth to `multi_market_analysis`, a single pair/open-position review to `market_analysis`; keep EA engineering separate |
| `multi_market_analysis` | Canonical primary for broad/cross-market research | Add base/quote macro, event coverage, currency-relative context, MTF structure, broker-specific microstructure and conditional open-position review |
| `market_analysis` | Single-instrument evidence and price structure | Add FX quote sides, broker identity, closed-bar, session and tick-volume semantics |
| `quant_backtesting` | Strategy validation | Add bid/ask, variable spread, carry/swap, rollover, DST, correlated-pair and OOS requirements |
| `risk_execution` | Bounded risk support when requested | Add read-only FX position review and missing-data rules; no order mutation |
| Catalog labels `forex`, `market_microstructure`, `technical_analysis`, `live_data_validation`, `risk_management`, `quant_validation` | Routed capability contracts, not separate FX reasoning authorities | Tighten FX-specific output contracts without changing triggers, tools, priorities or router topology |
| `mt5_mql5` | MT5/EA software engineering | Not changed; it is not the user's analysis brain |

The connected ChatGPT skill catalog also includes `trading-research`, `market-candle-analysis`, `market-candle-reader`, `economic-forecasting`, `market-intel`, `research-search`, and `volume-profile-footprint`. Their applicable ideas are incorporated as methodology references, not copied skill files or automatically available Cloudflare runtime capabilities. In particular, candle provenance/closed-bar checks, official macro-source discipline, source freshness, and backtest realism transfer well; footprint/order-book claims do not transfer to an MT5 tick-only FX feed.

## Connected GitHub systems reviewed

| Repository | Observed role | FX skill decision |
|---|---|---|
| [trading-api](https://github.com/hanlinh227-ship-it/trading-api) | Canonical GitHub Brain/skill source and Trading project authority | Apply the candidate changes here |
| [linhai-system-core](https://github.com/appvn553-byte/linhai-system-core) | System catalog/scaffold; it does not contain the running Brain V2 | Do not treat as live skill authority |
| [linhai-memory-continuity](https://github.com/appvn553-byte/linhai-memory-continuity) | Documentation/memory archive | Useful only for context; current runtime retrieval must be verified independently |
| [agent-bus](https://github.com/hanlinh227-ship-it/agent-bus) | File-based agent messaging | Transport only; no Forex reasoning method |

## External repository and skill screen

Checked on 2026-10-04. Upstream material remains quarantined as evidence/capability, not a second reasoning authority.

| Candidate | Observed value | Decision |
|---|---|---|
| [QuantConnect/Lean](https://github.com/QuantConnect/Lean) | Apache-2.0, active; broad backtesting/live algorithm engine with Forex examples | Best reference for reproducible multi-asset research and backtest architecture. Do not embed the .NET engine in the Cloudflare skill gateway or import its live-trading path. |
| [kernc/backtesting.py](https://github.com/kernc/backtesting.py) | AGPL-3.0; active; its API models spread and commission on OHLC backtests | Use only as a design reference for making transaction costs explicit. No code import without license review; this engine alone does not establish Exness tick, carry, or account semantics. |
| [jagres0039/hermes-market-skills](https://github.com/jagres0039/hermes-market-skills) | MIT; includes a Forex/commodity skill with DXY, calendar, news and SMC layers; Python CLI and optional TwelveData, yfinance, ForexFactory and Telegram sources | Useful as a checklist of evidence categories only. Do not import its skill or code: its prompt defaults to BUY/SELL/WAIT recommendations and Telegram-card output, uses a scraped calendar and delayed yfinance fallback, and does not preserve the user's Exness/MT5 quote contract. |
| [The-Swarm-Corporation/ForexTreeSwarm](https://github.com/The-Swarm-Corporation/ForexTreeSwarm) | MIT; multi-agent “forest” with technical/fundamental/sentiment roles and external feeds | Do not adopt another agent tree; it conflicts with the existing single-authority chain and has not passed source, entitlement, freshness or eval gates. |
| [mhallsmoore/qsforex](https://github.com/mhallsmoore/qsforex) | README says MIT and describes OANDA; GitHub API does not identify a license; last push observed 2022-06-21 | Do not import. Broker-specific and stale, with license metadata requiring manual review. |
| [mementum/backtrader](https://github.com/mementum/backtrader) | GPL-3.0; last push observed 2024-08-19 | Do not import. Its broad simulator is unnecessary for the current skill-only scope and adds a licensing/dependency burden. |
| [0xgetz/daily_forex_analysis](https://github.com/0xgetz/daily_forex_analysis) | MIT; LLM-assisted spot FX/metals analysis; pair-specific pip metadata and deterministic EMA/RSI/MACD/ATR/range calculations, with H1/H4/D1 structure and a 24/5 session model. README claims 221 tests; not independently run. | Keep as a reference for symbol-specific units and separating deterministic calculations from narrative. It uses external price providers, has no Exness bid/ask/account-position contract or macro calendar, supports fewer timeframes, and has a hard-coded UTC session model; do not import its code or treat its provider data as live Exness evidence. |\n| [liangzaici/forex-analysis-skills](https://github.com/liangzaici/forex-analysis-skills) | Repository was empty when checked | No usable content to evaluate or integrate. |

The most transferable improvements are evidence discipline, pair-specific pip/tick/contract metadata, deterministic calculation boundaries, and evaluation design, not upstream code or prebuilt trade recommendations. The user's Exness/MT5 symbol specification, quote side, and account contract remain authoritative for broker-specific observations. No upstream code has been imported.

## FX-specific evidence rules

- **Macro:** compare base and quote currency drivers; prefer first-party central-bank and statistical releases; preserve publication/event/observation times, timezone and source. Separate a data surprise from the price response.
- **Events:** cover both currencies over a stated time window. An incomplete or stale calendar is `EVENT_COVERAGE_UNKNOWN`, never “no news.”
- **Micro/market structure:** identify broker/provider, symbol mapping, bid/ask, source/receive time, spread, session, and closed-bar status. MT5 tick volume describes the observed feed; it is not consolidated turnover, aggressor flow or an interbank order book.
- **Price structure:** W1/D1 provide broad context; H4/H1 provide structure; M30/M15 provide setup context; M5/M1 are optional timing evidence. Missing timeframes stay missing. An open candle is provisional.
- **Currency exposure:** infer broad strength only from coherent, time-aligned crosses or a named index; a single pair cannot prove currency-wide strength. Avoid double-counting common-currency exposure.
- **Cost/risk:** preserve buy-at-ask / sell-at-bid semantics and mark open positions on the opposing side. Include spread, commission, swap/carry, rollover, slippage and contract conversion only when known. Otherwise report risk as unquantified. Flag missing SL and unusually concentrated exposure when the full position/account set supports the claim.
- **Communication:** separate observed MT5 values from analysis. Offer conditional scenarios and invalidation conditions, not an instruction to place, edit or close an order.

MetaQuotes' `MqlRates` reference distinguishes `tick_volume` from `real_volume`; the BIS describes FX execution across a diverse OTC venue landscape. These support labeling the exact feed rather than implying a universal FX tape: [MqlRates](https://www.mql5.com/en/docs/constants/structures/mqlrates), [BIS 2025 FX execution landscape](https://www.bis.org/publications/qr-202512/fx-trade-execution-landscape-through-prism-2025-bis-triennial-survey), [BIS 2025 Triennial Survey](https://www.bis.org/publications/triennial-central-bank-survey-foreign-exchange-and-over-the-counter-otc-derivatives-markets-2025).

## Candidate evaluation cases

These are acceptance cases to run before any release promotion; this document does not claim they have passed.

1. Fresh broker bid/ask with an old forming M15 bar: retain current quote, classify candle as provisional, and disclose stale history.
2. Long and short quote-side check: long entry uses ask and mark/exit uses bid; short entry uses bid and mark/exit uses ask.
3. Missing calendar feed or partial coverage for either currency: return `EVENT_COVERAGE_UNKNOWN`, not “no event.”
4. MT5 tick volume with no trade-level data: do not produce market-wide flow, footprint or volume-profile claims.
5. A single EURUSD chart with no other crosses: keep USD strength pair-specific; do not infer broad currency breadth.
6. Multiple USD positions with missing full account positions or contract values: flag possible concentration, but leave account-level loss/margin unquantified.
7. Position with no SL: explicitly flag it; describe conditional protection scenarios without issuing an order command.
8. Backtest using midpoint candles and zero spread/swap/commission: reject the result as non-executable or require sensitivity ranges.
9. Same strategy on multiple correlated pairs: evaluate aggregate currency exposure and walk-forward stability, not pair count alone.
10. Upcoming high-impact event: include the official/source timestamp and conditional scenarios; do not let headline sentiment override quote freshness or invalidation.
11. Existing gateway contract regression: preserve the v3 `dataAcquisitionPlan`, LIVE / CONTEXT_ONLY / GAP coverage, research-only Entry/SL/TP, TradingView link semantics, TOP_SETUP/NO_TRADE and BTC authority boundary while adding FX-only metadata.

## Promotion gates

Before this becomes active, compile the checkpoint-resolved skill capsule/catalog snapshot, run all repository skill/consolidation and gateway validators, review the exact diff and license/provenance record, run the cases above plus protected-regression tests, create a versioned release candidate, and verify runtime health at the exact promoted SHA. Any required gate that cannot be run leaves the candidate unpromoted. No deployment or trading authority change is part of this work.
