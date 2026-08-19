# MASTER TRADING STATE

Updated: 2026-08-19 UTC+7
Purpose: single canonical state for the Trading project.

## 2026-08-19 CURRENT SOURCE OVERLAY
Current GitHub `main` source outranks older historical version labels below when they conflict.

Reviewed component state:
- `cloudflare-worker/index.js`: **V77.18.43 — Legacy Cleanup + Version Sync**.
- `cloudflare-worker/hub-v77171.js`: **V77.18.42**.
- `cloudflare-worker/engine-v77168.js`: **V77.16.20 — Signal Lifecycle Guard R7**.
- System Health fixes present through **V77.18.45**.
- `cloudflare-worker/hyro-execution.js`: **V77.18.46** telemetry-degradation repair, commit `1d6db32155c06d464f4da94746df73e110b9b294`, reviewed **PASS by Claude 2026-08-19T11:40:00Z**.

V77.18.46 telemetry contract:
- critical probes: wallet, positions, orders;
- optional/degradable probe: closedPnl;
- critical failure remains fail-closed for new execution;
- closedPnl-only failure remains connected/degraded so existing positions stay visible/manageable;
- realized P/L freshness is explicit and unavailable realized data is not fabricated as zero.

Permanent AI co-engineering is active through GitHub:
- `/CLAUDE.md`
- `/AGENTS.md`
- `docs/ai-coengineer/PROTOCOL.md`
- `docs/ai-coengineer/SHARED_STATE.md`
- `docs/ai-coengineer/WRITE_LOCK.md`
- `docs/ai-coengineer/OPEN_ISSUES.md`
- `docs/ai-coengineer/DECISIONS.md`
- ChatGPT -> Claude: `docs/ai-coengineer/CHATGPT_TO_CLAUDE.md`
- Claude -> ChatGPT: `docs/ai-coengineer/CLAUDE_TO_CHATGPT.md`

Default AI roles:
- ChatGPT = PRIMARY_ENGINEER.
- Claude = REVIEWER / SECOND_ENGINEER.
- One writer at a time; production writes require explicit issue/handoff ownership plus matching write-lock scope.

Cloudflare deployment evidence observed 2026-08-19:
- Deployments UI showed the V77.18.46 Hyro telemetry repair in version history;
- later co-engineering/state commits from `main` also appeared in deployed version history.
This is deployment evidence, not a blanket runtime-health guarantee. Do not claim `PRODUCTION HEALTHY` without runtime evidence.

Architecture invariants remain:
- V73 frozen statistical prior;
- V74 live decision authority;
- V76 Forex R2 research-only, 0/28 promoted;
- canonical Signal markets are Forex, Crypto, Metal, Index Cash; legacy Futures Signal stays removed;
- PROP is one Hyro account only; never restore TK2/multi-account without explicit redesign;
- V77.18.22 safe-risk policy remains authoritative;
- preserve `TRADING_STATE` and `v775:books`;
- no release-driven forced close;
- never fabricate financial state/quotes/P&L or bypass structural-SL/freshness/hard-news gates.

## Read order
1. `CURRENT_HANDOFF.md`
2. `UNIFIED_RUNTIME_V77_7.md`
3. `ENTRY_EXECUTION_V76.md`
4. `NO_CUT_INTRADAY_ALLPASS_V73.md`
5. `LIVE_SYMBOL_ANALYSIS_V74.md`
6. `TWELVEDATA_GROW55_DATA_POLICY.md`
7. relevant market checkpoint.

# CURRENT ARCHITECTURE

## V73 — frozen statistical prior

V73 is frozen. No live or research workflow may rebuild/optimize it.

Frozen development result remains:
- Forex 28/28 PASS, minimum development WR 80.00%;
- Crypto 61/61 PASS, minimum development WR 80.22%;
- Forex H1; 59 Crypto H1; TON/IP 4H;
- frozen passing maps currently use 1 trade/day and RR1:1.

Classification: **exposed development all-pass, not untouched OOS; never promise future/live WR.**

Canonical files:
- `data/nocut_intraday_allpass_v73.json`
- `scripts/nocut_intraday_method_v73.py`
- `scripts/validate_nocut_v73.py`

## V74 — live analysis / execution authority

V74 remains the live decision authority over V73.

Order:
1. exact instrument / venue / contract;
2. fresh timestamped data;
3. current symbol-specific news/context;
4. D1/H4 liquidity/regime;
5. H1 structure;
6. frozen V73 prior where applicable;
7. M15 tradable location;
8. strict M5 close-confirmed MSS/displacement + retest;
9. structural SL first;
10. RR1 default; RR2 only with >=2.2R clean room after costs;
11. final execution-venue quote/spread before MARKET;
12. forward-log without retuning from the outcome.

