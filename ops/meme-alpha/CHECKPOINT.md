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
- Scanner/radar/trend/signer/live executor: ACTIVE on the currently installed production version
- Live executor architecture: multi-position
- Hard max live position count: NONE
- Duplicate mint protection remains
- Exit/sell remains allowed when entry gate is closed

### Current production executor
- v3.42 Capital-Utilization-First: PRODUCTION ACTIVE.
- Production executor SHA256: `077425b0744b17d22dbbaca23a5b130840640651ea2942fe919542462a0c5b88`
- Confirmed production capabilities:
  - continuous allocation
  - capital-utilization-first
  - free capital boosts new buys
  - equity growth scales absolute new-buy size
  - dynamic network exit headroom
  - no hard position-count limit
  - rotation to stronger opportunities
  - hard security/sellability fail-safes retained

### Important runtime discrepancy found by v3.50 pre-upgrade audit
Workflow run: `33981393887`
- `run-paper.sh` currently shows `LIVE_SIGNAL_MAX_AGE_SEC=6000`, NOT 60.
- This supersedes the older v3.44 audit statement that TTL 60 was active.
- Continuity topology is still present, but 6000 seconds is too permissive for signal freshness.
- v3.51 installer explicitly resets this to exactly `LIVE_SIGNAL_MAX_AGE_SEC=60`.
- Until v3.51 is installed, do NOT claim the current production signal TTL is 60 seconds.

### v3.51 Adaptive Alpha Stack
Status: CODED + SELF-TESTED + STAGED. NOT YET PRODUCTION ACTIVE.
Stage workflow run: `33981779575`
Git commit that triggered stage: `13f7f75d6e5abfe8ddd3aa0505a95025c7f60a21`
Staged executor SHA256: `68230517180a7867ec0b4b8a0068d9ab7e07ed1bc62324c498902969b638e2ab`
Staged installer:
`/opt/meme-alpha/app/runtime-status/v351-stage/install-v351.sh`

Self-test confirmed:
- `MICRO_EXECUTOR_V351_ADAPTIVE_ALPHA_SELF_TEST=PASS`
- `REALTIME_POOL_PULSE_INTEGRATION=TRUE`
- `ONCHAIN_WHALE_FLOW_INTEGRATION=TRUE`
- `ONLINE_EXPECTANCY_LEARNING=TRUE`
- `OPPORTUNITY_COST_ROTATION=TRUE`
- `JITO_REGION_RACE_WITH_SAFE_FALLBACK=TRUE`
- `EXECUTION_FEEDBACK_LOOP=TRUE`
- `ADAPTIVE_FAST_LOOP_MS=1500`
- inherited continuous allocation/capital-utilization/equity-scale/multi-position/safety markers remain TRUE

v3.51 upgrade contents:
1. Event-driven realtime pool pulse using Solana WebSocket account subscriptions for top radar pair accounts.
2. On-chain whale-flow intelligence from token supply + largest-account concentration changes; no paid provider key required.
3. Online expectancy learning from completed live trades, with shrinkage to reduce overfitting on small sample counts.
4. Candidate ranking and allocation include learned expectancy, realtime activity, whale-flow quality, liquidity, impact, flow and trend.
5. Opportunity-cost rotation compares new opportunity edge against held positions and includes estimated switching impact.
6. Jito Singapore/Tokyo region race for signed transactions with Jupiter Execute fallback if Jito submission fails.
7. Execution feedback logging: route, submit latency, confirmation latency, total latency, signature.
8. Executor loop reduced from ~4s to 1.5s; exit quote cache reduced from 10s to 5s; confirmation polling tightened.
9. Radar candidate enrichment ceiling increased from 60 to 90 and radar loop sleep is changed from 5s to 1s at install time.
10. Signal TTL is corrected from the discovered 6000 seconds to 60 seconds.
11. Existing root policy, sellability, holder-cluster, mint/freeze, Token-2022, liquidity, exact price-impact, signer isolation and fail-close safety remain.

### v3.51 deployment status
- GitHub self-hosted runner staged and self-tested v3.51 successfully.
- Automatic root install was attempted and blocked by the expected root boundary: `sudo: a password is required`.
- Current production remains v3.42 until the root installer is run.
- Required one-time production activation command:

```bash
/opt/meme-alpha/app/runtime-status/v351-stage/install-v351.sh
```

- Installer has backup + rollback and preserves live position mints before/after activation.
- Expected success marker:
`V351_ADAPTIVE_ALPHA_PRODUCTION_ACTIVE=TRUE`

### Prepared post-activation audit
- Audit script: `ops/meme-alpha/v352-post-v351-audit.sh`
- Audit workflow: `.github/workflows/meme-alpha-v352-post-v351-audit.yml`
- It checks executor hash/markers, signal TTL, services, state version, open positions, learning state, realtime/whale intel health, live SOL and nonzero token-account count.
- Do not mark v3.51 PRODUCTION ACTIVE until this audit or equivalent runtime evidence confirms installation.

### Latest on-chain wallet state previously confirmed
This is historical until refreshed after v3.51 activation:
- SOL: `0.439392033`
- Non-zero live token accounts: 4
- Previously observed holdings:
  - `8PzFWyLpCVEmbZmVJcaRTU5r69XKJx1rd7YGpWvnpump`
  - `9Pfync3ejPC9eHqVzq3nYQJAhyhjqpnB9UsaSfLxpump`
  - `Cy1GS2FqefgaMbi45UunrUzin1rfEmTUYnomddzBpump`
  - `G8aVC4nk5oPWzTHp4PDm3kAuixCebv9WRQMD93h9pump`
Do not assume balances/holdings are unchanged without a fresh chain audit.

### Provider note
The pre-upgrade runtime audit found no configured Birdeye/Helius/Jito API-key environment variables. v3.51 therefore implements immediate no-key realtime/on-chain intelligence and no-key Jito transaction endpoints. Birdeye/Helius labeled-wallet or LaserStream-grade data can be added later if credentials are intentionally provisioned, but v3.51 does not depend on them to run.

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
