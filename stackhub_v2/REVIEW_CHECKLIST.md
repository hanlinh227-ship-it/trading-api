# STACKHUB V2 Plan 1 Review Checklist

Plan: `docs/superpowers/plans/2026-09-11-stackhub-v2-foundation-taskbounty-readonly.md`

- [x] Python 3.12 package is isolated under `stackhub_v2/`.
- [x] Runtime is dry-run and zero-spend only.
- [x] TaskBounty discovery uses read-only GET requests only.
- [x] Current public JSON Feed `/api/v1/bounties.json` is live-probed in CI.
- [x] Empty feed is treated as healthy, not as an outage.
- [x] Opportunity persistence is idempotent on `(source, id)`.
- [x] Policy gate denies unknown/forbidden agent use and prohibited human simulation.
- [x] Claims, submissions and payouts remain empty in Plan 1 smoke tests.
- [x] Secret/wallet-material scan runs in CI.
- [x] GitHub Brain V4 validators run in CI.
- [x] Live read-only smoke runs twice and verifies source health + no duplicates.
- [ ] Autonomous claim/solve/submit is intentionally deferred to Plan 2.
- [ ] VPS/systemd long-running deployment is intentionally deferred until Plan 1 review/merge.
