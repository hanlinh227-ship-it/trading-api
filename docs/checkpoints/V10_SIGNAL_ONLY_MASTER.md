# V10 SIGNAL ONLY — MASTER STATE

Status: canonical source-of-truth for Telegram Signal Only V10 architecture on GitHub `main`.

## Separation

- Signal Only V10: Cloudflare scanner/advisory + dedicated VPS three-AI council + Telegram signal lifecycle.
- Binance Auto: separate VPS approval/execution project. Signal V10 never grants Binance order authority and does not modify Binance Auto execution logic.
- Signal V10 source is GitHub `main` plus the isolated VPS worktree `/opt/trading/signal-v10-src` tracking `origin/main`.
- Legacy V77/V78 files remain compatibility scanner internals only. They are not public version authority and their outcome history is not used as V10 win-rate data.

## Active V10 entry path

`cloudflare-worker/index.js` -> `hub-v10-unified-entry.js` -> `hub-v10-unified-v2.js` for Telegram UX and `signal-v10-scheduled-v2.js` for cron.

Compatibility scanner data flows into V10 only as input. Public authority remains V10.

## Signal lifecycle

1. Scan Forex, Crypto, Metal and Index with the compatibility scanner engine.
2. Every actionable candidate is re-analysed immediately before V10 admission. An already-present scanner price is not trusted as a substitute for this refresh.
3. Only a quote carrying a positive price and explicit `fresh === true` is propagated to V10. Missing, stale, unknown-freshness or refresh-failed quotes are cleared and fail closed at Entry Intelligence / pre-gate.
4. V10 pre-gate checks quote evidence, Entry Intelligence, plan completeness, RR, geometry and market-specific quality.
5. Up to three candidates are batched to the isolated VPS council.
6. Claude reviews context/regime/timing; DeepSeek attacks edge/risk weaknesses; Codex checks quantitative/logical consistency.
7. All three providers must return valid reviews. Promotion requires at least two aligned with the proposed direction, no opposite-direction reviewer, and directional confidence >=64.
8. Accepted V10 signal is sent to Telegram. Candidate-only/rejected output is not an official signal.
9. Cloudflare tracks each accepted V10 signal independently. TP/SL evaluation requires a newly loaded quote with positive price and explicit `fresh === true`; unverified lifecycle prices cannot close a signal.
10. Expired-but-not-yet-processed OPEN rows remain visible in Unified Live until lifecycle records `EXPIRED`, preventing a Live -> History visibility gap.
11. Closed V10 outcomes are written to `v10:signal:history`; they are not deleted.
12. V10 learning computes market/symbol/strategy statistics only from WIN/LOSS rows in the V10 ledger; EXPIRED is retained as history but excluded from WR.
13. Outcome insertion is idempotent for the same candidate/outcome, and learning maintains a processed-event seen set to prevent repeated counting during refresh.
14. Learning may make small bounded ranking/quality adjustments. It never rewrites source code or turns historical WR into a promised future probability.

## Telegram model

- `📚 LỆNH ĐANG CHẠY`: V10 OPEN plus legacy/compatibility books still active.
- `🔥 V10 CHÍNH THỨC`: only accepted three-AI V10 signals.
- `🔍 QUÉT MỚI`: candidates; rejects are summarized as `SETUP BỊ LOẠI — KHÔNG PHẢI LỆNH`.
- `🕘 LỊCH SỬ`: closed V10 outcomes plus compatibility order history.
- `📈 THỐNG KÊ`: observed V10 closed-signal outcomes only.
- `🧠 3 AI`: pending/review/health state.
- `🟨 BINANCE AUTO`: separate callback namespace and separate execution project.

## Win-rate semantics

Observed WR, Bayesian-smoothed WR, Wilson lower bound and AvgR are descriptive statistics from closed V10 outcomes, not guaranteed or calibrated future probabilities.

## Quality/frequency balance

- Review up to 3 actionable candidates per scan in one AI batch.
- No candidate means zero three-AI review calls.
- Base V10 quality floor remains market-specific; this optimization does not lower it.
- Historical learning adjustment remains bounded to avoid overfitting small samples.
- Real LONG/SHORT disagreement blocks promotion.
- A third reviewer may WAIT; unanimity is not required.
- No daily signal quota. Opportunity frequency comes from continuous scans and valid evidence, not from weakening gates.
- Optimization priority is removal of false rejects caused by broken data propagation, never bypassing freshness or quality protections.

## Runtime source of truth

Cloudflare `main`:
- `cloudflare-worker/index.js`
- `cloudflare-worker/hub-v10-unified-entry.js`
- `cloudflare-worker/hub-v10-unified-v2.js`
- `cloudflare-worker/signal-v10-scheduled-v2.js`
- `cloudflare-worker/signal-v10-council.js`
- `cloudflare-worker/signal-v10-learning.js`
- `cloudflare-worker/providers/entry-intelligence.js`

Dedicated VPS Signal V10 worktree from `origin/main`:
- `signal-only-v10/ai_council_worker.py`
- `signal-only-v10/runtime/install_signal_v10.sh`
- `signal-only-v10/runtime/update_signal_v10.sh`

Systemd:
- `signal-v10-council.service`
- `signal-v10-update.timer`

Binance Auto services are separate and are not restarted by Signal V10 updater.

## Guardrails

- SIGNAL ONLY has no execution authority.
- All three AI responses are required for official V10 promotion.
- Missing/unverified data => WAIT/reject, never fabricated evidence.
- Transient AI provider failure leaves a candidate pending for bounded retry until TTL; successful provider batch results may be reused briefly to avoid wasting tokens.
- Signal V10 and Binance Auto state are not used to approve each other's trades.
- V10 historical WR uses only closed V10 WIN/LOSS outcomes.
- A GitHub source commit is not proof that Cloudflare or VPS runtime has deployed it; runtime deployment must be verified separately.
