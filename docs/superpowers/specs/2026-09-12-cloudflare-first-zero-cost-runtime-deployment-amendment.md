# Cloudflare-First Runtime — Deployment Authority Amendment

Date: 2026-09-12
Status: Approved implementation correction based on production evidence
Supersedes: deployment-authority statements in `2026-09-12-cloudflare-first-zero-cost-runtime-design.md`

## Evidence that changed the design

During Gate A, the Cloudflare Workers GitHub App check `Workers Builds: trading-v77-scanner` failed instantly on the new branch. Historical verification then showed the same external Cloudflare Builds check also failed on the pre-migration production `main` revision and on older known-good Worker revisions. Therefore that GitHub App check is not a valid indicator of the currently deployed Worker and cannot remain production deployment authority.

Repository history also proves that direct Wrangler deployment through GitHub Actions previously deployed `trading-v77-scanner` successfully using existing repository secrets and the same existing KV/VPC bindings. The current `prepare-wrangler.mjs` has since been hardened further: it writes only `RUNTIME_REVISION`, uses `keep_vars: true`, and deliberately does not generate or mutate `BYBIT_AUTO_LIVE`, `BYBIT_BTC_LIVE_ACK`, `BYBIT_AUTO_DEMO`, or other operator switches.

## Revised deployment authority

Production Worker deployment authority is:

`GitHub main -> GitHub-hosted Actions runner -> validated Wrangler bundle -> exact-main RUNTIME_REVISION -> wrangler deploy -> live exact-revision smoke`

The failing Cloudflare Builds GitHub App is treated as a non-authoritative stale/broken integration. It may continue to emit a failing external check until its dashboard integration is removed or repaired, but it does not gate production when all canonical GitHub Actions and live-runtime gates pass.

## Zero-local and cost boundary

The deploy workflow uses a GitHub-hosted runner (`ubuntu-latest`), not the user's computer and not the trading VPS. Existing Cloudflare repository secrets provide deployment credentials and binding IDs. No new paid runtime is introduced.

## Safety requirements

The deploy workflow MUST:
- deploy only from canonical `main` or explicit workflow dispatch using `main`;
- validate gateway tests, typecheck, build, Worker preflight, and Wrangler bundle before deploy;
- preserve existing Cloudflare runtime operator variables via `keep_vars: true`;
- prove `RUNTIME_REVISION == GITHUB_SHA` after deploy;
- prove `/health` identifies `cloudflare-workers`, exact source revision, and `localInstallRequired=false`;
- prove `/capabilities` remains read-only;
- prove fresh venue-bound Bybit execution quotes and explicitly classify Binance unavailability/region restriction;
- preserve `/runtime/contract` and existing Bybit/private transport behavior;
- never set LIVE/PAPER/ACK/DEMO switches from CI.

## Gate A change

Gate A no longer requires the pre-existing broken `Workers Builds: trading-v77-scanner` external check to become green. It requires instead:
1. canonical PR CI green;
2. merge to `main`;
3. GitHub Actions production Wrangler deployment green;
4. exact `main` SHA visible through the live Worker;
5. live research and existing trading contract smoke green.

Only then may Gate B transfer GitHub Brain runtime authority from Railway to Cloudflare.
