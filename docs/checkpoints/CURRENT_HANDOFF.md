# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-22 UTC+7

## READ FIRST
1. fresh-read GitHub `main`;
2. `docs/checkpoints/MASTER_TRADING_STATE.md`;
3. this file;
4. `docs/ai-coengineer/SHARED_STATE.md`;
5. `docs/ai-coengineer/WRITE_LOCK.md`;
6. current V11 source relevant to the task.

GitHub `main` outranks stale checkpoint/version wording.

## CURRENT CANONICAL STATE

Signal V11 is the sole public signal authority and remains SIGNAL_ONLY.

Production is now designed to operate without routine VPS/manual commands:
- Cloudflare native scheduler scans automatically;
- accepted V11 MARKET signals are persisted in TRADING_STATE;
- a newly stored accepted signal triggers Telegram automatically;
- TP / SL / EXPIRED transitions trigger Telegram automatically;
- duplicate OPEN market/symbol/side signals are blocked;
- LIMIT/WATCH/MARKET_PLAN cannot be promoted to automatic MARKET;
- manual 3-AI MARKET hunter remains on-demand only;
- VPS is only required for the VPC Claude/Codex bridge service, not daily signal operation.

## TELEGRAM

Telegram V11 dashboard now includes:
- LIVE positions;
- WATCH setups;
- Forex / Crypto / Metal / Index manual scans;
- official V11 accepted signals;
- lifecycle history;
- statistics;
- on-demand three-AI MARKET hunter;
- separate Binance Auto entry point.

Automatic MARKET alert contains Entry, SL, TP, RR, quality, freshness/source, setup, WHY NOW and SIGNAL ONLY disclaimer.
Automatic lifecycle alerts are sent for TP / SL / EXPIRED.

## DATA / GATE INTEGRITY

Preserve:
- real timeframe ATR14 evidence;
- provider freshness hard gate;
- structural invalidation SL;
- forward-structure/liquidity TP;
- market-specific deterministic policy gates;
- fail-closed behavior.

Valid non-entry outcomes include WATCH, quality rejection, forward-target RR insufficiency, stale quote rejection, NO_MARKET_ENTRY and NO_3AI_CONSENSUS.

## CI / DEPLOYMENT

`.github/workflows/v11-signal-validation.yml` now validates production V11 changes on `main`.
`.github/workflows/deploy-cloudflare-worker.yml` is the canonical auto-deploy path for Cloudflare-worker changes.

Manual VPS deployment should only be used for recovery/diagnostics, not normal operation.

## VPC AI BRIDGE

- Cloudflare binding: `AI_BRIDGE`;
- VPC service: `v11-ai-bridge`;
- VPS systemd: `v11-manual-ai-bridge`;
- Claude + Codex: on-demand review only;
- DeepSeek: API-native when configured;
- all three required for positive manual-hunter consensus.

## NEXT ENGINEERING PHASE

Connection/plumbing work is considered complete unless new runtime evidence proves otherwise.
Next work is signal-quality refinement from actual production evidence:
1. observe newly created funnel rows only;
2. measure APPROVED/WATCH/REJECTED distribution per market;
3. evaluate closed lifecycle WIN/LOSS/EXPIRED outcomes;
4. improve ranking/discrimination without lowering hard gates;
5. investigate freshness failures only when reproducible during an active market session.

Do not return to old V78/V10 signal-authority methods.

## NEW CHAT PROMPT

`Continue Trading from current GitHub main. Read MASTER_TRADING_STATE.md, CURRENT_HANDOFF.md, SHARED_STATE.md and WRITE_LOCK.md. Signal V11 is the only public signal authority and is SIGNAL_ONLY. Cloudflare auto-scans, Telegram auto-notifies new accepted MARKET signals and TP/SL/EXPIRED lifecycle events, LIMIT/WATCH cannot be promoted into MARKET, and the three-AI hunter is on-demand fail-closed. Preserve TRADING_STATE, V11 native scheduler, VPC bridge and deterministic gates.`
