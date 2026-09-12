# Creative Visual Fusion Design

## Goal
Absorb open-source image-generation, prompt, storyboard, visual-consistency, design, and editing patterns into the existing GITHUB_BRAIN_V4 without creating a parallel creative brain, duplicate routing authority, or mandatory local/runtime framework dependency.

## Canonical architecture

`request -> task_router -> runtime_profile -> project_authority_if_required -> primary_domain -> primary_skill -> capability_fusion -> creative_visual_fusion_if_relevant -> bounded supporting skills/context/tools -> execute -> creative quality critic when material -> verification -> answer`

Creative Visual Fusion is a capability policy under the existing V4 authority chain. It does not replace `task_router`, project authority, stable security, existing prompt/design/adobe/writing skills, or the Skill Gateway capsule contract.

## Harmonization rules
- Canonical-skill-first: strengthen existing skills such as `image_prompt`, `video_prompt`, `prompt_debugging`, `character_consistency`, `scene_continuity`, `camera_direction`, `storyboard`, `graphic_design`, `layout`, `lighting`, `photoshop`, `premiere_pro`, `scriptwriting`, and `storytelling` rather than creating equivalent duplicate skills.
- Open-source repositories are evidence/pattern sources only; they receive no routing or reasoning authority.
- Prefer native contracts over mandatory framework dependencies.
- Zero-local remains the normal runtime contract.
- No provider/model/tool may expand permissions or override security/project authority.
- Creative continuity/memory remains bounded context, never truth authority.

## Native creative capability modules
1. `creative_direction`: audience, platform, purpose, visual language, brand/style, deliverable constraints.
2. `script_to_shots`: hook/beat decomposition, scene mapping, shot planning, pacing, transition logic, coverage diversity.
3. `visual_prompt_compiler`: subject, action, environment, composition, camera, lighting, materials/style, continuity facts, negative constraints, render constraints.
4. `continuity_engine`: character identity, wardrobe, props, environment, object counts, temporal state, camera diversity, previous/next-scene compatibility.
5. `visual_edit_reasoning`: classify edit intent; target/segment first; choose remove/replace/recolor/relight/inpaint/outpaint/repair/background operations; preserve non-target content.
6. `render_quality_critic`: prompt fidelity, identity/continuity, object-count, anatomy/deformation risk, perspective, lighting, camera repetition, design hierarchy, export/render suitability.

## Absorbed open-source patterns
- ControlNet: pose/depth/edge/composition conditioning patterns.
- IP-Adapter: image-reference/identity/style conditioning patterns.
- Segment Anything/SAM-family: target segmentation and mask-first editing patterns.
- GroundingDINO-style grounding: text-to-object targeting before local edits.
- Real-ESRGAN-style restoration: post-edit restoration/upscale as a finalization stage, not a creative authority.
- ComfyUI-style workflow graphs: explicit visual pipeline composition and reproducible node-like stages, without requiring ComfyUI in Stable runtime.
- Existing prompt/story/script repositories remain source inputs under the registry and harmonization rules.

## Profile behavior
### FAST
- No external creative framework call for routing.
- Use existing primary skill/capsule and a lightweight creative contract only when the selected skill is in prompt/design/adobe/writing creative scope.
- No durable continuity preload.

### STANDARD
- May use bounded continuity state and one creative-support capability set.
- May perform one maker/checker pass when material.

### DEEP
- May use script-to-shots, continuity engine, edit reasoning, and creative critic together inside the existing bounded execution graph.
- No hidden reasoning persistence; only explicit continuity facts, evidence references, constraints, and verification outcomes may persist.

## Edit safety and fidelity
- Existing user-provided image/reference is source of truth for identity/geometry/style facts unless the user explicitly asks to change them.
- Edit the smallest necessary region/scope.
- Do not silently add/remove characters, props, text, branding, or scene elements.
- Preserve exact character/object count when specified.
- When edit target or reference is unavailable, fail closed rather than inventing a target.

## Evaluation contracts
Regression tests must verify:
- checkpoint resolves the creative fusion policy;
- creative fusion remains subordinate to capability fusion/harmonization/security/authority;
- no parallel router or creative authority is introduced;
- existing canonical skills remain the route surface;
- FAST remains zero-local/no external creative routing dependency;
- continuity state is bounded and authority-subordinate;
- edit reasoning is target-preserving and fail-closed;
- upstream sources are registry references with training disabled;
- release manifest pins the new policy and all changed Stable files.

## Release
Promote as a new immutable V4 capability release only after Brain tests, V4/router/authority/registry validators, Skill Gateway snapshot validation, CI, exact-main deployment, and production route checks pass. The previous verified release remains rollback authority until post-merge verification succeeds.
