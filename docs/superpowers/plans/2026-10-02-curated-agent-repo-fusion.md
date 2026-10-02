# Curated AI coding repository fusion — implementation plan

Approved by Han Linh on 2026-10-02. Work is isolated on `codex/curated-ai-repos-20261002` in each repository.

## Core package

- [x] Create isolated branch.
- [x] Upgrade existing UX/UI guidance with original wording.
- [x] Record ten source URLs, immutable commits, license status, and no-copy boundaries.
- [x] Keep package instruction-only; add no hooks, telemetry, executable dependencies, or permissions.

## Trading Brain

- [x] Add ten sources to the existing advisory upstream registry with exact commit SHAs.
- [x] Add engineering/design targets mapped to existing canonical manifests.
- [x] Extend the validator for source SHA, canonical URL, ref, and audit date.
- [x] Add focused regression tests for provenance and non-authority invariants.
- [x] Write this spec and plan.

## Verification / release

- [ ] Validate JSON/YAML and run the focused validator and unit test.
- [ ] Confirm router, executor, trade authority, strategies, and permission files are unchanged.
- [ ] Review both PR diffs and available repository checks.
- [ ] Merge/release only from verified immutable commits; retain rollback.

## Local computer

- [ ] Retry read-only bridge access after repo validation.
- [ ] Install only through authorized executor from a verified immutable release, if local source admission and release gates pass.
- [ ] If bridge access remains unavailable, leave machine state unchanged and report the exact MCP blocker.
