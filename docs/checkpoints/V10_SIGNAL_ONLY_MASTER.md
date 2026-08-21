# V10 SIGNAL ONLY — MASTER STATE

Status: production architecture source-of-truth for Telegram Signal Only.

## Separation

- Signal Only V10: Cloudflare scanner/advisory + VPS three-AI council + Telegram signal lifecycle.
- Binance Auto: separate VPS approval/execution project. Signal V10 never grants Binance order authority.
- Legacy V77/V78 files remain compatibility scanner internals only. Public version authority is V10.

## Signal lifecycle

1. Scan market universe (Forex, Crypto, Metal, Index).
2. Existing engine produces fresh analyses and structural plans.
3. V10 pre-gate checks evidence freshness, Entry Intelligence, plan completeness, RR and quality.
4. Up to three candidates are batched to the VPS council.
5. Claude: context/regime/timing specialist.
6. DeepSeek: adversarial edge/risk specialist.
7. Codex: quantitative/logical consistency specialist.
8. All three providers must return a valid review. Promotion requires at least two reviewers aligned with the proposed direction, no reviewer taking the opposite direction, and directional confidence >=64.
9. Accepted V10 signal is sent to Telegram. Candidate-only output is not an official signal.
10. Existing signal lifecycle records TP/SL outcomes.
11. V10 learning ledger incrementally learns by market, symbol, and strategy from closed outcomes only.
12. Learning may make small bounded ranking/quality adjustments. It never rewrites source code or turns historical win-rate into a promised future probability.

## Win-rate semantics

Telegram shows `Observed WR`, sample size `n`, Bayesian-smoothed WR, 80% Wilson lower bound, and AvgR when available. These are descriptive closed-signal statistics, not guaranteed or calibrated future win probabilities.

## Quality/frequency balance

- Review up to 3 actionable candidates per scan in one AI batch.
- Base V10 quality floor is market-specific (roughly high-B range) rather than A-only.
- Historical learning adjustment is bounded to avoid overfitting small samples.
- Real LONG/SHORT disagreement blocks promotion.
- A third reviewer may WAIT; unanimity is not required.
- No trade quota is imposed by Signal V10; frequency comes from market scans and candidate quality.

## Runtime source of truth

Cloudflare:
- `cloudflare-worker/index.js`
- `cloudflare-worker/hub-v10.js`
- `cloudflare-worker/signal-v10-council.js`
- `cloudflare-worker/signal-v10-learning.js`

VPS council branch `auto-futures-v1`:
- `signal-only-v10/ai_council_worker.py`
- `signal-only-v10/runtime/install_signal_v10.sh`

## Guardrails

- SIGNAL ONLY has no execution authority.
- All three AI responses are required for official V10 promotion.
- Missing data => WAIT/reject, never fabricated evidence.
- Provider budget limits are shared with existing AI budget governance.
- Signal V10 and Binance Auto state are not used to approve each other's trades.
