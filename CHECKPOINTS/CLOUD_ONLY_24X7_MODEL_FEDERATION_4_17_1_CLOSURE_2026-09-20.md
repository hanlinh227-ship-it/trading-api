# Cloud-Only 24x7 Model Federation 4.17.1 — Closure

Date: 2026-09-20
Architecture: GITHUB_BRAIN_V4
Status: PACKAGED / CI-GATED / AWAITING PRODUCTION VERIFICATION
Target release: `4.17.1`
Previous release: `4.17.0`
Previous known-good release: `4.14.0`

## Scope

Release 4.17.1 formalizes the zero-local Model Mesh service-continuity contract.
Normal Brain execution does not require a personal computer, does not fall back
to a local runtime, and does not spill into a paid provider.

The contract defines 24/7 as federation service continuity, not as a claim that
every free provider or every model remains permanently hot. Provider/model
availability and free quota remain dynamic runtime facts.

## Cloud continuity contract

- Model Mesh remains `FREE_ONLY`.
- Personal-PC and local-runtime requirements are false.
- Local fallback and paid fallback are forbidden.
- At least 3 independent cloud provider paths and 5 active eligible models are
  required by the canonical validator.
- Provider selection is health-aware, quota-aware and model-family-aware.
- 429 and provider 5xx responses rotate to another verified zero-cost path.
- Free-quota headroom is respected before exhaustion and provider reset
  semantics are preserved.
- Opening another account to bypass quota is forbidden.
- Stable Runtime survives a Model Mesh/provider outage in degraded mode.

## 24/7 health maintenance

Cloudflare Worker is the health-refresh authority. The Worker cron runs every
20 minutes, inside the 30-minute live-evidence TTL. The same canonical provider
probe is used by scheduled refresh and bounded opportunistic self-heal.

Health work is read-only and non-blocking for user requests. The scheduled
handler has no financial, trading, deployment, routing-authority or
model-admission authority.

## Validation

New canonical validation:
`AI_SKILL_LIBRARY/v4/tools/validate_cloud_24x7.py`

Regression coverage:
`AI_SKILL_LIBRARY/tests/test_cloud_only_24x7_federation.py`

The validator is wired into the single `ci_validate.py` entrypoint and blocks
future changes that reintroduce personal-PC dependency, local fallback, paid
spillover, insufficient cloud redundancy, stale health cadence, or weakened
quota-aware failover.

## Release integrity

The immutable release manifest was regenerated for 4.17.1 and the retrieval
index was rebuilt for the new release pointer. The release remains
`known_good: false` until the required main-branch deployment and exact-SHA
production verification complete.

## Authority boundaries

`task_router` remains the sole routing authority. Model providers are
execution/evidence resources only. No Trading authority, order execution,
wallet, transfer, credential, destructive-write or permission-expansion
authority is added by this release.

Previous closure record:
`CHECKPOINTS/OPEN_MODEL_CAPABILITY_LEDGER_4_17_0_CLOSURE_2026-09-17.md`.
