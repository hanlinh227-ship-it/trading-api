# V77.16.9 Hyro-Only Prop Shell — Direct Promotion

Date: 2026-08-18

## Canonical state

- `cloudflare-worker/index.js` is now the V77.16.9 Telegram/PROP wrapper.
- `cloudflare-worker/engine-v77168.js` preserves the complete V77.16.8 trading engine blob unchanged.
- The wrapper delegates all scanner, Signal, Symbol, LIVE ORDERS, lifecycle and scheduled cron behavior to `engine-v77168.js`.
- Only Telegram menu/PROP handling and `/status` shell metadata are overridden.

## PROP scope

PROP is HYROTRADER ONLY.

Buttons:
- HYROTRADER overview
- HYRO orders
- HYRO risk
- HYRO connection

Current safety state:
- account/API: NOT CONNECTED
- auto trade: OFF
- risk firewall: SHELL READY
- Signal Hub remains independent from HyroTrader

## Important invariant

Do NOT run the old `apply_v77169_hyro_only_prop_shell.js` against the wrapper file. The old migration expected monolithic V77.16.8 `index.js` and is now superseded by this direct-promotion architecture.

## Why this architecture

GitHub Actions was not creating workflow runs. Direct Git object promotion was used instead, preserving the proven V77.16.8 engine byte-for-byte while exposing the new V77.16.9 role shell.

## Commit

Direct promotion commit: `78fa58ebf2aac355f85c778a7d40d5e2a546d28c`
