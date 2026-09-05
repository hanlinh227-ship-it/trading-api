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
- v3.42 Capital-Utilization-First: PRODUCTION ACTIVE and runtime-audited.
- Production executor SHA256: `077425b0744b17d22dbbaca23a5b130840640651ea2942fe919542462a0c5b88`
- v3.42 runtime markers confirmed:
  - `CAPITAL_UTILIZATION_FIRST=TRUE`
  - `FREE_CAPITAL_BOOSTS_NEW_BUYS=TRUE`
  - `MULTI_POSITION_NO_HARD_COUNT_LIMIT=TRUE`
- v3.36 autonomous features remain inherited:
  - continuous allocation
  - equity growth scales new buys
  - dynamic network exit headroom
  - multi-position, no hard count limit
  - rotation to stronger opportunity
  - hard security/sellability fail-safes retained

### v3.41 Continuity Scan
Status: PRODUCTION ACTIVE and runtime-audited.
Confirmed runtime markers:
- `LIVE_SIGNAL_MAX_AGE_SEC=60`
- `CONTINUITY_SCAN=KEEP_LAST_SAFE_GATE_DURING_REFRESH`
- `close_entry_gate 'FULL_CYCLE_FAILED'`
- paper execution remains disabled
Interpretation:
- a healthy full refresh no longer closes entry merely because refresh is running;
- failed refresh still closes entry immediately;
- excessive staleness still fail-closes.

### v3.44 Post-Activation Audit
Status: PASS.
Workflow run: `33981066349`
Git commit: `44bbd9f8a86dbfcc8f8a6918105f7eb685af9d11`
Confirmed on VPS/runtime:
- v3.42 executor marker: TRUE
- capital-utilization-first marker: TRUE
- free-capital boost marker: TRUE
- no hard position count limit marker: TRUE
- v3.41 signal TTL 60: TRUE
- v3.41 continuity marker: TRUE
- full-cycle fail-close: TRUE
- paper execution disabled: TRUE
- executor processes: 1
- signer processes: 1
- `meme-alpha-paper.service`: active
- `meme-alpha-micro-live.service`: active
- audit result: `V344_POST_ACTIVATION_AUDIT=PASS`
Note: the audit did not find the expected state file at `runtime-status/micro-live-state.json`; this does not invalidate executor/service activation, but live position count was therefore not refreshed by v3.44.

### Latest on-chain wallet state previously confirmed
This is the latest blockchain-confirmed snapshot on record, not necessarily current after later live trading:
- SOL: `0.439392033`
- Non-zero live token accounts: 4
- Previously observed holdings:
  - `8PzFWyLpCVEmbZmVJcaRTU5r69XKJx1rd7YGpWvnpump`
  - `9Pfync3ejPC9eHqVzq3nYQJAhyhjqpnB9UsaSfLxpump`
  - `Cy1GS2FqefgaMbi45UunrUzin1rfEmTUYnomddzBpump`
  - `G8aVC4nk5oPWzTHp4PDm3kAuixCebv9WRQMD93h9pump`
Do not assume these balances/holdings are still identical without a fresh chain audit.

### Current operating intent
- Do not cap the number of held coins for strategy reasons.
- If deployable SOL remains and a new candidate passes the full safety/quality pipeline, the bot may continue allocating to additional positions.
- Free capital should increase new-buy pressure rather than being held idle solely because portfolio exposure is already high.
- Equity growth should increase absolute new-entry size.
- Stronger opportunities may trigger capital rotation from weaker holdings.
- Keep only dynamic technical/network exit headroom and root-policy safety floor, not a strategic cash-hoarding reserve.

### Deployment/security rules
- NEVER grant `NOPASSWD: ALL`.
- NEVER make GitHub runner root.
- Keep signer isolation and private-key boundary intact.
- Root-level installers must have backup + rollback.
- Preserve sellRoute/security/holder/mint/freeze/Token-2022/price-impact/data-freshness fail-safes.
- Strategy may be autonomous; invalid/unsafe transaction prevention remains fail-closed.

## One command to view the latest checkpoint on VPS
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
