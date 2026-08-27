# FOREX CANONICAL STATE — 2026-08-27

Updated: 2026-08-27 UTC+7
Status: CANONICAL PRODUCTION AUTHORITY
Supersedes: FOREX_PURE_AI_060_20260827.md (historical, daily objective was 0.50% at 0.6.0)

## CURRENT PRODUCTION VERSION
`FOREX-AUTO-0.6.3-USER-CAMPAIGN-510-3D`

## EXECUTION AUTHORITY
- Pure AI: GPT/Codex (gpt-5.6-sol) + Claude — 2/2 quorum required
- DeepSeek / Qwen / OpenRouter: retired, not active
- EA: 1.002 on MT5 Windows (not VPS)
- Transport: MT5 → Cloudflare Hub → VPS 2AI Bridge → MT5
- Mode: LIVE (`FOREX_AUTO_LIVE=true` via deploy workflow)

## ACTIVE CAMPAIGN
- Target: +$510
- Trading days: 3 (Saturday/Sunday excluded)
- Cycle ID: USER_20260827_510USD_3TRADINGDAYS
- Daily objective: strictly above +1.00% from broker day-start equity
- Risk chasing: forbidden — target is context only, never permission to widen risk

## EA CAPABILITIES (1.002 confirmed)
- MARKET_ENTRY: active
- LIMIT_ENTRY: active (capability-gated in backend)
- STOP_ENTRY: active (capability-gated in backend)
- RED_NEWS_FAIL_CLOSED: active
- PENDING_NEWS_AUTO_CANCEL: active
- HOLD / CLOSE / MODIFY_SLTP: active

## HARD RISK LIMITS (unchanged)
- Max risk/trade: 1.00%
- Max total open risk: 3.75%
- Min RR: 1.5
- BUY/SELL alternation: hard lock on filled entry sequence

## FIXES APPLIED 2026-08-27 (F1–F6)
- F1: FOREX_ROLE in Python bridge synced — added orderType, entryPrice, entryCandidates
- F2: managementConsensus SELL SL direction fixed (Math.max for both BUY and SELL)
- F3: quoteAgeSec timestamp parser — handles Unix seconds, Unix ms, ISO string safely
- F4: entryConsensus relaxed to symbol+side matching with conservative orderType reconciliation
- F5: Adaptive AI council cadence — heartbeat stays 2s, AI council rate-limited (default 30s)
      Wake-up conditions: open positions, cooldown elapsed, pending management pending confirm
- F6: Checkpoint sync — historical 0.6.0 marked SUPERSEDED, this file is canonical

## TIMEZONE NOTE (A2 — unresolved)
Day-start baseline uses Etc/GMT-3 (UTC+3). The5ers server reset timezone
has not been independently verified from production runtime. Do not change
until confirmed from MT5 server time or The5ers documentation.
This remains an open recommendation, not a production change.

## DEPLOYMENT CONTRACT
Every Forex production change requires:
1. Source validation (npm run check + validate-forex-auto.mjs)
2. Cloudflare deploy
3. /forex/health PASS
4. MT5 canonical heartbeat fresh
5. EA version/capabilities confirmed from heartbeat, not assumed
