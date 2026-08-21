# V10 SIGNAL ONLY — MASTER STATE

Status: canonical source-of-truth for Telegram Signal Only V10 architecture on GitHub `main`.
Revision: V10-FINAL-CRYPTO-SCALP-COMPLETION — 2026-08-21.

## Separation

- Signal Only V10: Cloudflare scanner/advisory + dedicated VPS three-AI council + Telegram signal lifecycle.
- Binance Auto: separate VPS approval/execution project. Signal V10 does not grant Binance execution authority.
- Legacy V77/V78 files are compatibility scanner internals only, not public version authority and not V10 WR history.

## Active entry path

`cloudflare-worker/index.js` -> `hub-v10-unified-entry.js` -> `hub-v10-unified-v2.js` for Telegram UX and `signal-v10-scheduled-v2.js` for cron.

## Lifecycle

1. Scan Forex, Crypto, Metal and Index.
2. Re-analyse every actionable candidate immediately before V10 admission.
3. Only positive-price quotes with explicit `fresh === true` are trusted. Missing, stale, unknown-freshness and refresh-failed quotes fail closed.
4. Entry Intelligence and pre-gate validate plan completeness, geometry, RR and market-specific quality.
5. Up to three candidates are sent to the isolated VPS council.
6. Claude reviews context/regime/timing; DeepSeek challenges edge/risk; Codex checks quantitative/logical consistency.
7. All three provider responses must be valid. At least two must align with the proposed direction and no reviewer may oppose it.
8. Accepted V10 signals are sent to Telegram. Rejected candidates are not official BUY/SELL signals.
9. TP/SL lifecycle uses newly loaded verified-fresh quotes only.
10. OPEN rows remain visible until lifecycle records WIN, LOSS or EXPIRED; closed rows move to history rather than being deleted.
11. V10 learning uses only V10 WIN/LOSS outcomes for WR and is idempotent against repeated processing.

## Crypto scalp policy

Crypto is intentionally less restrictive than Forex/Metal/Index because the Signal-only objective is frequent, short-horizon opportunity discovery while retaining hard data integrity.

- Target scan cadence: 1 minute.
- Base quality floor: 64.
- Minimum structural RR at V10 advisory gate: 1.10.
- Three-AI aligned confidence floor: 60% for Crypto.
- All three AI reviews are still required.
- At least 2/3 must support the proposed direction.
- Any opposite-direction reviewer blocks promotion.
- Accepted Crypto signal TTL: 2 hours.
- A Crypto symbol with at least 8 closed samples and observed WR below 45% receives a +6 quality penalty.
- Verified-fresh quote, Entry/SL/TP completeness, valid LONG/SHORT geometry and Entry Intelligence remain mandatory.
- Unknown quote freshness is treated as unverified, not fresh.

Forex, Metal and Index thresholds are unchanged by this Crypto tuning.

## Telegram model

- `📚 LỆNH ĐANG CHẠY`: V10 OPEN plus active compatibility books.
- `🔥 V10 CHÍNH THỨC`: accepted three-AI V10 signals only.
- `🔍 QUÉT MỚI`: candidates; rejects display as `SETUP BỊ LOẠI — KHÔNG PHẢI LỆNH`.
- `🕘 LỊCH SỬ`: closed V10 outcomes plus compatibility history.
- `📈 THỐNG KÊ`: observed closed V10 outcomes only.
- `🧠 3 AI`: pending/review/health state.
- `🟨 BINANCE AUTO`: separate callback namespace and execution project.

## Guardrails

- SIGNAL ONLY has no execution authority.
- Missing/unverified data => WAIT/reject; evidence is never fabricated.
- Real LONG/SHORT AI disagreement blocks promotion.
- Historical learning is bounded and cannot rewrite source code.
- Binance Auto hard-risk controls and execution authority are not modified by Signal V10 tuning.
- No daily signal quota; Crypto frequency comes from one-minute discovery plus a purpose-built scalp advisory gate.
- A GitHub source commit is not proof of Cloudflare/VPS deployment; production runtime requires deployment evidence.

## Runtime source of truth

Cloudflare `main`:
- `cloudflare-worker/index.js`
- `cloudflare-worker/hub-v10-unified-entry.js`
- `cloudflare-worker/hub-v10-unified-v2.js`
- `cloudflare-worker/signal-v10-scheduled-v2.js`
- `cloudflare-worker/signal-v10-council.js`
- `cloudflare-worker/signal-v10-learning.js`
- `cloudflare-worker/providers/entry-intelligence.js`

Dedicated VPS:
- `signal-only-v10/ai_council_worker.py`
- `signal-only-v10/runtime/install_signal_v10.sh`
- `signal-only-v10/runtime/update_signal_v10.sh`

Systemd:
- `signal-v10-council.service`
- `signal-v10-update.timer`
