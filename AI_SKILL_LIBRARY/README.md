# AI Skill Library — GITHUB_BRAIN_V4

`GITHUB_BRAIN_V4` is the single repository-level AI brain for ChatGPT, Claude, Codex and other repo-aware agents. It does not fine-tune a model. It provides one deterministic bootstrap, one router, one authority chain, canonical skills with bounded supporting skills, a tiered retrieval index, and a license-aware knowledge-source registry.

`GITHUB_BRAIN_V3`, `GITHUB_BRAIN_V2` and `GITHUB_BRAIN_V1` are compatibility aliases only. Their files resolve to V4 through `checkpoint.json` and carry `superseded_by: GITHUB_BRAIN_V4`.

## Bootstrap (HOT tier only)

1. `AGENTS.md`
2. `AI_SKILL_LIBRARY/checkpoint.json` — discovery root; never hard-code versions or paths elsewhere.
3. `AI_SKILL_LIBRARY/AI_GLOBAL_CHECKPOINT.md` — current runtime/deployment state.
4. `AI_SKILL_LIBRARY/v4/releases/current.json` — verify the immutable release manifest.
5. `AI_SKILL_LIBRARY/v4/stable/router.yaml` — the only router. Exactly one profile (`FAST`/`STANDARD`/`DEEP`), exactly one primary skill, its validated execution capsule.
6. `AI_SKILL_LIBRARY/v4/index/retrieval_index.yaml` — exact lookup first (skill id, alias, path, project scope); semantic search only after an exact miss and never in `FAST`.
7. Lazy-load project authority, ≤2 supporting skills, relevant sources and tools only when the routed profile permits (`AI_SKILL_LIBRARY/v4/stable/budgets.yaml`).

`AI_SKILL_LIBRARY/v4/index/workspace_map.yaml` answers "where is what" without scanning the repository.

## Retrieval order

`REQUEST → task_router → domain → project authority (if required) → primary skill → ≤2 supporting skills → relevant index (exact first) → relevant sources → tools → answer`

Tiers: **HOT** (router, authority, current skills, current release), **WARM** (supporting policy, skill reasoning text, sources), **COLD** (legacy checkpoints, historical releases, retired systems). `FAST` never touches WARM/COLD.

## Skills

`skills/catalog.yaml` is the canonical skill list. Rows with `alias_of` are aliases: never primary, never routed; their triggers fold into the canonical skill at compile time. Each purpose has exactly one primary skill; a trigger term is owned by exactly one primary skill (the compiler rejects ambiguity).

Domain packs live in `v4/skills/<domain>/manifest.yaml`; reasoning text for the larger skills lives in `skills/<family>/*.md` (WARM).

## Authority

Precedence (`v4/stable/evidence.yaml`, referenced everywhere else): current runtime → current project authority → first-party current → peer-reviewed/primary → approved reference → scoped verified memory → model background.

Providers, plugins, upstream repositories and memory are evidence or tools, never reasoning authority. No majority vote, no silent averaging. Trading authority is external to the Brain (`projects.yaml` → `docs/checkpoints/CURRENT_HANDOFF.md`) and loads only after a Trading route; research and multi-market analysis never widen execution authority.

## Releases

Never edit SHA256 values by hand:

```bash
python AI_SKILL_LIBRARY/v4/tools/release.py build --version X.Y.Z --source <reason> --validated --known-good
python AI_SKILL_LIBRARY/v4/tools/build_retrieval_index.py --write
```

## Validation (single entrypoint)

```bash
python AI_SKILL_LIBRARY/v4/tools/ci_validate.py --source-sha "$(git rev-parse HEAD)"
```

This runs every validator, the release/index freshness checks, the consolidation checks (single router, alias rows, budget consistency, trading bridge guards) and the unit tests exactly once. CI workflows call the same entrypoint.

## Adding a skill, source or upstream pattern

Strengthen an existing canonical skill first. A new primary skill is admitted only when it is materially distinct, passes `v4/stable/harmonization.yaml` (provenance, license, overlap, conflict, risk, permission, performance, eval, authority impact) and starts in Evergreen quarantine with zero routing authority. Never create a parallel Brain, a second router, a second memory system, a separate creative brain or a duplicate Trading authority.
