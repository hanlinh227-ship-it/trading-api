# V77.18.15 — DUAL HYRO ACCOUNTS

Updated: 2026-08-18 UTC+7

## PURPOSE
Operate two HyroTrader accounts from one PROP Telegram hub without sharing execution state or mirroring trades.

## ACCOUNT A / TK1
- Existing account and all existing keys/state remain untouched.
- Uses legacy Hyro secrets: `HYRO_BYBIT_API_KEY/SECRET` for Challenge Demo and legacy LIVE names later if funded.
- Existing KV namespaces remain canonical and are not migrated/reset.

## ACCOUNT B / TK2
- New isolated scope prefix: `v771815:hyro:B:` applied to all Hyro module KV keys.
- Uses separate secrets:
  - `HYRO_B_BYBIT_API_KEY`
  - `HYRO_B_BYBIT_API_SECRET`
  - optional later funded: `HYRO_B_BYBIT_LIVE_API_KEY`, `HYRO_B_BYBIT_LIVE_API_SECRET`
  - `HYRO_B_BYBIT_MODE` (normally DEMO for Challenge)
  - `HYRO_B_AUTO_EXECUTION` (default OFF unless explicitly true)
- If B profile is missing, rules are cloned from A as configuration only; balances/orders/execution/notifications/position manager/portfolio state are never cloned.

## TELEGRAM HUB
PROP opens a two-account hub:
- `Tổng 2 TK`
- `TK1`
- `TK2`

Each account has independent:
- Tổng quan
- Vị thế
- Risk
- Kết nối
- Quét
- Auto pause/resume

Summary shows equity, daily P/L, active positions and AUTO state for each account.

## CRON / EXECUTION
- One orchestrator runs A then B each minute.
- No duplicate legacy A cron is allowed.
- B is skipped if B credentials are missing.
- Account A preserves current runtime behavior and state.

## CROSS-ACCOUNT ANTI-MIRROR
Hyro support prohibits copy/mirroring/coordinated multi-account trading. Therefore V77.18.15 adds a global anti-mirror registry `v771815:hyro:anti_mirror`.
- A recent executed symbol+side is excluded from B and vice versa for 6 hours.
- Runtime receives `excludedSignatures` before candidate execution.
- This is additional to each account's own 3-slot portfolio guard.

## STATE CONTINUITY
Never reset/delete:
- Signal LIVE ORDERS / `v775:books`
- all existing TK1 Hyro state
- `v771811:hyro:manage:*`
- `v771814:hyro:portfolio`
- `v771815:hyro:B:*`
- `v771815:hyro:anti_mirror`
- PERSONAL state

## DEPLOYMENT GATE
Do not call V77.18.15 production active until Cloudflare build is green and 100% traffic. After deploy verify:
1. PROP shows `Tổng 2 TK`, `TK1`, `TK2`.
2. TK1 still shows the same equity/state as before deploy.
3. TK2 shows credentials missing/off until its dedicated secrets are added.
4. After adding B secrets, TK2 telemetry connects to its own account/UID/equity.
5. `HYRO_B_AUTO_EXECUTION` remains OFF until account identity, telemetry, position/risk/native SLTP gates are verified.
6. Anti-mirror prevents same symbol+side execution across the two accounts.