Coverage: 28 Forex + 61 Crypto = 89/89 V74 playbooks.

## V75 — Fast Data layer

V75 changes data latency/read efficiency only. It does not weaken V74 or modify V73.

Preferred live artifacts:
- single symbol → `data/decision.json`;
- Forex scan → `data/forex-fast.json`;
- Crypto scan → `data/crypto-fast.json`.

Supported non-crypto uses `scripts/twelvedata_market.py` (`V4-TWELVEDATA-FAST-STRICT`): exact identity/type, D1/H4/H1/M15/M5 parallel fetch, closed candles, `/quote.last_quote_at` provider time, `/price` only after identity proof, >65s hard stale block, no fabricated bid/ask.

Forex 28-pair benchmark `32049900306`: 28 H1 + Top3 deep data section 0.643s once runner active. Crypto universe benchmark `32050388431`: 57/57 exact available OKX USDT instruments analyzed, 0 errors, 5.427s data section.

## V76 — Forex Entry Research R2

V76 is a research/execution-gate layer after V75; it does not modify V73/V74/V75.

**R2 final result is locked and negative for live promotion:**
- six objective setup families A–F;
- CLOSE/RETEST/LIMIT_FVG × STRUCTURE/STRUCTURE_ATR × RR1/RR2 = 72 variants;
- exact 28-pair Forex research;
- 30,000 M5 bars/pair, approximately 2026-05-05 through 2026-08-17;
- chronological 60% DEV / 20% VALIDATION / 20% untouched OOS;
- DEV ranks, VALIDATION gates, OOS only promotes/rejects and never retunes;
- retained global archetypes: **NONE**;
- promoted Forex symbols: **0/28**;
- all 28 methods = `RESEARCH_ONLY`;
- research candidates only: `C_SWEEP_FVG`, `D_BREAK_RETEST_CONT`;
- fully rejected in R2: A_SWEEP_MSS, B_H1_PULLBACK_RECLAIM, E_FAILED_BREAK_REV, F_IFVG_RECLAIM.

No V76 R2 Forex method may authorize a live order. `scripts/entry_v76.py` accepts only methods version `V76-ENTRY-METHODS-R2` and returns NO_ENTRY for non-promoted methods. Pilot R1 is explicitly blocked.

Do not tune R2 after reading OOS. New filters/hypotheses require a separately versioned generation with a new untouched OOS window.

Canonical V76 files:
- `scripts/research_v76_entry_forex.py`
- `scripts/evaluate_v76_entry_forex.py`
- `scripts/fetch_v76_history.py`
- `scripts/run_v76_entry_research.py`
- `scripts/entry_v76.py`
- `scripts/summarize_v76.py`
- `data/v76_entry_research.json`
- `data/v76_entry_methods.json`
- `data/v76_entry_summary.json`
- `data/v76_pair_table.md`
- `docs/checkpoints/ENTRY_EXECUTION_V76.md`

Historical high-impact macro-event windows were not fabricated because the canonical research feed lacks a complete timestamped historical macro calendar. Current V74 news/context refresh remains mandatory live. Historical transaction cost is modeled as fixed 0.05R because historical broker bid/ask is unavailable.

## V77.7.0 — unified production runtime

V77.7.0 is the historical foundation of the single GitHub-owned Cloudflare/Twelve Data/Telegram production shell. Current component overlays above supersede its older component version label where source has advanced. It does **not** replace V74 authority, rewrite V73, or promote V76.

Canonical production source:
- `cloudflare-worker/index.js`
- `cloudflare-worker/package.json`
- `cloudflare-worker/wrangler.example.jsonc`
- `.github/workflows/validate-cloudflare-v77.yml`
- `docs/checkpoints/UNIFIED_RUNTIME_V77_7.md`

Target topology:

`GitHub main -> Cloudflare Workers Builds -> trading-v77-scanner -> Twelve Data / exact crypto venues -> TRADING_V77_STATE KV -> Telegram`

Runtime rules:
- broad ranking is discovery only;
- Twelve Data batch requests reduce Cloudflare HTTP subrequests but do not reduce Twelve Data credits per symbol;
- Forex: 28 H1 broad symbols in one batch + Top3 five-timeframe deep batches;
- Crypto: 61 exact identities via exchange bulk discovery + 30 rotating Twelve Data H1 symbols in one batch + Top3 five-timeframe deep batches;
- Metal: XAUUSD/XAGUSD share H1/deep batches;
- strict news/context gate: technical-ready setups stop at `NEWS_CONTEXT_REQUIRED` until a 30-minute Telegram clearance or a genuine `NEWS_GATE_URL` service clears the symbol;
- Forex/Metal Twelve Data reference price does not authorize executable MARKET/LIMIT without real broker bid/ask;
- Crypto MARKET/LIMIT requires news clearance + fresh exact Bybit/OKX/Binance bid/ask + estimated spread <=0.10R;
- RR1 default; RR2 only with >=2.2R clean room;
- existing KV state remains `TRADING_STATE -> TRADING_V77_STATE` and books key remains `v775:books`.

