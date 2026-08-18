# V77.18.0 — CONSOLIDATED AUTO-READY STATE

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
- Max 2 concurrent Hyro positions, no duplicate active symbol.
- Manual Pause blocks new Hyro entries and cancels pending orders, but monitoring and existing-position protection continue.

## Hyro auto source
- Auto PROP trades use `hyro-scanner.js` only, independent from SIGNAL.
- Dynamic Bybit USDT perpetual universe; broad liquidity filter then H1/M15/M5 deep scan.
- Existing symbol-specific knowledge remains in Signal engine; dynamic Hyro scanner uses a stricter generic fallback for additional Bybit symbols.

## Telegram PROP contract
Telegram PROP is an ACCOUNT DASHBOARD, not an auto-signal feed.
It may show:
- configured account/phase/program/drawdown type
- balance/equity/available
- daily P/L in USD
- intraday peak and drawdown from peak
- open positions and each unrealized P/L
- total floating P/L, open-risk estimate, pending count
- connection/auto/pause status
It MUST NOT announce, push, or mirror Hyro auto-entry orders to Telegram.

## Execution safety defaults
- `HYRO_BYBIT_MODE` defaults to `DEMO`.
- `HYRO_AUTO_EXECUTION` defaults OFF.
- Required Cloudflare secrets: `HYRO_BYBIT_API_KEY`, `HYRO_BYBIT_API_SECRET`.
- Auto order requires: complete profile + API telemetry connected + not paused + auto secret true + daily target not reached + risk firewall pass + plan RR >= 1.5.
- Execution uses idempotency KV and native Bybit SL/TP.

## Cleanup rule
Old auto-promotion migration workflows and `scripts/apply_v*.js` are superseded by this canonical state and should not remain active on main. Audit/validation/research files may remain if they do not rewrite canonical production code.

## Cloudflare deployment note
GitHub canonical is prepared. Cloudflare runtime must deploy `cloudflare-worker/index.js` with the same KV binding `TRADING_STATE`; do not delete or recreate the namespace during deployment.
