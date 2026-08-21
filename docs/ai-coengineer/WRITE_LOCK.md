# AI WRITE LOCK

LOCKED: true
OWNER: CHATGPT
SCOPE: V10-CRYPTO-SCALP-THROUGHPUT-R2
ACQUIRED: 2026-08-21

## Allowed writes
- signal-only-v10/ai_council_worker.py
- docs/ai-coengineer/WRITE_LOCK.md

## Intent
- Reduce avoidable Crypto scalp starvation without weakening verified-fresh quote, Entry/SL/TP geometry, V10 pre-gate, or three-provider completeness.
- Increase council batch throughput so 1-minute Crypto scanning does not create an avoidable AI-review backlog.
- Make AI review instructions explicitly Crypto-scalp aware: missing optional derivatives microstructure alone must not fabricate a rejection; reviewers must judge supplied evidence and prefer WAIT over an unsupported reversal.
- Preserve Signal V10 / Binance Auto separation.
