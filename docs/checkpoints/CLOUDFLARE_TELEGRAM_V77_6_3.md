# CLOUDFLARE / TELEGRAM V77.6.3

Updated: 2026-08-18 UTC+7
Status: stable manual-scan repair after V77.6.2 clean Telegram UI.

## Root cause fixed

Crypto could remain stuck on the Telegram message `Đang quét CRYPTO...` because external provider fetches had no hard timeout, Binance/Bybit/OKX bulk requests were sequential, and a manual Telegram scan redundantly managed all open Forex/Crypto/Metal lifecycle positions before starting discovery. That lifecycle pass could consume Twelve Data Grow55 credits before Crypto deep analysis.

## V77.6.3 fixes

- Adds a bounded external fetch timeout for Twelve Data, Binance, Bybit and OKX.
- Adds an overall discovery deadline so a provider cannot hold Telegram indefinitely.
- Runs Binance/Bybit/OKX bulk ticker requests concurrently with `Promise.allSettled`.
- Manual Telegram `/run-now?group=...` discovery no longer performs all-group lifecycle checks first. Cron remains the sole once-per-minute lifecycle manager for existing MARKET/LIMIT positions.
- Telegram catches scan deadline/provider failures and returns a compact safe message instead of remaining stuck on `Đang quét`.
- Keeps V77.6.2 clean Telegram behavior: no raw Broad lỗi / Deep lỗi in the operator UI. Raw diagnostics remain available in `/run-now`, Worker logs and KV last-run state.
- Applies timeout protection consistently to Forex, Crypto and Metal provider calls.

## Canonical safety

This is an operational reliability fix. It does not alter V73 frozen status, V74 live authority, V75 data role or V76 R2 research-only lock.

## Deploy test order

1. `/status` must report V77.6.3.
2. Telegram FOREX must return a final summary, not hang.
3. Telegram CRYPTO must return a final summary or compact timeout-safe note, never remain only on `Đang quét`.
4. Telegram METAL must return a final summary, not hang.
5. Cron logs should continue lifecycle checks without starting discovery scans.
