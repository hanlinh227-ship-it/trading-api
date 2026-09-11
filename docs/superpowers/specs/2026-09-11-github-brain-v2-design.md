# GITHUB_BRAIN_V2 Expanded Skill Router — Design

## Purpose

Upgrade the repository-level AI bootstrap from a flat GitHub-first registry into a modular skill-routing system that is safe to extend, avoids cross-domain contamination, and remains usable from new chats when GitHub access is available.

## Goals

1. Every substantive task first passes through one lightweight router.
2. The router selects one primary skill and at most two supporting skills by default.
3. Domain state is loaded only after routing. Trading state must never be loaded for unrelated creative, game, Adobe, Blender, research, or software tasks.
4. Skills, source registries, plugin mappings, and project authority are separate concepts and separate files.
5. One project/domain may have only one active authority/checkpoint at a time.
6. Legacy update/checkpoint files that are superseded and non-authoritative are removed from `main`; Git history remains the archive.
7. The architecture must leave room for new skills without changing the core bootstrap contract.
8. Repository instructions must remain concise enough that future agents can reliably follow them.

## Non-goals

- This does not fine-tune ChatGPT or guarantee GitHub availability in every ChatGPT surface.
- A plugin is not a reasoning skill. Plugins provide data/actions; skills define reasoning and workflow.
- External repositories are reference knowledge, not authority over the user's current project state.

## Canonical bootstrap

The stable activation key is `GITHUB_BRAIN_V2`.

Routing flow:

`request -> checkpoint.json -> GITHUB_BRAIN_V2.md -> router.yaml -> selected skills -> project authority -> approved sources/plugins if needed -> critical review -> execution -> verification -> answer`

If GitHub is unavailable, the assistant must disclose that the checkpoint was not freshly loaded and use last-known context rather than pretending a refresh occurred.

## Repository layout

```text
AI_SKILL_LIBRARY/
  checkpoint.json
  GITHUB_BRAIN_V2.md
  CORE_PROTOCOL.md
  router.yaml
  plugins.yaml
  sources.yaml
  LICENSE_POLICY.md
  ingest_sources.py
  validate_registry.py
  validate_brain.py
  requirements.txt
  skills/
    core/
    engineering/
    trading/
    creative/
    academic/
    productivity/
  tests/
    test_integration.py
    test_brain_v2.py
```

`AGENTS.md` becomes a short bootstrap pointer. It must not preload trading state globally.

## Skill contract

Each skill file is registered in `router.yaml` with:

- `id`: unique stable identifier.
- `path`: repository path to the skill instruction.
- `domains`: semantic domains covered by the skill.
- `triggers`: representative intent terms or task classes.
- `excludes`: intents that must not activate the skill by themselves.
- `requires`: prerequisite skills, if any.
- `conflicts_with`: skills that must not be co-selected unless an explicit composite route allows it.
- `priority`: deterministic routing precedence.
- `plugin_ids`: logical plugin capabilities that may be used when available.
- `source_categories`: knowledge categories that may be consulted after routing.

The router default budget is one primary skill plus up to two supporting skills. Core `critical_thinking` and `verification` may be applied as cross-cutting review layers and do not count against the domain-skill budget.

## Initial skill families

### Core reasoning
- task_router
- critical_thinking
- research
- evidence_synthesis
- decision_analysis
- planning
- verification
- error_recovery

### Engineering
- coding
- software_architecture
- debugging
- tdd
- code_review
- github_ops
- api_design
- database
- security
- deployment
- cloudflare
- android
- web_app
- automation
- agent_coordination

### Trading
- trading_router
- crypto
- forex
- futures
- indices
- market_microstructure
- technical_analysis
- risk_management
- execution
- backtesting
- quant_research
- mt5_mql5
- trading_bot
- live_data_validation

### Game
- game_design
- game_dev
- gameplay_systems
- godot
- unity
- web_game
- game_ai
- level_design
- game_2d
- game_3d
- optimization

### Creative / visual / media
- graphic_design
- ux_ui
- product_design
- design_system
- branding
- typography
- color
- layout
- illustration
- product_photography
- design_3d
- modeling
- topology
- uv
- texturing
- materials
- lighting
- rigging
- animation_3d
- rendering
- asset_optimization
- blender
- photoshop
- illustrator
- premiere_pro
- after_effects
- lightroom
- audition
- indesign
- acrobat
- image_generation
- image_editing
- video_generation
- video_prompt
- character_consistency
- scene_continuity
- camera_direction
- storyboard
- video_editing
- prompt_engineering
- image_prompt
- agent_prompt
- negative_constraints
- prompt_debugging
- prompt_optimization
- scriptwriting
- screenwriting
- voice_over
- advertising_copy
- hook_retention
- storytelling
- children_content
- youtube_script
- social_content

