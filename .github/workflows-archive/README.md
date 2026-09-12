# Archived workflows (COLD tier)

These workflows belong to execution authorities that `docs/checkpoints/CURRENT_HANDOFF.md` retired
(Meme runtime, Signal V10/V11 hub). Every file here was a one-shot trigger (push gated on its own
path or `workflow_dispatch`) and none is part of canonical CI or production deployment.

GitHub Actions does not evaluate files in this directory, so a push to `main` no longer parses
~320 inert workflow definitions. Git history is preserved; nothing was deleted.

Restore (only after an explicit migration re-authorizes that runtime):

```bash
git mv .github/workflows-archive/<name>.yml .github/workflows/<name>.yml
```

Archived on 2026-09-12 by the GITHUB_BRAIN_V4 consolidation (see
`AI_SKILL_LIBRARY/v4/audit/BRAIN_CONSOLIDATION_2026-09-12.md`).
