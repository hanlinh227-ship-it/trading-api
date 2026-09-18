# STACKHUB V2 Live Hardening Plan

Goal: remove avoidable technical blockers and retry loops while preserving marketplace, financial, credential, and safety gates.

## Tasks
1. Add failing regression tests for TaskForce duplicate/permanent/retryable failures and orchestrator failure classification.
2. Make TaskForce application idempotent for already-applied responses and normalize known platform rejection reasons.
3. Classify permanent 4xx as terminal and keep transient 408/429/5xx/network failures retryable.
4. Increase discovery from 10 to 100 items per source and raise bounded live concurrency to 4.
5. Add deployment preflight: install test dependencies, run full pytest suite, verify local solver dependency, start/pull Ollama model when local solver is selected, and run a solver smoke test before any live mutation.
6. Add dedicated STACKHUB CI for every STACKHUB change.
7. Deploy, inspect live logs, confirm service health, scan inventory, application behavior, and payout state. Fix any remaining reproducible error before declaring completion.

Safety invariants: external spend remains 0; no wallet private keys/seed phrases; no CAPTCHA/human impersonation; no bypass of creator acceptance; no external withdrawal automation requiring gas; no unsupported real-world actions.
