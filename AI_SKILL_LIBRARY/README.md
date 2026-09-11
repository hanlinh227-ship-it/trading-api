# AI Skill Library — GITHUB_BRAIN_V2

`GITHUB_BRAIN_V2` is the repository-level routed skill layer for ChatGPT, Claude, Codex, and other repo-aware agents.

It does **not** fine-tune a model. It provides a deterministic bootstrap, skill router, project-authority registry, plugin capability map, and license-aware knowledge source registry.

## Bootstrap

Canonical order:

1. `AI_SKILL_LIBRARY/checkpoint.json`
2. `AI_SKILL_LIBRARY/GITHUB_BRAIN_V2.md`
3. `AI_SKILL_LIBRARY/CORE_PROTOCOL.md`
4. `AI_SKILL_LIBRARY/router.yaml`
5. selected skill files only
6. current project authority only when the selected route requires it
7. relevant `sources.yaml` categories and optional `plugins.yaml` capabilities
8. critical review and verification

The stable activation key is `GITHUB_BRAIN_V2`. `GITHUB_BRAIN_V1` remains a compatibility alias and routes to V2.

## Why routing exists

The repository contains unrelated domains and historical project material. Loading everything at once causes context contamination and competing instructions. V2 therefore routes first and loads the smallest relevant context.

Default domain budget: **one primary skill + at most two supporting domain skills**. `critical_thinking` and `verification` are cross-cutting layers and do not count toward this budget.

Trading state is never a global preload.

## Skill families

V2 initially routes across:

- core reasoning, research, critique, planning and verification;
- coding, architecture, debugging/TDD, GitHub/API/database/security, deployment, Cloudflare, Android, web and automation;
- crypto, forex, futures, indices, market microstructure, technical analysis, risk/execution, quant/backtesting and MT5/MQL5;
- game design/development, Godot/Unity/web games, game AI, level design and optimization;
- graphic design, UX/UI, product design, branding, typography, color/layout and product photography;
- 3D modeling, topology, UV/texturing, materials, lighting, rigging/animation/rendering and Blender;
- Photoshop, Illustrator, Premiere Pro, After Effects, Lightroom, Audition, InDesign and Acrobat workflows;
- prompt engineering, image/video prompting, negative constraints, prompt debugging, continuity/camera/storyboard and generative-media workflows;
- screenwriting, voice-over, advertising copy, hooks/retention, storytelling, children's content, YouTube/social scripts;
- academic/literature/methodology/qualitative/quantitative/interdisciplinary/citation review;
- spreadsheets, charts, reports, DOCX/PDF/slides/presentations;
- marketing, content strategy, product marketing, campaigns, customer research, pitching, business analysis and remote-work evaluation.

Closely related leaf capabilities are exposed as aliases under focused skill files to keep the library compact and avoid contradictory duplicate instructions.

## Plugins are not skills

`plugins.yaml` maps optional capabilities. Current mappings include Figma, Product Design, Runway, to3D, Scite, Massive, Binance and Superpowers.

A missing optional plugin must not break the route. The agent should fall back to available tools/source reasoning and disclose material limitations.

## Project authority

`router.yaml` defines exactly one `CURRENT_AUTHORITY` for each registered project scope. Historical snapshots cannot override it.

For Trading, authority is loaded only after a Trading route is selected. External repositories/plugins are references or data sources, never proof of profitability or execution authority.

## Knowledge sources and licensing

`sources.yaml` is knowledge-only. It is separate from behavioral skills.

Policy for new sources:

- default retrieval: enabled when license/provenance permit;
- default training: **disabled**;
- future training/fine-tune dataset use requires explicit approval;
- manual/per-item/unclear rights remain disabled until reviewed;
- provenance is preserved;
- third-party repositories are never executed merely for ingestion.

Existing V1 sources retain their explicit approved flags during migration.

## Adding a new skill

To extend V2 without redesigning the architecture:

1. Add one focused Markdown skill file under `AI_SKILL_LIBRARY/skills/<family>/`.
2. Register one unique skill ID in `router.yaml`.
3. Add aliases/triggers/exclusions/requirements/conflicts/priority.
4. Add optional plugin capabilities or source categories only if needed.
5. Add or update tests.
6. Run `validate_brain.py` and CI.

Do not create another global checkpoint merely to add a domain.

## Validation

```bash
python -m py_compile AI_SKILL_LIBRARY/ingest_sources.py AI_SKILL_LIBRARY/validate_registry.py AI_SKILL_LIBRARY/validate_brain.py
python -m unittest discover -s AI_SKILL_LIBRARY/tests -v
python AI_SKILL_LIBRARY/validate_registry.py
python AI_SKILL_LIBRARY/validate_brain.py
python AI_SKILL_LIBRARY/ingest_sources.py --all --dry-run --output /tmp/ai-skill-library.jsonl
```

CI also performs a non-executing upstream repository audit.

## New chats

Persistent ChatGPT/project instructions can point to `GITHUB_BRAIN_V2`. In a repo-aware chat, the first substantive task should refresh the checkpoint and pass through the router.

GitHub cannot itself force a ChatGPT surface that does not expose GitHub access to perform a fresh repository read. In that case, the protocol requires explicit disclosure and fallback to last-known context rather than pretending a refresh occurred.
