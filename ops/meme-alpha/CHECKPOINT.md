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
- Inspect current VPS/runtime when needed.
- Continue from the latest confirmed state.

## Current confirmed state
Checkpoint date: 2026-09-06 (+07)

### Production — v3.51 Adaptive Alpha Stack
Status: **PRODUCTION ACTIVE + RUNTIME AUDITED**.
Executor SHA256:
`68230517180a7867ec0b4b8a0068d9ab7e07ed1bc62324c498902969b638e2ab`

Confirmed production:
- multi-position, no hard strategic position-count cap
- capital-utilization-first / free-capital allocation
- equity-growth scaling
- online expectancy learning
- realtime pool pulse
- opportunity-cost rotation
- Jito Singapore/Tokyo submission race + Jupiter fallback
- execution latency feedback
- ~1.5s executor loop
- ~5s exit quote cache
- signal TTL exactly 60s
- demo execution disabled
- hard sellability/security/mint/freeze/Token-2022/liquidity/impact/signer fail-safes retained

### Latest live-chain snapshot
v3.52 audit:
- LIVE SOL: `0.153814036`
- Non-zero SPL token accounts: `5`
This is a point-in-time snapshot only.

### v3.54 integrity audit — PASS
Workflow run: `33982416797`
Confirmed:
- all five core services active
- exactly one live executor process
- realtime pool pulse healthy
- entry gate true at sample time
- signal/security pipeline live

Important correction about state audit:
- `/var/lib/meme-alpha` is `750 meme-alpha:meme-alpha`.
- GitHub runner cannot traverse into the state directory by design.
- Therefore prior `STATE_UNREADABLE_OR_MISSING` was a **runner permission-isolation observation, not evidence the live state file was missing**.
- Do not weaken this directory isolation merely to make audits readable.

### v3.55 whale-flow diagnosis
Workflow run: `33982471856`
Five samples over ~60 seconds all showed:
- eligible `securityDecision=PASS + holderClusterDecision=PASS` candidates: `0`
- whale service process remained active
- output remained `DEGRADED / 0 rows`
- RPC test was not attempted because there was no eligible candidate

Conclusion:
- current whale-flow v3.50 incorrectly labels **empty eligible input** as `DEGRADED`.
- it also only monitors currently eligible entry candidates, so held positions can lack continuous whale/holder concentration monitoring when they disappear from the entry candidate set.

### v3.56 Whale Flow + Portfolio Observability Hardening
Status: **CODED + SELF-TEST PASS + STAGED. NOT PRODUCTION ACTIVE YET.**
Workflow run: `33982627439`
Staged SHA256:
`b77a9f43355a35894e0c95883e52a980e7ac20cc2b70d58df964f84e1129f479`
Staged installer:
`/opt/meme-alpha/app/runtime-status/v356-stage/install-v356.sh`

v3.56 fixes:
- held positions are always included in whale/holder-flow monitoring, even when not current entry candidates
- no eligible candidates => `IDLE_HEALTHY`, not false `DEGRADED`
- `DEGRADED` reserved for real inspection/RPC failure when sources exist
- retries transient RPC calls
- preserves recent good rows instead of immediately erasing intelligence
- exports sanitized `/opt/meme-alpha/app/runtime-status/portfolio-observability.json`
- observability includes state version, open-position count/mints and learning counters, without exposing private keys/secrets
- root state directory isolation stays intact

Self-test markers:
- `V356_WHALE_FLOW_SELF_TEST=PASS`
- `HELD_POSITIONS_ALWAYS_MONITORED=TRUE`
- `NO_CANDIDATES_IS_IDLE_HEALTHY=TRUE`
- `PORTFOLIO_OBSERVABILITY_EXPORT=TRUE`

Automatic GitHub activation was attempted but existing root boundary blocked it:
`sudo: a password is required`
This is intentional privilege separation; current root-owned production source was not bypassed.

### v3.57 one-time Safe AutoDeploy bootstrap
Status: **CODED + STAGED. ROOT BOOTSTRAP NOT YET CONFIRMED ACTIVE.**
Stage workflow run: `33982702207`
Staged command:
`/opt/meme-alpha/app/runtime-status/v357-bootstrap/install-safe-autodeploy.sh`

Purpose:
- install a root-owned fixed `/usr/local/sbin/meme-alpha-safe-deploy` dispatcher
- grant `github-runner` NOPASSWD only to that fixed dispatcher, NEVER `NOPASSWD: ALL`
- dispatcher only accepts allowlisted Meme Alpha source components and allowlisted services
- artifact must be a regular file inside a fixed deploy-candidates directory
- SHA256 is mandatory
- JS syntax is checked as non-root
- backup + rollback is mandatory
- executor deployments preserve arming state and verify exactly one executor process
- bootstrap also activates already staged v3.56 in the same one-time root operation

After v3.57 bootstrap is installed once, future ordinary bot source upgrades can be staged and safely activated from GitHub without asking for a root password each time, while keeping the signer and OS root boundary intact.

### Current operating intent
- do not cap number of held coins for strategy reasons
- deployable capital may continue to be allocated to qualifying opportunities
- held positions must remain actively monitored for exit/safety/flow changes
- stronger opportunities may rotate capital after switching cost
- technical exit/network reserve remains

### Deployment/security rules
- NEVER grant `NOPASSWD: ALL`
- NEVER make GitHub runner root
- keep signer/private-key isolation
- never replace root-owned production files by directory-write tricks
- root deploy path must validate component/path/hash and have backup + rollback
- preserve all hard security and execution fail-safes

## One command to view latest checkpoint on VPS
```bash
cat /opt/meme-alpha/app/runtime-status/MEME_ALPHA_CHECKPOINT.md
```

## Required checkpoint after every future update
Record:
- timestamp
- version/change
- git commit/workflow
- CODED / SELF-TESTED / STAGED / PRODUCTION ACTIVE / ON-CHAIN CONFIRMED
- live position count/SOL if known
- gate/scanner/radar/signer/executor health
- rollback
- next pending action or `NONE`

## Important interpretation
"Production active" does not mean guaranteed profit.
Actual BUY/SELL must be confirmed by runtime/on-chain evidence before reporting it as fact.
