# MEME ALPHA AUTO TRADE — CHECKPOINT

This file is the canonical project checkpoint for the Solana memecoin auto-trading bot.

## Mandatory rule after every update
After EVERY bot update, deployment, runtime change, scanner/radar change, executor change, signer change, risk/gate change, or production audit:
1. Update this file before considering the work complete.
2. Record what is CODED vs STAGED vs PRODUCTION ACTIVE vs ACTUAL ON-CHAIN CONFIRMED.
3. Record any pending root/manual step explicitly.
4. Preserve the exact next action and rollback point.
5. Never claim a live trade unless blockchain/runtime evidence confirms it.

## Resume phrase
If the user says: **"xem lại bot auto trade meme coin"**
- Read this checkpoint first.
- Then inspect current VPS/runtime if needed.
- Continue from the latest confirmed state instead of reconstructing from memory.

## Current confirmed state
Checkpoint date: 2026-09-06 (+07)

### Architecture
- Chain: Solana
- Wallet: Phantom-backed live wallet through isolated signer
- Live execution: ACTIVE
- Demo/paper execution: DISABLED; legacy paper service is scanner/risk/signal only
- New-list radar: ACTIVE
- Scanner: ACTIVE
- Trend pulse: ACTIVE
- Signer: ACTIVE
- Live executor: multi-position architecture
- Hard max live position count: NONE
- Existing positions are stored independently in `st.positions[]`
- Duplicate mint protection remains
- Exit/sell remains allowed when entry gate is closed

### Latest production executor confirmed
- v3.36 Autonomous Portfolio was confirmed production active.
- Production executor SHA256 confirmed at audit: `608785762d5387b58a2bfb4adead1bf29e7cfe9c489472bf7013442a35ab21d2`
- v3.36 features confirmed:
  - continuous allocation
  - equity growth scales new buys
  - dynamic network exit headroom
  - multi-position, no hard count limit
  - rotation to stronger opportunity
  - hard security/sellability fail-safes retained

### Latest live-wallet audit after v3.36
- SOL: `0.439392033`
- Non-zero live token accounts: 4
- Holdings observed:
  - `8PzFWyLpCVEmbZmVJcaRTU5r69XKJx1rd7YGpWvnpump` — 8477.346201
  - `9Pfync3ejPC9eHqVzq3nYQJAhyhjqpnB9UsaSfLxpump` — 1103.014859
  - `Cy1GS2FqefgaMbi45UunrUzin1rfEmTUYnomddzBpump` — 4918.032166
  - `G8aVC4nk5oPWzTHp4PDm3kAuixCebv9WRQMD93h9pump` — 1828.811494
- 4/4 live positions were preserved after v3.36 upgrade.

### Scanner/gate bottleneck discovered
- Radar observed healthy and fresh (~1s in one audit), 100 radar candidates.
- Trend observed fresh (~2s in one audit).
- Safe signal snapshot was observed stale (~24.9s) while full scan was running.
- Old scan topology closes/blocks entry during long full-cycle refresh windows.

### v3.41 Continuity Scan
Status: STAGED, NOT YET CONFIRMED PRODUCTION ACTIVE.
Purpose:
- stop closing entry merely because a full refresh starts;
- keep last safe signal usable during refresh;
- only close on failed refresh or excessive staleness;
- keep paper execution disabled.
Staged installer:
`/opt/meme-alpha/app/runtime-status/v341-stage/install-v341.sh`
Success marker:
`V341_CONTINUITY_SCAN_PRODUCTION_ACTIVE=TRUE`

### v3.42 Capital-Utilization-First
Status: STAGED, SELF-TEST PASS, NOT YET CONFIRMED PRODUCTION ACTIVE.
Self-test markers:
- `CAPITAL_UTILIZATION_FIRST=TRUE`
- `FREE_CAPITAL_BOOSTS_NEW_BUYS=TRUE`
- `EQUITY_GROWTH_SCALES_NEW_BUYS=TRUE`
- `DYNAMIC_NETWORK_EXIT_HEADROOM=TRUE`
- `MULTI_POSITION_NO_HARD_COUNT_LIMIT=TRUE`
- `ROTATION_TO_STRONGER_OPPORTUNITY=TRUE`
Staged executor SHA256:
`077425b0744b17d22dbbaca23a5b130840640651ea2942fe919542462a0c5b88`
Staged installer:
`/opt/meme-alpha/app/runtime-status/v342-stage/install-v342.sh`
Expected success marker:
`V342_CAPITAL_UTILIZATION_PRODUCTION_ACTIVE=TRUE`

### Deployment/security rules
- NEVER grant `NOPASSWD: ALL`.
- NEVER make GitHub runner root.
- Keep signer isolation and private-key boundary intact.
- Root-level installers must have backup + rollback.
- Preserve sellRoute/security/holder/mint/freeze/Token-2022/price-impact/data-freshness fail-safes.
- Strategy may be autonomous; invalid/unsafe transaction prevention remains fail-closed.

## One command to view the latest checkpoint on VPS
After checkpoint sync is installed, use:

```bash
cat /opt/meme-alpha/app/runtime-status/MEME_ALPHA_CHECKPOINT.md
```

## Required checkpoint write after each future update
Every future update must end with a checkpoint entry containing:
- timestamp
- version/change name
- git commit/workflow run if applicable
- CODED / SELF-TESTED / STAGED / PRODUCTION ACTIVE / ON-CHAIN CONFIRMED status
- current live positions count if known
- current live SOL if known
- gate/scanner/radar/signer/executor status
- rollback location
- next pending action, or `NONE`

## Important interpretation
"Production active" does not mean "a profitable trade happened".
"Bot active" does not mean "entry gate is open at every instant".
Actual live BUY/SELL must be confirmed from runtime/on-chain evidence before reporting it as fact.
