# V10 SIGNAL ONLY — MASTER STATE

Status: production architecture source-of-truth for Telegram Signal Only.

## Separation

- Signal Only V10: Cloudflare scanner/advisory + dedicated VPS three-AI council + Telegram signal lifecycle.
- Binance Auto: separate VPS approval/execution project. Signal V10 never grants Binance order authority and must not modify Binance Auto runtime logic.
- Signal V10 source is `main` plus the isolated VPS worktree `/opt/trading/signal-v10-src` tracking `origin/main`.
- Legacy V77/V78 files remain compatibility scanner internals only. They are not public version authority and their outcome history is not used as V10 win-rate data.

## Signal lifecycle

1. Scan market universe (Forex, Crypto, Metal, Index) with the compatibility scanner engine.
2. V10 converts fresh analyses into candidates; legacy notifications are not official V10 signals.
3. V10 pre-gate checks evidence freshness, Entry Intelligence, plan completeness, RR, geometry and market-specific quality.
4. Up to three candidates are batched to the isolated VPS council.
5. Claude: context/regime/timing specialist.
6. DeepSeek: adversarial edge/risk specialist.
7. Codex: quantitative/logical consistency specialist.
8. All three providers must return a valid review. Promotion requires at least two reviewers aligned with the proposed direction, no reviewer taking the opposite direction, and directional confidence >=64.
9. Accepted V10 signal is sent to Telegram. Candidate-only output is not an official signal.
10. Cloudflare tracks each accepted V10 signal independently against fresh symbol quotes until TP, SL or expiry.
11. Closed V10 outcomes are written only to `v10:signal:history`.
12. V10 learning computes market/symbol/strategy statistics only from that V10 ledger; V77/V78 history is excluded.
13. Learning may make small bounded ranking/quality adjustments. It never rewrites source code or turns historical win-rate into a promised future probability.

## Win-rate semantics

Telegram shows `Observed WR`, sample size `n`, Bayesian-smoothed WR, 80% Wilson lower bound, and AvgR when available. These are descriptive V10 closed-signal statistics, not guaranteed or calibrated future win probabilities.

## Quality/frequency balance

- Review up to 3 actionable candidates per scan in one AI batch.
- No candidate => zero Claude/DeepSeek/Codex review calls.
- Base V10 quality floor is market-specific rather than A-only.
- Historical learning adjustment is bounded to avoid overfitting small samples.
- Real LONG/SHORT disagreement blocks promotion.
- A third reviewer may WAIT; unanimity is not required.
- No daily signal quota. Frequency comes from continuous market scans and candidate quality.

## Runtime source of truth

Cloudflare `main`:
- `cloudflare-worker/index.js`
- `cloudflare-worker/hub-v10.js`
- `cloudflare-worker/signal-v10-council.js`
- `cloudflare-worker/signal-v10-learning.js`

Dedicated VPS Signal V10 worktree from `origin/main`:
- `signal-only-v10/ai_council_worker.py`
- `signal-only-v10/runtime/install_signal_v10.sh`
- `signal-only-v10/runtime/update_signal_v10.sh`

Systemd:
- `signal-v10-council.service`
- `signal-v10-update.timer`

Binance Auto services/branch are separate and are not restarted by Signal V10 updater.

## Telegram ownership

- `/start`, `/menu`, Signal V10 and market callbacks => Signal V10 Hub.
- `binance` / `binance:*` callbacks => Binance approval control only.
- This prevents old Binance menu handlers from masking the V10 Hub.

## Guardrails

- SIGNAL ONLY has no execution authority.
- All three AI responses are required for official V10 promotion.
- Missing data => WAIT/reject, never fabricated evidence.
- Transient provider failure leaves candidate pending for bounded retry until TTL; successful provider batch results may be reused briefly to avoid wasting tokens.
- Signal V10 and Binance Auto state are not used to approve each other's trades.
- V10 historical WR uses only closed V10 outcomes.
