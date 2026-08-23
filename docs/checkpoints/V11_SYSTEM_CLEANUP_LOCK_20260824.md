# V11 SYSTEM CLEANUP LOCK — 2026-08-24

Status: CLEANED / LOCKED
Repository: hanlinh227-ship-it/trading-api

## Purpose
Keep the active system small, non-conflicting and prompt-first. Do not recreate obsolete Issue/PR/job orchestration or old-version active workflows.

## Canonical active workflow surface
Only these GitHub Actions remain active by design:
1. `.github/workflows/v11-fiveai-direct-backtest.yml` — sole V11 research/backtest path; five-AI research + deterministic evidence.
2. `.github/workflows/v11-signal-validation.yml` — canonical V11 production validation.
3. `.github/workflows/deploy-cloudflare-worker.yml` — canonical V11 Cloudflare deployment.
4. `.github/workflows/multi-ai-gateway-smoke.yml` — current five-provider gateway diagnostic; read-only and useful after deployment.
5. `.github/workflows/audit-market-data.yml` — explicit market-data audit/evidence path.
6. `.github/workflows/vps-runner-smoke.yml` — manual read-only V11 bridge diagnostic only; checks `v11-manual-ai-bridge.service`, not retired AI-loop/watcher services.

## Removed active conflicts
Removed/retired from Actions: legacy AI task redirect/wake/fanout, AUTO_TASK trigger, AI Closed Loop Issue->PR writer, PR event reconcile, DeepSeek legacy PR review, old V10/V77/V73/V75/V78 validation/scan/patch/debug/dispatch workflows, duplicate V11 legacy/public/report-only/symbol backtests, strict-over-80 patch, one-shot hub patch and disabled continuous watch.

The old Claude watcher heartbeat issue is closed/retired. Open research AI-TASK/PR orchestration is not part of the active system.

## Research authority
`V11 Direct 5AI` is the only active research/backtest authority.
Historical old-version source/data may remain read-only as learning evidence, but old workflows must not execute, write main, dispatch jobs, or compete for authority.

## Threshold authority
The V11 research contract is inclusive per-symbol WR `>= 80.00%`, not strictly greater than 80. RR allowed is exactly 1:1 or 1:2. Preserve the locked 1-3 real executions per eligible symbol/day and integrity/no-leakage/final-holdout rules.

## Owner interaction
Owner is prompt-only/final-result-only. Ordinary work starts immediately. Do not create Issue/PR orchestration for research. Do not ask owner to troubleshoot. Infrastructure repair is allowed only for a proven hard blocker and must be minimal.

## Ongoing hygiene rule
For every future task, inspect only the relevant active surface. If a component is obsolete and can execute, write, dispatch, duplicate authority, contradict current thresholds, or create misleading operational state, retire/remove it as part of the task. Do not delete historical evidence merely because it is old.
