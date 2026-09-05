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
- Live executor architecture: multi-position
- Hard max live position count: NONE
- Duplicate mint protection remains
- Exit/sell remains allowed when entry gate is closed

### Current production executor — v3.51 Adaptive Alpha Stack
Status: **PRODUCTION ACTIVE + RUNTIME AUDITED**.
Production executor SHA256:
`68230517180a7867ec0b4b8a0068d9ab7e07ed1bc62324c498902969b638e2ab`

Confirmed production capabilities:
- continuous allocation
- capital-utilization-first
- free capital boosts new buys
- equity growth scales absolute new-buy size
- dynamic network exit headroom
- no hard position-count limit
- online expectancy learning from completed live trades
- realtime pool-pulse integration
- on-chain whale/holder-flow intelligence module
- opportunity-cost rotation with switching-cost adjustment
- Jito Singapore/Tokyo region race with Jupiter Execute fallback
- execution feedback loop (submit/confirm/total latency + route)
- executor loop ~1.5s
- exit quote cache ~5s
- radar enrichment ceiling 90; install changed radar cadence to 1s
- hard security/sellability/mint/freeze/Token-2022/liquidity/price-impact/signing fail-safes retained

### v3.52 post-activation audit
Workflow run: `33982149540`
Audit commit: `3debeb86547224d90589eea67cbc6a3a83f08fac`
Result: **AUDIT STEP SUCCESS / V352_POST_V351_AUDIT=COMPLETE**.

Confirmed on VPS/runtime:
- `EXECUTOR_SHA_MATCH=TRUE`
- `V351_EXECUTOR_MARKER=TRUE`
- `ONLINE_LEARNING_MARKER=TRUE`
- `JITO_ROUTER_MARKER=TRUE`
- `SIGNAL_TTL_60=TRUE`
- `PAPER_EXECUTION_DISABLED=TRUE`
- `meme-alpha-micro-live.service=active`
- `meme-alpha-paper.service=active`
- `meme-alpha-realtime-pulse.service=active`
- `meme-alpha-whale-flow.service=active`
- `meme-alpha-signer.service=active`

Runtime freshness snapshot from that audit:
- realtime pool pulse: `HEALTHY`, age ~0.10s, 32 rows
- safe signal age: ~38.97s, 18 rows
- micro-live entry gate: `true`, age ~38.94s
- signal TTL fixed to exactly 60 seconds (older 6000-second discrepancy is resolved)

### Current live wallet snapshot from v3.52
On-chain confirmed at audit time:
- LIVE SOL: `0.153814036`
- Non-zero SPL token accounts: `5`

Do not assume this balance/count remains identical after later live trades.

### Whale-flow note
The whale-flow service itself is ACTIVE, but at the v3.52 snapshot its output was:
- status: `DEGRADED`
- rows: `0`
A v3.53 debug showed the current signal snapshot had **no candidate simultaneously matching `securityDecision=PASS` and `holderClusterDecision=PASS`**, so the module had no eligible mint to inspect at that instant (`CANDIDATE_MINT=NONE`). This is not evidence that the service crashed; it is currently an empty-input/degraded state. The executor treats unavailable/degraded whale intelligence as neutral rather than bypassing hard safety gates.

### State visibility note
The GitHub runner reported `STATE_UNREADABLE_OR_MISSING=TRUE` for `/var/lib/meme-alpha/data/micro-live/state.json`. The live services/executor are active and chain state was independently confirmed, but runner permissions prevented refreshing the internal open-position list/learning counters in the audit. Do not infer internal position count from this flag.

### Current operating intent
- Do not cap number of held coins for strategy reasons.
- If deployable SOL remains and a candidate passes the full safety/quality pipeline, bot may continue allocating to additional positions.
- Free capital should increase new-buy pressure instead of being held idle solely because portfolio exposure is already high.
- Equity growth should increase absolute new-entry size.
- Stronger opportunities may rotate capital from weaker holdings after estimated switching cost.
- Only technical/network exit headroom and root-policy safety floor remain as reserve constraints.

### Deployment/security rules
- NEVER grant `NOPASSWD: ALL`.
- NEVER make GitHub runner root.
- Keep signer isolation/private-key boundary intact.
- Root-level installers must have backup + rollback.
- Preserve sellRoute/security/holder/mint/freeze/Token-2022/price-impact/data-freshness fail-safes.
- Strategy may be autonomous; invalid/unsafe transaction prevention remains fail-closed.

## One command to view latest checkpoint on VPS
```bash
cat /opt/meme-alpha/app/runtime-status/MEME_ALPHA_CHECKPOINT.md
```

## Required checkpoint write after each future update
Every future update must end with:
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
