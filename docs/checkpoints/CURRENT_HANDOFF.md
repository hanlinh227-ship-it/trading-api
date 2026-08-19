# CURRENT HANDOFF — TRADING PROJECT

Updated: 2026-08-19 UTC+7

## READ FIRST
1. `/CLAUDE.md`
2. `/AGENTS.md`
3. `/docs/ai-coengineer/PROTOCOL.md`
4. `MASTER_TRADING_STATE.md`
5. `docs/ai-coengineer/SHARED_STATE.md`
6. `docs/ai-coengineer/WRITE_LOCK.md`
7. `docs/ai-coengineer/OPEN_ISSUES.md`
8. `docs/ai-coengineer/DECISIONS.md`
9. relevant market checkpoint

## CURRENT CANONICAL COMPONENT STATE
GitHub `main` source is authoritative when historical checkpoint text lags.

Current reviewed component state:
- Production entrypoint `cloudflare-worker/index.js`: **V77.18.43 — Legacy Cleanup + Version Sync**.
- HUB `cloudflare-worker/hub-v77171.js`: **V77.18.42**.
- Signal engine `cloudflare-worker/engine-v77168.js`: **V77.16.20 — Signal Lifecycle Guard R7**.
- Health Guardian fixes are present through **V77.18.45**.
- Hyro execution telemetry repair is **V77.18.46**, repair commit `1d6db32155c06d464f4da94746df73e110b9b294`.

Component versions are independent. Do not bump a component solely for cosmetic alignment when that component source did not change.

## AI-001 — HYRO TELEMETRY REPAIR
**RESOLVED. Claude review PASS 2026-08-19T11:40:00Z.**

Current telemetry contract:
- critical: `wallet`, `positions`, `orders`;
- optional/degradable: `closedPnl`;
- critical failure => `connected:false` and fail-closed for new execution;
- `closedPnl`-only failure => `connected:true`, degraded diagnostics, existing positions remain visible/manageable;
- realized P/L freshness is explicit; unavailable realized data is not fabricated as zero.

Claude confirmed no hard-risk constants, state keys, credential routing or order semantics were changed by the repair.

Non-blocking future improvement: when `closedPnlFresh:false`, Telegram closure reporting may annotate realized P/L as unavailable instead of displaying a stale/zero-looking delta without context.

## PERMANENT CHATGPT ↔ CLAUDE CO-ENGINEERING
GitHub is the durable communication bus between ChatGPT and Claude.ai.

Root entrypoints:
- `/CLAUDE.md`
- `/AGENTS.md`

Protocol/state files:
- `docs/ai-coengineer/PROTOCOL.md`
- `docs/ai-coengineer/SHARED_STATE.md`
- `docs/ai-coengineer/WRITE_LOCK.md`
- `docs/ai-coengineer/OPEN_ISSUES.md`
- `docs/ai-coengineer/DECISIONS.md`
- ChatGPT -> Claude: `docs/ai-coengineer/CHATGPT_TO_CLAUDE.md`
- Claude -> ChatGPT: `docs/ai-coengineer/CLAUDE_TO_CHATGPT.md`

Default roles:
- ChatGPT = **PRIMARY_ENGINEER**.
- Claude = **REVIEWER / SECOND_ENGINEER**.

One writer at a time. `LOCKED:false` does not itself grant production-write authority; issue ownership or an explicit handoff is still required. Both AIs must refresh `main` before analysis/write and current source outranks stale docs.

Claude.ai cannot wake itself when GitHub changes. A user `continue co-engineering` turn starts the Claude session; after that Claude must refresh/read the GitHub bus and continue without asking the user to paste project state manually.

## AI GOVERNANCE / RUNTIME AI
The repository still contains runtime AI governance modules such as `ai-arbiter.js` and `dual-ai-intervention.js`. These runtime paths are distinct from the human-invoked Claude.ai GitHub co-engineering bus.

Neither AI co-engineering path may bypass deterministic validation, trading hard gates, secrets policy, state safety or write-lock ownership.

## PROP / HYRO
PROP remains **SINGLE HYRO ACCOUNT ONLY**. Never restore TK2/multi-account logic unless explicitly redesigned.

