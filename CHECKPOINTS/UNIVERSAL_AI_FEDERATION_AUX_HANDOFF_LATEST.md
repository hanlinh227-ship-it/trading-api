# Universal AI Federation — Auxiliary Handoff

Status: AUXILIARY / NON-AUTHORITY
Owner of implementation: Claude Code
Canonical Brain: `GITHUB_BRAIN_V4`

## Purpose

This handoff exists only to reduce duplicate work and give Claude Code verified operational inputs. It does not create a second implementation lane, second router, second Brain, second runtime scheduler, or second model registry.

## Canonical invariants

- `GITHUB_BRAIN_V4` is the sole Brain/project authority.
- `task_router` is the sole task-routing authority.
- Task Graph Builder decomposes work.
- AI Legion owns specialist-role orchestration.
- Adaptive Model Mesh selects model/provider/runtime for an already-defined role.
- Open Model Universe owns discovery/governance/admission, not routing.
- Local runtime owns residency/load/unload/execution.
- Memory Continuity is context-only.
- External models/frameworks/repos have `authority=false`.

## Required architecture shape

`User/Event -> Brain -> task_router -> Task Graph -> AI Legion role -> Model Mesh capability selection -> model/runtime/tool execution -> checker/grader/verifier -> evidence synthesis -> Brain output`

Do not flatten models directly into Brain and do not bind one model permanently to one domain unless benchmark evidence requires it.

## Peer Tri-Layer learning

Reuse the approved Peer Tri-Layer AI Legion design:

- Layer A: Experience
- Layer B: Curated Knowledge
- Layer C: Open Exploration

A/B/C are peers. Claims are resolved with provenance, freshness, contract authority, reproducibility, benchmark/regression evidence, contradiction analysis, and checker/grader verification. Majority vote does not determine truth.

## Hundreds-of-AI interpretation

The system may expose hundreds of specialist roles/models as AVAILABLE/COLD candidates, but only a bounded subset should run concurrently.

Initial concurrency ceiling remains:

- STANDARD <= 2 workers
- DEEP <= 4 workers

Increase only with benchmark evidence.

## Model lifecycle

Use a single governed lifecycle:

`DISCOVERED -> QUARANTINED -> ADMITTED -> COLD -> WARM -> ACTIVE -> SLEEPING/EVICTED`

Artifact present on disk does not mean admitted. Registry membership does not mean active.

## Model integration rule

Every model must independently establish:

- official/verifiable upstream
- immutable revision or equivalent immutable artifact identity
- license evidence
- exact model-file size
- exact model-file SHA256
- safe-format/structural evidence
- isolated first load
- real inference
- runtime/hardware evidence
- benchmark/capability evidence
- role eligibility

No approval may be copied from one model to another.

## Current staged artifacts

Machine-readable operational index:

`AI_SKILL_LIBRARY/v4/open_model_universe/wave1_staging.json`

Known staging:

1. Canonical Qwen3-0.6B Q8_0
   - workflow run `35200311835`
   - artifact `10487472041`

2. Wave 1 workflow run `35201035730` completed successfully and produced:
   - Qwen3-1.7B Q8_0 artifact `10487951643`
   - Qwen3-4B Q4_K_M artifact `10487314513`
   - Granite 3.3 2B Instruct Q4_K_M artifact `10488431786`

Treat GitHub Actions archive digests as transport evidence only. Claude must recompute the actual model-file identity after extraction before intake/admission.

## Critical path

Do not let broad model expansion delay the baseline path:

`B1 -> B2 -> B3 -> B4 -> Wave 0 -> PERSONAL_AI_BASELINE_001 -> Wave 1 admission -> Multi-Model Federation V1 -> LOCAL_ONLY_SELF_DEVELOPMENT -> Controlled Self-Development V1 -> evergreen model discovery`

## Auxiliary work already done

- Created reusable GitHub Actions artifact transport for the canonical Qwen3-0.6B artifact.
- Created Wave 1 staging workflow and successfully staged three additional model artifacts.
- Recorded machine-readable staging metadata.
- Opened draft PR #440 as an auxiliary handoff only.

## Claude instructions

1. Refresh `main`, `AI_SKILL_LIBRARY/checkpoint.json`, and canonical router first.
2. Compare this branch/PR against Claude's current implementation branch before cherry-picking or merging.
3. Consume only non-conflicting pieces.
4. Preserve fail-closed governance.
5. Close B1 with real runtime evidence before claiming baseline progress.
6. Generalize artifact intake by manifest rather than adding per-model special cases.
7. Connect admitted models under Model Mesh and AI Legion; never directly under Brain authority.
8. Keep local-only mode genuinely free of paid/cloud fallback when enabled.
9. Emit tests, exact-head CI, machine-readable evidence, and updated canonical handoff for every promotion.

## Merge policy for PR #440

Do not auto-merge. Claude should reconcile it with the current canonical main and its active branch. If the same workflow/manifest/handoff functionality already exists in Claude's branch, prefer the newer canonical implementation and close/supersede this PR rather than duplicate it.
