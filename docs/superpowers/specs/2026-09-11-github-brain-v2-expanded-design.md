# GITHUB_BRAIN_V2 Expanded — Design Specification

Date: 2026-09-11
Status: Proposed / approved in chat, pending written-spec review
Branch: `github-brain-v2-expanded`

## 1. Goal

Upgrade the current GitHub-first knowledge layer from `GITHUB_BRAIN_V1` to a modular `GITHUB_BRAIN_V2` that:

- routes every substantive new request through a lightweight intent router;
- activates only the relevant skills for that request;
- supports many more domains without cross-domain contamination;
- keeps project/runtime state authoritative over generic knowledge;
- separates behavioral skills, knowledge sources, tools/plugins, and project state;
- removes or archives stale update/checkpoint files that can conflict with current authority;
- leaves explicit extension points for future skills, sources, tools, and projects;
- preserves safe fallbacks when GitHub or plugins are unavailable.

## 2. Non-goals

- Do not fine-tune a model as part of this migration.
- Do not execute third-party repositories merely to ingest knowledge.
- Do not dump private chat history or secrets into this public repository.
- Do not force every request to load every skill or every source.
- Do not weaken trading safety/risk/runtime controls.
- Do not delete historical files until reference/authority analysis shows they are superseded and unreferenced.

## 3. Core architecture

Default reasoning path:

`request -> bootstrap -> intent router -> project-state authority -> primary skill -> supporting skills -> relevant sources -> relevant tools/plugins -> critical review -> execute -> verify -> answer`

Rules:

1. Every substantive request passes through the router.
2. Router may return `NO_SPECIAL_SKILL` for trivial/general requests.
3. Default maximum active domain skills per request: 3.
4. One skill is primary; at most two are supporting unless an explicit workflow requires more.
5. Skills must declare `triggers`, `excludes`, `requires`, `conflicts_with`, `priority`, `tools`, `sources`, and `output_contract`.
6. Project state always outranks external reference material for implementation/state questions.
7. Live-data domains must pass freshness/source validation before conclusions.
8. When GitHub cannot be refreshed, the assistant must disclose that and use last-known context rather than pretending a fresh read.

## 4. Repository layout

Target layout:

```text
AI_SKILL_LIBRARY/
  checkpoint.json
  GITHUB_BRAIN_V2.md
  router.yaml
  CORE_PROTOCOL.md
  LICENSE_POLICY.md
  sources.yaml
  plugins.yaml
  projects.yaml
  skills/
    core/
    coding/
    trading/
    game/
    design_2d/
    design_3d/
    blender/
    adobe/
    prompt/
    script/
    research/
    data_docs/
    business_marketing/
    general/
  schemas/
    skill.schema.json
    router.schema.json
    project.schema.json
  tests/
  validate_registry.py
  validate_router.py
  validate_authority.py
```

`AGENTS.md` becomes a compact bootstrap, not the place where all domain-specific operational rules live.

## 5. Skill domains

### Core reasoning
- task_router
- critical_thinking
- fact_checking
- research
- evidence_synthesis
- decision_analysis
- planning
- verification
- error_recovery

### Coding / engineering
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

### 2D / visual design
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

### 3D
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

### Blender
- blender_modeling
- blender_materials
- blender_geometry_nodes
- blender_animation
- blender_rigging
- blender_render
- blender_compositing

### Adobe
- photoshop
- illustrator
- premiere_pro
- after_effects
- lightroom
- audition
- indesign
- acrobat

### Prompting / generative media
- prompt_engineering
- image_prompt
- video_prompt
- agent_prompt
- negative_constraints
- prompt_debugging
- prompt_optimization
- image_generation
- image_editing
- video_generation
- character_consistency
- scene_continuity
- camera_direction
- storyboard
- video_editing

### Writing / script
- scriptwriting
- screenwriting
- voice_over
- advertising_copy
- hook_retention
- storytelling
- children_content
- youtube_script
- social_content

### Academic / research
- academic_research
- literature_review
- methodology
- qualitative_research
- quantitative_analysis
- interdisciplinary_research
- citation_review
- argumentation

### Data / documents
- data_analysis
- spreadsheet
- charts
- report
- docx
- pdf
- slides
- presentation
- google_docs_workflow

### Business / marketing
- marketing
- content_strategy
- product_marketing
- creative_campaign
- customer_research
- pitching
- business_analysis
- remote_work

### General problem solving
- comparison
- recommendation
- troubleshooting
- how_to
- learning
- translation
- summarization

## 6. Router behavior and conflict prevention

Each skill definition must include conflict metadata. Router resolution order:

1. Detect explicit project context.
2. Detect required freshness/tooling.
3. Choose primary domain.
4. Choose one primary skill.
5. Add supporting skills only when they materially improve the task.
6. Apply conflict rules.
7. Apply domain-specific authority rules.
8. Reject duplicate/competing authority loaders.

Examples:

- Photoshop request -> `photoshop + graphic_design`; trading excluded.
- BTC live analysis -> `trading_router + crypto + live_data_validation`; Blender/Adobe excluded.
- Blender shoe model -> `blender_modeling + design_3d`; `to3D` optional only if useful.
- Video scene prompt -> `video_prompt + scene_continuity + camera_direction`; coding excluded unless code generation is requested.
- Android app bug -> `android + debugging + coding`.
- Academic critique -> `critical_thinking + academic_research + citation_review`.

