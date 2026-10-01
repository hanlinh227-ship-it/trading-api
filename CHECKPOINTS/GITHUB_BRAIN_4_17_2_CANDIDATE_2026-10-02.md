# GitHub Brain V4 4.17.2 Candidate Checkpoint

Date: 2026-10-02
Architecture: GITHUB_BRAIN_V4
Status: CI-VALIDATED CANDIDATE / NOT DEPLOYED
Target release: `4.17.2`
Current production baseline: `4.17.1`
Source baseline SHA: `cc1ac7dcfbdeb812c21a3124296155e59c0c556c`

## Scope

This record tracks a release candidate for the canonical Brain repository,
`hanlinh227-ship-it/trading-api`. It does not assert that release 4.17.2 is
live. Production remains at the last verified release until the exact-main
deployment and post-deployment checks pass.

The candidate refreshes the canonical skill retrieval index after release
pointer changes and improves cross-platform local validation on Windows and
Linux. It does not change the production Exness quote route, trade permissions,
the Bybit worker, provider billing policy, or routing authority.

## Changes in this candidate

- Rebuilt the retrieval index from the canonical registry and release pointer.
- Corrected rollback coverage so the active release cannot be selected as its
  own previous known-good rollback target.
- Added Windows process RSS measurement via the Win32 process memory API.
- Made interpreter identity and cache path tests platform-independent.


## Validation and promotion state

- Local targeted tests for RSS sampling, interpreter identity, and cache-root
  containment pass on Windows.
- Local `ci_validate.py` completed with exit 0: 3,501 AI library tests and
  90 root tests passed; 24 tests were skipped.
- This run compiled snapshots using the baseline SHA below while validating
  the candidate working tree. Exact candidate-SHA GitHub CI is still pending.
- The successful exact-main workflow run
  `36813506218` verified source SHA `cc1ac7dcfbdeb812c21a3124296155e59c0c556c`
  and release `4.17.1`. It is baseline evidence only, not evidence that
  candidate release `4.17.2` has been deployed.
- PR CI passed on source SHA
  `1410236d1272dcf50d18e09de45a91136fc6d65b`: Skill Library CI, Cloudflare
  Research Runtime CI, Zero Local Cloud Runtime, Fast Gateway CI, and Crypto
  Skill Registry validation succeeded. Candidate Release automation was
  skipped because it requires a bot-generated Evergreen branch.
- After those green gates, canonical `evergreen.py mark-known-good` set
  `promotion.validated: true` and `history.known_good: true`. Local release
  verification and release consistency tests pass after this mutation.
- The metadata update creates a new commit, which still needs exact-SHA CI and
  production deployment verification. Production remains at `4.17.1` until
  those gates complete.

## Authority and safety

`task_router` remains the sole routing authority. No model provider, skill,
or adapter gains routing, financial, execution, credential, or deployment
authority through this candidate.

Exness remains read-only. The Bybit worker source is unchanged; its existing
production canaries remain part of the deployment gate. No trading actions
were introduced.
