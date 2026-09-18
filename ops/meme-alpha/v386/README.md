# Meme Alpha V386 — proposal policy, not live

Status: CODED, 33/33 unit tests PASS. NOT INTEGRATED, NOT DEPLOYED, NOT BACKTESTED.
Review commit: b704a27e6827080bef9182ec07b344f3d808a0d0.
Branch: codex/meme-v386-cost-aware-policy.
Run tests: node --test ops/meme-alpha/v386/portfolio-policy.test.mjs

## User objective
Broaden Solana opportunities, hold healthy trends, rotate genuinely deteriorating positions into demonstrably better opportunities after costs, compound confirmed capital. Bybit and signer/OS boundaries unchanged.

## Verified live baseline
2026-09-06 12:09:51 UTC, workflow 34032286546, job 101483902373:
- executor markers V381_FAST_CAPITAL / V382_NO_SOFT_GATE_FAST_PIPELINE; SHA256 21ec15212eb02ab5e65c6665000c5ffd395a9cbd84f0a87b26c60f0202f5d8a9
- scanner V385; SHA256 42732fd15ff8238ce6e9008e6423df9df5763ae4df18f5ee7cc1971e4c35e949
- signal export SHA256 83acd7da0b05d457292180c8fc15a366633d09f3b6d5e24f318886f1ef89cde1
- allowed=true; armOk=true; armAttested=true; executionMode=MICRO_LIVE; scaleAllowed=false
- portfolio export updated 12:09:48 UTC; openPositions=4
- sampled signal count/probe/routed=0. No new BUY/SELL established by this audit.

## Important correction
The repository runtime source snapshot identifies itself as V360. It is not the verified V382 live executor. Its MEME_CONFIRMED predicate and rotation formulas are evidence about that stored snapshot only, not proof of the current live bottleneck. Do not deploy that snapshot over V382.

## Policy behavior
- Pure, side-effect-free proposal helpers; no network calls/signing/order authority.
- All Solana labels may enter WATCH; WATCH is not security clearance. Execution still requires existing hard safety checks.
- Rotation compares same-horizon calibrated net forecast bps, uncertainty and explicit all-in cost bps at the intended notional. Never converts raw ranking scores to financial forecasts.
- Distinct weakening observations and independent evidence required; healthy runners retained.
- Initial conservative turnover/rotation bounds are anti-fee-churn controls, not caps on ordinary buy count or held coin count. Not claimed optimal.
- Capital budgeting respects cash, exit reserve, fees, marked-equity freshness, risk ceiling and scaleAllowed=false.

## Required integration and review before activation
1. Obtain current executor/scanner/export source through the authorized read-only channel and compare live hashes. Never scrape secrets or bypass directory permissions.
2. Trace universe security classification end to end before changing executable non-meme scope. The helper currently broadens WATCH only.
3. Supply externally calibrated same-horizon forecasts with validated out-of-sample results and explicit all-in costs. Without them rotation remains HOLD; do not fabricate projections from scores.
4. Diagnose scaleAllowed=false at its source. Preserve it unless a separately verified policy legitimately clears it.
5. Integrate durable intent, sell confirmation/reconciliation, target revalidation after sell, partial fills, timeout/restart recovery and pending-order exclusion. These lifecycle behaviors are requirements, not implemented by the pure helper.
6. Verify held-position feed coverage independently of entry candidates; preserve actual positions, wallet state, learning, signer and hard security.
7. Independent reviewer PASS and integration/shadow tests are required before safe-deploy activation. Do not self-finalize this production-risk change.

Rollback: no live strategy change made; leave existing V382 executor/V385 scanner untouched. Read-only audit workflow has no trading-state mutation or restart.

NEXT_AI_PROMPT: continue co-engineering: refresh main and branch codex/meme-v386-cost-aware-policy in hanlinh227-ship-it/trading-api; REVIEW b704a27e6827080bef9182ec07b344f3d808a0d0 and ops/meme-alpha/v386/README.md. Return PASS/WARN/BLOCK for the pure policy and an exact integration scope after checking live V382 hashes against audit 34032286546. Respect WRITE_LOCK, preserve scale gate, signer and hard safety; no production activation from unit tests alone.
