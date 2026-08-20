# Archived one-shot GitHub Actions — V78-020 through V78-024

Archived: 2026-08-20
Owner: ChatGPT
Reason: these workflows were implementation/verification carriers for already-resolved V78 batches. Keeping them active under `.github/workflows/` creates unnecessary Actions noise and can retrigger stale guards. Exact historical content remains immutable in Git history and is addressable by the blob SHAs below.

This archive does **not** remove any validation record, source commit, Cloudflare deployment evidence, or canonical state record. It does not change trading behavior.

| Workflow | Archived blob SHA |
|---|---|
| `.github/workflows/v78-020-entry-intelligence-batch.yml` | `dea7b27ea9426a5dcdec367d8adfc148f2429e19` |
| `.github/workflows/v78-020-production-verify.yml` | `b5845a9c08e37790bf7edf20e6d420fb77ff0f05` |
| `.github/workflows/v78-021-apply.yml` | `4a940ae94a606af360a3e1e0bf68b80b7a28f32e` |
| `.github/workflows/v78-021-apply-v2.yml` | `fa5f9b685394fa5a1932958b9ccf89c5dcb5e534` |
| `.github/workflows/v78-022-apply.yml` | `aebe471b2c20a743640494e79217e61cdbf74193` |
| `.github/workflows/v78-022-fast.yml` | `9da1b1fc04ec334024dfb05cad733d197f39c0b3` |
| `.github/workflows/v78-022-retry.yml` | `5520db2c14bd2679155642f84edb036577887817` |
| `.github/workflows/v78-023-hub-intelligence.yml` | `3a1d15bfe722782bac6e8c2dd7c4281ec30a6c05` |
| `.github/workflows/v78-024-doc-sync.yml` | `5efeadb14632cf06716681b547d2bc7fa64af218` |

## Retained durable evidence

- `docs/ai-coengineer/V78-020_VALIDATION.txt`
- `docs/ai-coengineer/V78-021_VALIDATION.txt`
- `docs/ai-coengineer/V78-022_VALIDATION.txt`
- `docs/ai-coengineer/V78-023_VALIDATION.txt`
- `docs/ai-coengineer/V78-024_VALIDATION.txt`
- `docs/ai-coengineer/SHARED_STATE.md`
- Git commit history and exact blobs listed above.

## Safety invariants

- No `TRADING_STATE` or `v775:books` reset/deletion.
- No risk/freshness/structural-SL/news weakening.
- No Futures/TK2 restore.
- Binance20 remains quarantined.
- No Hyro H1-H6 execution/idempotency/cancel-scope/multi-account change in this archive operation.
- Production Claude API remains paused.
