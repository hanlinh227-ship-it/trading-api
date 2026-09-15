# Model Mesh Live Health and TinyFish Stabilization Implementation Plan

> Execute in order with test-driven development. Each implementation task starts with a failing focused test, then the minimum production change, focused verification, and a logical commit.

## Task 1: Canonical FREE_ONLY contract and diagnostic taxonomy

Files: `AI_SKILL_LIBRARY/v4/model_mesh/free_only_policy.json`, registry/compiler validators, `cloudflare-worker/model-mesh/contracts.js`, focused Python and Node tests.

Add failing tests proving recurring/account-specific verified free states are eligible and trial/time-limited states are not. Add the versioned policy artifact and enforce it in compiler/runtime validation. Add the closed sanitized error enum and status-to-category mapping. Verify malformed or secret-bearing errors reduce to `UNKNOWN_SANITIZED` without payload echo.

## Task 2: Live-health state machine and isolated KV store

Files: new `cloudflare-worker/model-mesh/health-store.js`, new focused test file, `cloudflare-worker/package.json`.

Test missing, fresh, stale, cooldown, quarantine, fingerprint mismatch, exact source-revision mismatch, recovery, KV unavailable, and bounded propagation re-read. Implement keys under `brain:model-mesh:health:v1:` only, records without sensitive fields, one record per model, explicit expiry, and no list/delete operations.

## Task 3: Provider probes and execution feedback

Files: provider adapters/client, probe and execute tests.

Test bounded response parsing, timeout, HTTP classification, safe result schema, per-provider state, and tracked persistence. Make probe results precise and sanitized, persist them through the health store, and allow successful execution to refresh evidence. Preserve zero routing/reasoning authority.

## Task 4: Runtime-aware health and planner

Files: model mesh handler/runtime/selector/active module and their tests.

Test exact six-state reporting and accurate counts. Make the planner read the live overlay. Assert FAST and SECRET zero, STANDARD 1–2, DEEP 1–4, family dedupe, stale exclusion, and graceful all-down with `no_live_healthy_provider`. Ensure immutable snapshot objects remain byte-for-byte unchanged.

## Task 5: TinyFish evidence service

Files: new evidence policy/client/handler modules, `cloudflare-worker/index.js`, generated binding checks, tests.

Test Search and Fetch request shapes, exact `TINY_FISH_API` binding, FAST/SECRET rejection, Agent/Browser rejection, host/URL/input limits, timeout, bounded retry, rate/circuit behavior, bounded parsing, sanitization, health, authenticated canary, and no Model Mesh membership. Mount only `/brain/evidence/*` before trading routes.

## Task 6: Deployment hardening and false-green CI removal

Files: Wrangler preparation, deploy workflow, validation tests.

Add tests for preserved financial switches, isolated KV binding, forbidden generated secrets, and redaction. Sync `TINY_FISH_API` without exposing values. After deploy, probe providers and TinyFish, print only the safe matrix, require every runtime ACTIVE provider to have a fresh pass, require planner lower and upper bounds when live providers exist, and accept all-down only with the explicit reason. Keep bounded propagation retries.

## Task 7: Production diagnosis and provider-by-provider remediation

Merge and deploy the diagnostic-capable exact-main revision. Capture the safe provider/model/status/category matrix. For each failure, correct endpoint/model/request configuration only when evidence supports it; otherwise mark the candidate `NOT_ELIGIBLE` or `QUARANTINED`. Never broaden FREE_ONLY or force 9/9. Re-run focused tests after each provider commit.

## Task 8: Release, pull request, and exact-SHA production proof

Run the complete Node suite and Linux Python release validation, inspect the diff, and perform security review. Update checkpoint/release artifacts through repository tooling. Push the branch, open a PR, require full CI and review, merge without force, wait for exact-main deployment, and verify runtime revision, Brain health, route matrix, provider matrix, planner cardinality, TinyFish health/canary, and unchanged trading contract. Mark known-good only when all gates pass; otherwise report the precise safe blocker.