Normal Telegram output shows books, coverage and canonical WATCH stage only. Raw provider errors stay in `/run-now` diagnostics and Worker logs.

# MARKET DATA INTEGRITY

The old Cloudflare shorthand Worker is not canonical runtime. Same-text ticker collisions are rejected.

Rules:
1. explicit canonical identity;
2. exact provider symbol/type metadata;
3. closed candles only for technical calculations;
4. provider timestamp != fetch time;
5. aggregated price != executable quote;
6. stale data is never called live;
7. no fabricated spread;
8. cash index, futures and spot are never interchangeable.

Current routing:
- Forex: direct strict Twelve Data Grow55 exact `AAA/BBB` mapping for analysis/reference; broker execution quote still required before new executable order;
- Crypto: Twelve Data standardized analysis + exact exchange-native Bybit/OKX/Binance execution;
- spot metals/energy: exact Twelve Data identity for analysis/reference; broker execution quote still required before new executable order;
- NAS100/US500/DAX/N225-family cash indices: historical Grow55 integration may DATA_BLOCK unsupported identities; current Signal architecture remains Index Cash and exact provider identity is required;
- exact NQ/MNQ/ES/MES/GC/SI/CL futures: no cash-index proxy; exact authoritative contract feed required for futures analysis/execution.

# VALIDATION EVIDENCE

- Market-data audit `32050497678`: SUCCESS, 7 PASS / 10 BLOCKED_AS_DESIGNED / 0 FAIL.
- V73 validator `32050638267`: SUCCESS.
- V74 validator `32050656054`: SUCCESS.
- V76 final R2 research `32053656572`: SUCCESS.
- V76 compact summary `32054967541`: SUCCESS.
- V76 post-R2 validator `32055039365`: SUCCESS; validates methods R2, 28 pairs, retained=[], conservative intrabar scoring and V73 frozen.
- Historical V77.7.0 local `node --check`: PASS. Current GitHub workflow `.github/workflows/validate-cloudflare-v77.yml` remains the deterministic repository guard; do not claim a particular workflow run passed unless that run is verified.
- V77.18.46 code review: Claude PASS on repair commit `1d6db32155c06d464f4da94746df73e110b9b294`.

# ACTIVE REPOSITORY

Live/validation workflows:
- `fetch-market.yml`
- `scan-forex.yml`
- `live-crypto-v75-scan.yml`
- `audit-market-data.yml`
- `validate-nocut-v73.yml`
- `validate-live-v74.yml`
- `validate-cloudflare-v77.yml`

Isolated V76 workflows:
- `research-v76-entry.yml`
- `validate-entry-v76.yml`
- `summarize-v76.yml`

Production Cloudflare source:
- `cloudflare-worker/index.js`

Legacy optimizers, old blind tests, one-off diagnostics and obsolete live-data paths remain in Git history only.

# CURRENT LIVE ENTRY RULE

Because V76 R2 promoted 0/28, V76 cannot authorize live Forex entries. Current production decisions follow V74 evidence through the current V77 component stack.

DATA_BLOCK always overrides forced-trade research logic.

Forex/Metal: without a real broker/venue bid/ask feed, no new executable MARKET/LIMIT may be created from Twelve Data reference data alone.

Crypto: MARKET/LIMIT requires the complete canonical technical stack, current news/context clearance, structural risk/room, and a fresh exact venue bid/ask confirmation.

Index Cash: use exact authoritative cash-index identity/data only. Never proxy a futures contract from a cash index or vice versa.

NQ/ES Futures: no backtest/live proxy from cash indices. Use exact authoritative futures data only; compare MNQ/MES and choose the stronger setup when such data is available. Structural SL first, then contract count; user framework roughly max SL $500 / target $1,500 when structure supports it.

## Handoff phrase

`Continue Trading co-engineering from GitHub main. Read CLAUDE.md, AGENTS.md, the AI co-engineering protocol/state/lock/issues/decisions/inbox, then CURRENT_HANDOFF and this MASTER state. Current reviewed components: index V77.18.43, hub V77.18.42, Signal V77.16.20, Health through V77.18.45, Hyro execution V77.18.46 PASS. Keep V73 frozen, V74 live authority, V76 R2 research-only, one Hyro account, V77.18.22 safe risk, TRADING_STATE and v775:books. Canonical Signal markets are Forex/Crypto/Metal/Index Cash; never restore Futures Signal/TK2, fabricate financial data, weaken hard gates or write outside explicit ownership/write-lock scope.`
