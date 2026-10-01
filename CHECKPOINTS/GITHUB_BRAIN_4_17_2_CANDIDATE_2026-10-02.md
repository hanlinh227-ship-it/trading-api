# GitHub Brain V4 4.17.2 Production Checkpoint

Date: 2026-10-02
Architecture: GITHUB_BRAIN_V4
Status: PRODUCTION VERIFIED
Release: `4.17.2`
Production source SHA verified: `4b92c37d02ae4c7ab493a0e8572e5dae809bc97e`
Previous production baseline: `4.17.1` at `cc1ac7dcfbdeb812c21a3124296155e59c0c556c`

## Scope

This record closes the 4.17.2 release candidate for the canonical Brain
repository, `hanlinh227-ship-it/trading-api`.

The release refreshes the canonical skill retrieval index after release
pointer changes and improves cross-platform local validation on Windows and
Linux. It does not change the production Exness quote route, trade permissions,
the Bybit strategy or worker source, provider billing policy, or routing
authority.

## Changes

- Rebuilt the retrieval index from the canonical registry and release pointer.
- Corrected rollback coverage so the active release cannot be selected as its
  own previous known-good rollback target.
- Added Windows process RSS measurement via the Win32 process memory API.
- Made interpreter identity and cache-root tests platform-independent.
- Promoted release 4.17.2 through the canonical release and evergreen tooling.

## Verification

- Local targeted tests for RSS sampling, interpreter identity, and cache-root
  containment passed on Windows.
- Local `ci_validate.py` completed with exit 0: 3,501 AI library tests and
  90 root tests passed; 24 tests were skipped.
- PR #539 passed exact-head CI for source SHA
  `d95d9154d5a5b579223f878cf250c58d5a05c24c`: AI Skill Library CI, Cloudflare
  Research Runtime CI, Zero Local Cloud Runtime, Fast Gateway CI, and Crypto
  Skill Registry validation succeeded. Candidate Release automation was
  skipped because it requires a bot-generated Evergreen branch.
- The canonical main deployment gate passed on exact source SHA
  `4b92c37d02ae4c7ab493a0e8572e5dae809bc97e` in
  [run #257](https://github.com/hanlinh227-ship-it/trading-api/actions/runs/36907137493).
  It verified the deployed revision, Skill Gateway and Model Mesh health,
  Exness read-only quote E2E, existing Bybit market-stream and execution
  universe canaries, Brain route matrix, zero-cost guard, and external
  credential boundary.
- Production `/brain/health` returned release `4.17.2` and source SHA
  `4b92c37d02ae4c7ab493a0e8572e5dae809bc97e`.
- [Zero Local Cloud Runtime run #1461](https://github.com/hanlinh227-ship-it/trading-api/actions/runs/36907137452)
  passed production health, read-only capability checks, and live research
  smoke with exact source SHA and research-only authority.
- An auxiliary deployment-observer attempt initially saw the previous
  `source_sha` during rollout propagation. The later authoritative main gate
  and zero-local production smoke both passed on the exact new SHA; the
  observer was re-run separately to confirm stable propagation.

## Authority and safety

`task_router` remains the sole routing authority. No model provider, skill,
or adapter gains routing, financial, execution, credential, or deployment
authority through this release.

Exness remains read-only. The Bybit worker source is unchanged and its
existing production canaries passed. No trading actions were introduced.