## 7. Tool / plugin routing

Plugins are tools, not reasoning policy.

Initial routing registry:

- Figma -> ux_ui, product_design, design_system
- Product Design -> product_design, prototyping/user-flow workflows
- Runway -> image/video generation and editing
- to3D -> design_3d / asset bootstrap
- Scite -> evidence validation / academic critique
- Massive -> live stocks, forex, futures, indices, crypto data
- Binance -> crypto public market data
- Superpowers -> planning, TDD, debugging, code review, verification workflows

A plugin must not be invoked solely because it is installed.

## 8. Knowledge-source policy

`sources.yaml` becomes a knowledge registry only.

Source modes:

- `TRAINING_OK`
- `RAG_ONLY`
- `REFERENCE_ONLY`
- `MANUAL_REVIEW`

Default policy changes from permissive training to conservative:

- default training = false;
- RAG/reference can be broader;
- license and provenance remain mandatory;
- mixed-license repos may be reference-only unless path-level rules are explicit;
- model weights, datasets, media, icons, fonts, and screenshots require separate rights review.

## 9. Project-state routing

`projects.yaml` maps project families to their canonical state entrypoints.

Trading project rule:

- `CURRENT_HANDOFF.md` and the checkpoint it names define current strategy authority;
- older checkpoints may remain historical but cannot claim active authority;
- legacy multi-coin/Forex/Meme/Signal execution state retired by the current handoff must not be loaded as active execution state;
- live/runtime validation remains mandatory before claiming a deployment is LIVE.

This design explicitly resolves the current conflict where an older `MASTER_TRADING_STATE.md` still names `BYBIT-AUTO-1.7.3` while the newer `CURRENT_HANDOFF.md` names BTC-only `BYBIT-BTC-STATEFLOW-2.1` as active authority.

## 10. Legacy cleanup policy

No bulk deletion by filename/version pattern.

For every candidate legacy file:

1. Search references from source, workflows, active docs, AGENTS/CLAUDE instructions, and current checkpoints.
2. Determine whether content is historical, superseded, or still operational.
3. Migrate any still-valid unique information into the canonical current state if needed.
4. Remove the file from `main` only when it is both superseded and no longer required by live/runtime workflows.
5. Preserve recoverability through Git history.

Likely cleanup candidates include old root version audit/state files, obsolete handoff documents, redundant Bybit Auto checkpoint versions, and superseded KAGGRICULTURE version checkpoints, but each must pass the reference check first.

## 11. New-chat behavior

Persistent instruction target:

1. New substantive request arrives.
2. If GitHub is available, refresh `AI_SKILL_LIBRARY/checkpoint.json`.
3. Load `GITHUB_BRAIN_V2.md`.
4. Run router classification.
5. Load only the selected skills and project state.
6. Use relevant sources/plugins/tools.
7. Run critical review + verification before final answer where appropriate.

Compatibility aliases:

- `GITHUB_BRAIN_V1` -> redirect to current V2 manifest after migration.
- `GITHUB_BRAIN_V2` -> canonical activation key.

Important product limitation: repository instructions can guide repo-aware/context-aware sessions, but GitHub alone cannot technically force a platform surface that has no GitHub connector/context to perform a live GitHub read. The fallback rule must remain explicit.

## 12. Validation and CI

Add validators/tests for:

- schema validity;
- skill file existence;
- router targets;
- duplicate skill ids;
- cycles in `requires`;
- impossible conflicts;
- missing tools/sources;
- duplicate active authority for the same project;
- multiple `CURRENT`/`ACTIVE` claims in one project family;
- stale checkpoint references;
- license/source-policy violations;
- V1 compatibility redirect;
- dry-run routing examples.

CI must fail on structural or authority conflicts before merge.

## 13. Migration sequence

1. Introduce V2 manifest/router/protocol/schemas without deleting V1.
2. Add core skills and router tests.
3. Add domain skills in grouped batches.
4. Split plugin/tool registry from source registry.
5. Add project authority registry.
6. Update `AGENTS.md` to a minimal V2 bootstrap.
7. Run authority/reference audit.
8. Migrate valid legacy information.
9. Remove superseded/unreferenced files.
10. Add V1 -> V2 compatibility redirect.
11. Run full CI and authority validation.
12. Merge only after green verification.

## 14. Extension points

Future growth is expected and must not require another architecture rewrite.

New capability should normally require only:

- one new skill file;
- optional router trigger entry;
- optional source entries;
- optional plugin/tool mapping;
- tests for conflict/selection behavior.

The core bootstrap and routing contract should remain stable.

## 15. Acceptance criteria

V2 is ready for activation when all conditions hold:

- checkpoint identifies `GITHUB_BRAIN_V2` as canonical;
- V1 activation key safely redirects to V2;
- router selects relevant skills without loading unrelated domains;
- plugin registry is separated from skill/source registries;
- project authority registry prevents stale project state from outranking current state;
- current trading authority conflict is resolved;
- legacy cleanup removes only verified superseded/unreferenced files;
- no secrets/private chat dumps are added;
- validators/tests pass;
- CI on the migration branch is green;
- post-merge CI on `main` is green.

## 16. Safety of activation

Activation is staged, reversible through Git history, and does not mutate live trading state merely by changing the knowledge/router layer. Any runtime trading-code modification requires its own project-specific implementation and validation path.