### Academic / analysis
- academic_research
- literature_review
- methodology
- qualitative_research
- quantitative_analysis
- interdisciplinary_research
- citation_review
- argumentation

### Productivity / documents
- data_analysis
- spreadsheet
- charts
- report
- docx
- pdf
- slides
- presentation
- google_docs_workflow

### Business / marketing / general problem solving
- marketing
- content_strategy
- product_marketing
- creative_campaign
- customer_research
- pitching
- business_analysis
- remote_work
- comparison
- recommendation
- troubleshooting
- how_to
- learning
- translation
- summarization

The first V2 implementation may group tightly related leaf capabilities into one skill file while exposing them as route aliases. This keeps files small enough to reason about without creating dozens of nearly empty documents.

## Plugin routing

`plugins.yaml` maps logical capabilities, not hard dependencies. Initial mappings include:

- Figma -> UX/UI, design systems, UI implementation context.
- Product Design -> product flows and prototype review.
- Runway -> image/video generation and editing workflows.
- to3D -> 2D-to-3D asset conversion.
- Scite -> scientific evidence and citation-context review.
- Massive -> live/historical multi-asset market data.
- Binance -> public crypto market data.
- Superpowers -> planning, TDD, debugging, review, and verification workflows.

Missing plugins must not break routing; the system falls back to available tools or source-only reasoning and discloses material limitations.

## Source policy

`sources.yaml` remains a knowledge registry. V2 changes the default training posture to opt-in:

- `TRAINING_OK`: explicitly approved for dataset/fine-tune preparation.
- `RAG_ONLY`: usable for retrieval/context but not automatic training export.
- `REFERENCE_ONLY`: may be read as reference but not ingested into reusable corpora.
- `MANUAL_REVIEW`: disabled until rights/provenance are approved.

Existing `rag` and `training` fields may remain temporarily for compatibility, but V2 validation requires the explicit usage tier for new entries.

## Authority model

Project state files must declare one of:

- `CURRENT_AUTHORITY`
- `REFERENCE`
- `RETIRED`

A machine-readable authority registry in `router.yaml` identifies the one current authority per project/domain. Validation fails if more than one active authority exists for the same scope.

For trading, current authority is the newest explicitly promoted state, currently `docs/checkpoints/CURRENT_HANDOFF.md`, which points to `docs/checkpoints/BYBIT_BTC_STATEFLOW_2_1_20260904.md`. Stale `MASTER_TRADING_STATE.md` content must not remain a competing authority.

## Legacy cleanup policy

A file is deleted from `main` only when all are true:

1. It is an update, audit, handoff, checkpoint, plan, or temporary diagnostic rather than executable source required at runtime.
2. It is superseded by a newer canonical authority or belongs to a retired project flow.
3. The V2 bootstrap/router does not reference it.
4. No active workflow depends on it.
5. Any still-useful invariant is migrated into a current authority/skill before deletion.

Git history is the archive. V2 avoids keeping multiple old snapshots in the working tree merely for history.

## New-chat behavior

Persistent account/project instructions should point to `GITHUB_BRAIN_V2`. A new substantive request should always pass through the lightweight router when GitHub is available. The router may return `general`/`NO_SPECIAL_SKILL` for ordinary questions, but the routing decision still occurs before domain state is loaded.

The repository cannot force ChatGPT surfaces that do not expose GitHub to perform a GitHub read. The protocol therefore distinguishes `fresh_git_context=true` from fallback context and forbids pretending otherwise.

## Validation and CI

CI must verify:

- checkpoint ID/path/version and V1 compatibility alias;
- all routed skill paths exist;
- unique skill IDs;
- valid requires/conflicts references;
- no direct conflict in default composite routes;
- domain skill budget is not exceeded by route definitions;
- plugin capability references exist;
- one active authority per project scope;
- source registry/license/usage-tier validity;
- ingestion dry run still works;
- Python files compile;
- optional upstream repository audit remains non-executing.

## Compatibility and migration

`GITHUB_BRAIN_V1` remains an accepted activation alias during migration, but `checkpoint.json` points only to V2. V1's checkpoint document is removed from the working tree once the V2 checkpoint and alias behavior are validated.

Trading-specific co-engineering docs remain available only when the trading/project route explicitly requests them; they are no longer mandatory global bootstrap files.

## Extension points

Future upgrades add a skill registry entry plus one focused skill file, optional plugin capability, and optional source category. They must not require changing the checkpoint bootstrap contract. Router schema versioning is explicit so V3 can be introduced without ambiguous mixed rules.