V77.18.22 safe-risk policy remains authoritative after 2026-08-19 00:00 UTC:
- A base ~0.45% equity;
- single cap ~0.55%;
- combined open risk ~0.90%;
- internal daily hard stop ~1.60%;
- structural SL authoritative; reduce USD risk using size, not by silently tightening structural invalidation.

TP management retained:
- TP1 ~0.85R, ~45%;
- TP2 ~1.60R, ~35%;
- runner ~20% toward ~2.45R;
- BE after TP1;
- trailing after TP2;
- HOLD/TIGHTEN/CUT position review retained.

## SIGNAL / MARKET ARCHITECTURE
Legacy Futures Signal remains removed.

Canonical Signal markets:
- Forex
- Crypto
- Metal
- Index Cash

Do not restore global legacy scan/live callbacks or Futures proxy logic.

V73 remains frozen statistical prior. V74 remains live decision authority. V76 Forex R2 remains research-only with 0/28 promoted; do not use rejected/promoted-none V76 research as live order authority.

Forex/Metal: Twelve Data reference price alone never authorizes executable MARKET/LIMIT without real execution-venue bid/ask.

Crypto: execution requires fresh exact venue-native quote and the canonical hard gates.

Cash index and futures are never interchangeable.

## SYSTEM HEALTH / TELEGRAM
Health fixes through V77.18.45 are present:
- legacy `future` health group removed in favor of canonical `index` identity;
- on-demand market scan age is informational, not a false system ERROR;
- full health owns automatic health notification;
- duplicate ERROR/WARN alerts are deduplicated/cooldown-controlled;
- recovery is reported separately;
- optional Hyro endpoint degradation must not be reported as total PROP OFF when critical telemetry remains healthy.

## GITHUB / CLOUDFLARE
Production source remains GitHub `main`.

Deployment contract:
- Worker: `trading-v77-scanner`;
- existing `TRADING_STATE` KV binding;
- `keep_vars: true`;
- deterministic validation before deployment;
- validator must not mutate/push source.

Observed deployment evidence on 2026-08-19:
- Cloudflare Deployments UI showed `V77.18.46 isolate Hyro closedPnl telemetry degradation` in version history;
- later communication/shared-state commits from `main` were also visible as deployed versions.

Do not elevate this evidence into a broader `PRODUCTION HEALTHY` claim without runtime evidence. The user explicitly requested no additional ad-hoc testing at that stage.

## STATE SAFETY — HARD RULE
Never:
- reset `TRADING_STATE`;
- delete/reset Signal LIVE ORDERS `v775:books`;
- close a position merely because code/version changed;
- restore Futures Signal legacy;
- restore Hyro TK2/multi-account;
- weaken hard risk to increase trade count;
- bypass structural SL, freshness or hard-news safeguards;
- fabricate broker/exchange quote or P/L;
- commit secrets/tokens/private keys.

## CURRENT OPEN ISSUE
AI-002: documentation synchronization. This handoff and `MASTER_TRADING_STATE.md` are being synchronized to the V77.18.46 reviewed component state and permanent GitHub co-engineering mode, then Claude must review the exact documentation diff before AI-002 is marked RESOLVED.

## NEW CHAT PROMPT
`Continue Trading co-engineering from GitHub main. Read /CLAUDE.md, /AGENTS.md, docs/ai-coengineer/PROTOCOL.md, MASTER_TRADING_STATE.md, CURRENT_HANDOFF.md, SHARED_STATE.md, WRITE_LOCK.md, OPEN_ISSUES.md, DECISIONS.md and your inbox. Current reviewed state: index V77.18.43, hub V77.18.42, Signal V77.16.20, Health through V77.18.45, Hyro execution V77.18.46 PASS. PROP is one Hyro account. GitHub is the permanent ChatGPT↔Claude bus with one writer at a time. Preserve V73 frozen/V74 authority/V76 research-only, V77.18.22 safe risk, TRADING_STATE and v775:books; never restore Futures Signal/TK2 or fabricate financial data.`
