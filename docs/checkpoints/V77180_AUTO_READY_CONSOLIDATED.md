# V77.18.2 — CONSOLIDATED AUTO-READY STATE

## Canonical architecture
- `cloudflare-worker/index.js` is the only production entrypoint.
- SIGNAL, PROP and PERSONAL are independent runtimes.
- SIGNAL: Telegram signal scanning/reporting only. It does not feed PROP or PERSONAL execution.
- PROP/HyroTrader: independent Bybit scanner + risk/execution + account telemetry. Auto entries are SILENT on Telegram.
- PERSONAL: reserved independent runtime; no routing from SIGNAL or PROP.

## Backward-compatible runtime state — NEVER DELETE OR RESET
- Existing Signal/LIVE ORDERS state owned by legacy V77.16.8 engine remains untouched.
- Hyro profile: `v7717:hyro:profile`
- Hyro setup draft: `v77171:hyro:draft`
- Hyro manual control: `v77173:hyro:control`
- Hyro telemetry/runtime namespace: `v7718:hyro:*`
- Future versions must read these keys before introducing replacements and must migrate non-destructively.

## Hyro account policy
- Wizard: Challenge/Funded -> account size -> Standard/Trailing or Swing/Static -> One-Step/Two-Step when Challenge.
- Daily strategy profit objective: fixed +5% of configured account size.
- Risk firewall always has priority over profit objective.
- Internal daily hard stop remains below 3% account size.
- Structural native SL, adaptive structure/liquidity TP, minimum planned RR 1.5.
- Maximum 2 active Hyro symbols total across filled positions + pending orders.
- No duplicate active symbol.
- Manual Pause blocks new Hyro entries and cancels pending orders, but monitoring and existing-position protection continue.
- Reaching daily +5% or daily hard stop cancels remaining pending orders and blocks new entries.

## Hyro auto source
- Auto PROP trades use `hyro-scanner.js` only, independent from SIGNAL.
- Dynamic Bybit USDT perpetual universe; broad liquidity filter then H1/M15/M5 deep scan.
- Auto execution does not consume Telegram SIGNAL entries.
- Existing symbol-specific knowledge remains preserved in Signal engine; Hyro dynamic scanner is a separate stricter fallback for the prop account.

## Telegram PROP contract
Telegram PROP is an ACCOUNT DASHBOARD, not an auto-signal feed.
It shows only account/runtime state such as:
- configured account/phase/program/drawdown type
- wallet/equity/available
- equity P/L today in USD
- gross realized profit today
- gross realized loss today
- net realized P/L today
- current floating P/L
- intraday peak and drawdown from peak
- live positions and each position unrealized P/L
- pending count and open-risk estimate
- connection/auto/pause status
It MUST NOT announce, push, mirror, or expose Hyro auto-entry candidates/orders to Telegram.

## Execution safety defaults
- `HYRO_BYBIT_MODE` defaults to `DEMO`.
- `HYRO_AUTO_EXECUTION` defaults OFF.
- Required Cloudflare secrets: `HYRO_BYBIT_API_KEY`, `HYRO_BYBIT_API_SECRET`.
- Auto order requires: complete profile + API telemetry connected + not paused + auto secret true + daily target not reached + daily hard stop not reached + active-slot/risk firewall pass + plan RR >= 1.5.
- Execution uses idempotency KV and native Bybit SL/TP.

## Cleanup completed
- Legacy `.github/workflows/apply-v*.yml` auto-promotion workflows were removed from `main`.
- Legacy `scripts/apply_v*.js` migration scripts were removed from `main`.
- Audit/validation/research assets were preserved where they do not rewrite canonical production code.
- All KV namespaces/state, LIVE ORDERS state, market data, symbol knowledge and current engine modules were preserved.

## Cloudflare deployment contract
- Deploy only `cloudflare-worker/index.js` as canonical entrypoint.
- Preserve existing `TRADING_STATE` KV namespace ID; never recreate or clear the namespace during deploy.
- `prepare-wrangler.mjs` already requires the existing `TRADING_KV_NAMESPACE_ID`, keeps vars, and points `main` to `index.js`.
- Cloudflare account deployment itself is not modified by GitHub connector; source is ready for deployment once the existing Cloudflare project pulls/deploys current main.
