# Retired workflow history (COLD tier)

Retired one-shot workflow definitions are intentionally **not kept in the current
working tree**. They are preserved by Git history, which is the correct archival
surface for execution definitions that no longer have authority.

Why:
- archived YAML still bloated every clone/checkout;
- 300+ retired files added search noise and false conflict candidates;
- none belongs to canonical CI or production deployment;
- GITHUB_BRAIN_V4 must not preload or route through retired execution lanes.

Current-tree policy:
- keep this README only as the tombstone/pointer;
- keep retired workflows out of `.github/workflows/`;
- recover an old definition from Git history only after an explicit migration
  re-authorizes that runtime.

Example recovery:

```bash
git log --all -- .github/workflows-archive/<name>.yml
git show <historical-commit>:.github/workflows-archive/<name>.yml
```

The original retirement was performed by the 2026-09-12 GITHUB_BRAIN_V4
consolidation. See
`AI_SKILL_LIBRARY/v4/audit/BRAIN_CONSOLIDATION_2026-09-12.md`.
